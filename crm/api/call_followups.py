"""Manager outcomes and native callback tasks, separate from provider facts."""

from hashlib import sha256

import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.utils import add_days, get_datetime, now_datetime, today

from crm.api import call_work, celio_tasks
from crm.call_work_storage import internal_write

DOCTYPE = "CRM Call Outcome"
OUTCOMES = ("Agreed", "Callback", "Not interested", "Wrong number")
TERMINAL = ("Completed", "No Answer", "Busy", "Failed", "Canceled")


def _context_condition(table):
	from crm.api.telephony import _reference_query

	allowed = (Coalesce(table.reference_doctype, "") == "") & (Coalesce(table.reference_docname, "") == "")
	for dt in celio_tasks.CONTEXTS.values():
		if (permitted := _reference_query(dt[0])) is not None:
			allowed |= (table.reference_doctype == dt[0]) & table.reference_docname.isin(permitted)
	return allowed


def review_query():
	t = frappe.qb.DocType(DOCTYPE)
	return frappe.qb.from_(t).select(t.name).where(_context_condition(t))


def task_query():
	t = frappe.qb.DocType("CRM Task")
	if not frappe.has_permission("CRM Task", "read"):
		return frappe.qb.from_(t).select(t.name).where(t.name == "")
	return frappe.qb.get_query("CRM Task", fields=["name"], ignore_permissions=False).where(
		_context_condition(t)
	)


def review_calls(outcome=None):
	t = frappe.qb.DocType(DOCTYPE)
	q = frappe.qb.from_(t).select(t.call_log).where(t.name.isin(review_query()))
	return q.where(t.outcome == outcome) if outcome else q


def due_calls(employee=""):
	t, link = frappe.qb.DocType("CRM Task"), frappe.qb.DocType("Dynamic Link")
	q = (
		frappe.qb.from_(link)
		.join(t)
		.on(link.link_name == t.name)
		.select(link.parent)
		.where(
			(link.parenttype == "CRM Call Log")
			& (link.parentfield == "links")
			& (link.link_doctype == "CRM Task")
			& t.name.isin(task_query())
			& t.status.notin(("Done", "Canceled"))
			& (t.due_date < add_days(today(), 1))
		)
	)
	return q.where(t.assigned_to == employee) if employee else q


def summary(rows):
	"""Project only authorized outcomes; never read personal conversation drafts."""
	if not rows:
		return
	names = [r["name"] for r in rows]
	t = frappe.qb.DocType(DOCTYPE)
	reviews = {
		r.call_log: r.outcome
		for r in frappe.qb.from_(t)
		.select(t.call_log, t.outcome)
		.where(t.call_log.isin(names) & t.name.isin(review_query()))
		.run(as_dict=True)
	}
	for r in rows:
		r["outcome"] = reviews.get(r["name"], "")
		r["unhandled_missed"] = bool(
			r["type"] == "Incoming" and r["status"] in TERMINAL[1:] and not r["outcome"]
		)
		r["due_tasks"] = 0
		r["overdue_tasks"] = 0
	task, link = frappe.qb.DocType("CRM Task"), frappe.qb.DocType("Dynamic Link")
	due = (
		frappe.qb.from_(link)
		.join(task)
		.on(task.name == link.link_name)
		.select(link.parent, task.name, task.due_date)
		.where(
			(link.parenttype == "CRM Call Log")
			& (link.parentfield == "links")
			& (link.link_doctype == "CRM Task")
			& link.parent.isin(names)
			& task.name.isin(task_query())
			& task.status.notin(("Done", "Canceled"))
			& (task.due_date < add_days(today(), 1))
		)
		.distinct()
		.run(as_dict=True)
	)
	indexed = {r["name"]: r for r in rows}
	for task in due:
		r = indexed[task.parent]
		r["due_tasks"] += 1
		if str(task.due_date)[:10] < today():
			r["overdue_tasks"] += 1


