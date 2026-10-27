"""Source-owned task operations for Celio. CRM Task and its native hooks stay canonical."""
from hashlib import sha256
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, nowdate

FIELDS = {"title", "description", "due_date", "priority", "assigned_to", "status"}
CONTEXTS = {"lead": ("CRM Lead", "lead_name"), "deal": ("CRM Deal", "deal_name")}


def available(user=None):
	user = user or frappe.session.user
	return bool(user != "Guest" and frappe.db.get_value("User", user, "enabled")
		and frappe.has_permission("CRM Task", "read", user=user))


def readable(doc, user=None, ptype="read", current=False):
	user = user or frappe.session.user
	if not available(user) or not frappe.has_permission("CRM Task", ptype, doc=doc, user=user):
		return False
	if doc.reference_doctype or doc.reference_docname:
		return bool(doc.reference_doctype and doc.reference_docname
			and frappe.db.get_value(doc.reference_doctype, doc.reference_docname, "name", for_update=current, order_by=None)
			and frappe.has_permission(doc.reference_doctype, "read",
				doc=frappe.get_doc(doc.reference_doctype, doc.reference_docname, for_update=current), user=user))
	return True


def _require():
	if not available():
		frappe.throw(_("This CRM task is not available."), frappe.PermissionError)


def _task(name, lock=False):
	_require()
	if not frappe.db.get_value("CRM Task", name, "name", for_update=lock, order_by=None):
		frappe.throw(_("This CRM task is not available."), frappe.PermissionError)
	doc = frappe.get_doc("CRM Task", name, for_update=lock)
	if not readable(doc, current=lock):
		frappe.throw(_("This CRM task is not available."), frappe.PermissionError)
	return doc


def _context(doc):
	kind = next((key for key, (dt, _) in CONTEXTS.items() if dt == doc.reference_doctype), "")
	if not kind or not doc.reference_docname:
		return {"kind": "", "name": "", "label": "", "route": "/crm/tasks"}
	dt, field = CONTEXTS[kind]
	return {"kind": kind, "name": doc.reference_docname,
		"label": frappe.db.get_value(dt, doc.reference_docname, field) or doc.reference_docname,
		"route": f"/crm/{'leads' if kind == 'lead' else 'deals'}/{quote(str(doc.reference_docname), safe='')}#tasks"}


def project(doc):
	context = _context(doc)
	return {"name": str(doc.name), "source": "crm", "source_label": "EXP CRM",
		"subject": doc.title, "title": doc.title, "description": doc.description or "",
		"status": doc.status or "Todo", "state_group": "completed" if doc.status == "Done" else "cancelled" if doc.status == "Canceled" else "open",
		"priority": doc.priority or "Medium", "due_date": str(doc.due_date) if doc.due_date else None,
		"exp_end_date": str(doc.due_date) if doc.due_date else None, "modified": str(doc.modified),
		"assigned_to": doc.assigned_to or "", "accountable_owner": doc.assigned_to or "",
		"assignees": [doc.assigned_to] if doc.assigned_to else [], "context": context,
		"scope": "crm", "project": None, "team": None, "moscow": "", "bug": {"applicable": False}, "relative_estimate": {"status": "not_applicable"},
		"planned_effort_hours": None, "actual_hours": None, "task_type": None,
		"is_overdue": bool(doc.due_date and getdate(doc.due_date) < getdate(nowdate()) and doc.status not in {"Done", "Canceled"}),
		"can_write": frappe.db.table_exists("CRM Task Operation") and readable(doc, ptype="write"), "can_change_status": False,
		"can_edit_content": False, "can_manage_dates": False, "can_complete": False,
		"route": f"/celio/crm-tasks/{quote(str(doc.name), safe='')}", "crm_route": context["route"]}