def _call(name, write=False, lock=False):
	from crm.api.telephony import get_call, has_customer_reference

	data = get_call(name)
	doc = frappe.get_doc("CRM Call Log", name, for_update=lock)
	doc.check_permission("read")
	if lock and has_customer_reference(doc):
		if doc.reference_doctype not in {"CRM Lead", "CRM Deal", "Contact"} or not doc.reference_docname:
			frappe.throw(_("This call is not available."), frappe.PermissionError)
		parent = frappe.get_doc(doc.reference_doctype, doc.reference_docname, for_update=True)
		parent.check_permission("read")
	if write:
		call_work._require()
		doc.check_permission("write")
		if doc.status not in TERMINAL:
			frappe.throw(_("Finish the call before saving its outcome."))
	return doc, data


def _review(name, lock=False):
	if frappe.db.get_value(DOCTYPE, name, "name", for_update=lock, order_by=None):
		return frappe.get_doc(DOCTYPE, name, for_update=lock)
	return None


def _check_review_context(review, lock=False):
	if review and review.reference_doctype:
		kind = next(
			(k for k, (dt, _) in celio_tasks.CONTEXTS.items() if dt == review.reference_doctype), None
		)
		call_work._context(kind, review.reference_docname, current=lock)


def _materials(doc):
	notes, tasks = [], []
	for link in doc.links:
		try:
			if link.link_doctype == "FCRM Note":
				note = frappe.get_doc("FCRM Note", link.link_name)
				note.check_permission("read")
				kind = next(
					(k for k, (dt, _) in celio_tasks.CONTEXTS.items() if dt == note.reference_doctype), None
				)
				call_work._context(kind, note.reference_docname)
				notes.append(call_work._project_note(note))
			elif link.link_doctype == "CRM Task":
				task = celio_tasks._task(link.link_name)
				item = celio_tasks.project(task)
				item["description_text"] = call_work._plain_text(task.description)
				tasks.append(item)
		except (frappe.PermissionError, frappe.DoesNotExistError):
			continue
	return {
		"notes": list({n["name"]: n for n in notes}.values()),
		"tasks": list({t["name"]: t for t in tasks}.values()),
	}


@frappe.whitelist()
def get_workspace(name):
	doc, data = _call(name)
	review = _review(name)
	materials = _materials(doc)
	# A canonical note/task can explicitly belong to a different accessible
	# customer than the call's original primary reference. Offer both choices.
	from crm.api.telephony import _reference_labels

	material_refs = [
		frappe._dict(reference_doctype=n["reference_doctype"], reference_docname=n["reference_docname"])
		for n in materials["notes"]
	]
	for task in materials["tasks"]:
		if task["context"]["kind"] in celio_tasks.CONTEXTS:
			material_refs.append(
				frappe._dict(
					reference_doctype=celio_tasks.CONTEXTS[task["context"]["kind"]][0],
					reference_docname=task["context"]["name"],
				)
			)
	for ref in _reference_labels(material_refs).values():
		if not any(r["doctype"] == ref["doctype"] and r["name"] == ref["name"] for r in data["references"]):
			data["references"].append(ref)
	can_manage = bool(doc.status in TERMINAL and frappe.has_permission("CRM Call Log", "write", doc))
	try:
		_check_review_context(review)
	except frappe.PermissionError:
		return {
			"viewer": frappe.session.user,
			"can_manage": False,
			"review": None,
			"references": data["references"],
			**materials,
		}
	context = None
	if review and review.reference_doctype:
		context = {"doctype": review.reference_doctype, "name": review.reference_docname}
	return {
		"viewer": frappe.session.user,
		"can_manage": can_manage,
		"review": {
			"revision": review.revision if review else 0,
			"outcome": review.outcome if review else "",
			"callback_task": str(review.callback_task or "") if review else "",
			"context": context,
			"processed_by": review.processed_by if review else "",
			"processed_at": str(review.processed_at) if review else "",
		},
		"references": data["references"],
		**materials,
	}


@frappe.whitelist(methods=["POST"])
def save_outcome(name, outcome, expected_revision, mutation_id, expected_viewer, callback=None):
	return call_work._retry(
		lambda: _save_outcome(name, outcome, expected_revision, mutation_id, expected_viewer, callback)
	)