def my_work(user=None):
	user = user or frappe.session.user
	if not available(user):
		return []
	# Same personal scope as ERP My Work; permission filtering precedes all counts.
	rows = frappe.get_list("CRM Task", filters={"assigned_to": user}, fields=["name"], limit_page_length=0)
	return [project(doc) for row in rows if readable(doc := frappe.get_doc("CRM Task", row.name), user)]


@frappe.whitelist(methods=["GET"])
def get_task(name: str):
	doc = _task(name)
	return {"task": project(doc), **options()}


@frappe.whitelist(methods=["GET"])
def get_document(name: str):
	"""Native CRM form refresh, including the source parent and field-level guards."""
	doc = _task(name)
	from frappe.client import get
	return {"viewer": frappe.session.user, "document": get("CRM Task", str(doc.name)),
		"safe_save": frappe.db.table_exists("CRM Task Operation")}


@frappe.whitelist(methods=["GET"])
def options():
	_require()
	meta = frappe.get_meta("CRM Task")
	return {"viewer": frappe.session.user, "can_create": frappe.db.table_exists("CRM Task Operation") and frappe.has_permission("CRM Task", "create"),
		"statuses": meta.get_field("status").options.splitlines(),
		"priorities": meta.get_field("priority").options.splitlines()}


@frappe.whitelist(methods=["GET"])
def search_contexts(kind: str = "lead", query: str = ""):
	_require()
	if kind not in CONTEXTS:
		frappe.throw(_("Invalid customer context."))
	dt, field = CONTEXTS[kind]
	if not frappe.has_permission(dt, "read"):
		return []
	pattern = "%" + str(query or "")[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
	return [{"value": row.name, "label": row.get(field) or row.name} for row in frappe.get_list(dt,
		fields=["name", field], filters={field: ["like", pattern]}, order_by="modified desc, name desc", limit_page_length=20)
		if frappe.has_permission(dt, "read", doc=frappe.get_doc(dt, row.name))]


@frappe.whitelist(methods=["GET"])
def search_people(name: str | None = None, kind: str = "", context: str = "", query: str = ""):
	_require()
	doc = _task(name) if name else frappe.get_doc({"doctype": "CRM Task"})
	if not name:
		_set_context(doc, kind, context)
	pattern = "%" + str(query or "")[:100].replace("%", "\\%").replace("_", "\\_") + "%"
	# This is the CRM assignment directory, not Celio membership or role provisioning.
	users = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"},
		or_filters={"full_name": ["like", pattern], "name": ["like", pattern]}, fields=["name", "full_name"], limit=0)
	return [{"value": row.name, "label": row.full_name or row.name} for row in users if readable(doc, row.name)][:20]


def _set_context(doc, kind, name, current=False):
	if not kind and not name:
		return
	if kind not in CONTEXTS or not name:
		frappe.throw(_("Choose an available customer context."))
	dt = CONTEXTS[kind][0]
	if not frappe.db.get_value(dt, name, "name", for_update=current, order_by=None) or not frappe.has_permission(dt, "read", doc=frappe.get_doc(dt, name, for_update=current)):
		frappe.throw(_("Choose an available customer context."), frappe.PermissionError)
	doc.reference_doctype, doc.reference_docname = dt, name


@frappe.whitelist(methods=["POST"])
def save_task(values: dict | str, mutation_id: str, name: str | None = None,
	expected_modified: str | None = None, expected_viewer: str | None = None):
	for attempt in range(3):
		try:
			return _save_task(values, mutation_id, name, expected_modified, expected_viewer)
		except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
			request = getattr(frappe.local, "request", None)
			# Only these top-level RPCs own the whole transaction. An embedded
			# server call must leave rollback/retry to its caller.
			if attempt == 2 or not request or request.method != "POST" or frappe.form_dict.get("cmd") not in {
				"crm.api.celio_tasks.save_task", "celio.api.crm_tasks.save_task",
			}:
				raise
			frappe.db.rollback()
			# Permissions cached by the failed attempt may have been revoked.
			frappe.clear_cache(user=frappe.session.user)
			frappe.local.user_perms = None


def _save_task(values, mutation_id, name, expected_modified, expected_viewer):
	_require()
	if not frappe.db.table_exists("CRM Task Operation"):
		frappe.throw(_("Task editing is not ready on this site."))
	if expected_viewer != frappe.session.user:
		frappe.throw(_("Your account changed. Reload before saving."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else values
	allowed = FIELDS | ({"context_kind", "context_name"} if not name else set())
	if not isinstance(values, dict) or set(values) - allowed or not isinstance(mutation_id, str) or not 16 <= len(mutation_id) <= 100:
		frappe.throw(_("Invalid CRM task changes."))
	request_hash = sha256(frappe.as_json([name, expected_modified, values]).encode()).hexdigest()
	operation = sha256(f"{frappe.session.user}\0{mutation_id}".encode()).hexdigest()
	# A missing receipt has no row to lock. Serialize this author's saves on an
	# existing row until the HTTP transaction commits, before reading the receipt.
	locked_author = frappe.db.get_value("User", frappe.session.user, ["modified", "enabled"],
		as_dict=True, for_update=True)
	snapshot_author = frappe.db.get_value("User", frappe.session.user, ["modified", "enabled"], as_dict=True)
	# Native User saves change modified when roles or enabled state change.
	# A request that waited for that save must restart before trusting its
	# earlier permission snapshot. Embedded callers still own their rollback.
	if locked_author != snapshot_author:
		raise frappe.QueryDeadlockError
	_require()
	previous = frappe.db.get_value("CRM Task Operation", operation, ["request_hash", "task"], as_dict=True, for_update=True, order_by=None)
	if previous:
		if previous.request_hash != request_hash:
			frappe.throw(_("This request was already used for different changes."))
		# A locking receipt read can see a committed winner that predates this
		# request's consistent snapshot. Retry the owning RPC before reading
		# its Task and permissions; never turn that stale snapshot into a 403.
		if not frappe.db.get_value("CRM Task Operation", operation, "name", order_by=None):
			raise frappe.QueryDeadlockError
		return {"task": project(_task(previous.task, lock=True)), "replayed": True}
	doc = _task(name, lock=True) if name else frappe.get_doc({"doctype": "CRM Task", "status": "Todo", "priority": "Medium"})
	if name:
		if not readable(doc, ptype="write", current=True):
			frappe.throw(_("You cannot edit this CRM task."), frappe.PermissionError)
		if not expected_modified or get_datetime(doc.modified) != get_datetime(expected_modified):
			frappe.throw(_("This task changed in another window. Your draft is kept; reload before saving."), frappe.TimestampMismatchError)
	else:
		doc.check_permission("create")
		_set_context(doc, values.get("context_kind", ""), values.get("context_name", ""), current=True)
	for field in FIELDS & values.keys():
		if values[field] is not None and not isinstance(values[field], str):
			frappe.throw(_("Invalid CRM task changes."))
		doc.set(field, values[field] or None)
	if not (doc.title or "").strip() or len(doc.title) > 140:
		frappe.throw(_("Enter a task title of up to 140 characters."))
	meta = frappe.get_meta("CRM Task")
	for field in ("status", "priority"):
		if doc.get(field) not in meta.get_field(field).options.splitlines():
			frappe.throw(_("Invalid CRM task choices."))
	if doc.assigned_to and not readable(doc, doc.assigned_to, current=True):
		frappe.throw(_("The assignee must have access to this CRM task and its customer context."), frappe.PermissionError)
	# Native CRMTask.validate/after_insert own assignment ToDo and all other hooks.
	doc.save()
	# Native assignment updates _assign/modified after insert. Return its saved revision.
	doc.reload()
	from crm.task_operations import internal_write
	with internal_write():
		frappe.get_doc({"doctype": "CRM Task Operation", "name": operation, "user": frappe.session.user,
			"request_hash": request_hash, "task": doc.name}).insert(ignore_permissions=True)
	return {"task": project(doc), "replayed": False}