def _save_outcome(name, outcome, expected_revision, mutation_id, expected_viewer, callback):
	call_work._require(expected_viewer)
	if outcome not in OUTCOMES or not isinstance(mutation_id, str) or not 16 <= len(mutation_id) <= 80:
		frappe.throw(_("Choose a call outcome."))
	callback = frappe.parse_json(callback) if isinstance(callback, str) else callback
	if outcome == "Callback":
		if (
			not isinstance(callback, dict)
			or set(callback) != {"context_kind", "context_name", "title", "assigned_to", "due_date"}
			or not all(isinstance(v, str) for v in callback.values())
			or not callback["assigned_to"]
			or not callback["due_date"]
		):
			frappe.throw(_("Choose a customer, assignee and callback time."))
		try:
			get_datetime(callback["due_date"])
		except (ValueError, TypeError):
			frappe.throw(_("Choose a valid callback time."))
	elif callback:
		frappe.throw(_("Callback details require the Callback outcome."))
	request_hash = sha256(frappe.as_json([name, outcome, expected_revision, callback]).encode()).hexdigest()
	call_work._lock_author()
	_call(name, write=True)
	# Same lock/order as provider refresh and explicit conversation links.
	from crm.integrations.exolve.api import _lock_call

	_lock_call(name)
	doc, _call_data = _call(name, write=True, lock=True)
	review = _review(name, lock=True)
	_check_review_context(review, lock=True)
	if review and review.last_mutation == mutation_id:
		if review.last_hash != request_hash or review.processed_by != frappe.session.user:
			frappe.throw(_("This request was already used for different changes."))
		return {**get_workspace(name), "replayed": True}
	if str(review.revision if review else 0) != str(expected_revision):
		frappe.throw(
			_("The call outcome changed in another window. Reload before saving."),
			frappe.TimestampMismatchError,
		)
	if review and review.callback_task:
		task = celio_tasks._task(review.callback_task, lock=True)
		if task.status not in {"Done", "Canceled"}:
			frappe.throw(_("Complete or cancel the existing callback task before changing the outcome."))
	if not review:
		review = frappe.get_doc(
			{"doctype": DOCTYPE, "name": name, "__islocal": 1, "call_log": name, "revision": 0}
		)
	if outcome == "Callback":
		context = call_work._context(callback["context_kind"], callback["context_name"], current=True)
		# This top-level transaction owns retry/rollback and the call lock.
		result = celio_tasks._save_task(
			{
				**callback,
				"description": _("Callback from call history"),
				"status": "Todo",
				"priority": "Medium",
			},
			"callback-" + sha256(f"{name}\0{mutation_id}".encode()).hexdigest(),
			None,
			None,
			expected_viewer,
		)
		review.reference_doctype, review.reference_docname = context["doctype"], context["name"]
		review.callback_task = result["task"]["name"]
		if not doc.has_link("CRM Task", review.callback_task):
			doc.link_with_reference_doc("CRM Task", review.callback_task)
			flag = frappe.flags.in_exolve_sync
			try:
				frappe.flags.in_exolve_sync = True
				doc.save(ignore_permissions=True)
			finally:
				frappe.flags.in_exolve_sync = flag
	review.outcome, review.processed_by, review.processed_at = outcome, frappe.session.user, now_datetime()
	review.revision = (review.revision or 0) + 1
	review.last_mutation, review.last_hash = mutation_id, request_hash
	with internal_write():
		review.save(ignore_permissions=True)
	return {**get_workspace(name), "replayed": False}


@frappe.whitelist(methods=["POST"])
def complete_task(name, task, expected_modified, mutation_id, expected_viewer, status="Done"):
	def save():
		call_work._require(expected_viewer)
		if status not in {"Done", "Canceled"}:
			frappe.throw(_("Invalid task completion status."))
		call_work._lock_author()
		from crm.integrations.exolve.api import _lock_call

		_lock_call(name)
		doc, _call_data = _call(name, lock=True)
		if not doc.has_link("CRM Task", task):
			frappe.throw(_("This task is not linked to this call."), frappe.PermissionError)
		celio_tasks._save_task({"status": status}, mutation_id, task, expected_modified, expected_viewer)
		return get_workspace(name)

	return call_work._retry(save)
