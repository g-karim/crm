"""In-call work saves canonical notes/tasks before a provider Call Log exists."""
from hashlib import sha256
from urllib.parse import quote

from bs4 import BeautifulSoup
import frappe
from frappe import _
from frappe.utils import escape_html, get_datetime

from crm.api import celio_tasks

CONTEXTS = celio_tasks.CONTEXTS
_UNSET = object()


def _require(viewer=_UNSET):
	if (frappe.session.user == "Guest" or not frappe.db.get_value("User", frappe.session.user, "enabled")
		or not frappe.has_permission("CRM Call Log", "create") or (viewer is not _UNSET and viewer != frappe.session.user)):
		frappe.throw(_("Your account changed or calling is unavailable. Reload before saving."), frappe.PermissionError)


def _context(kind, name, current=False):
	if not isinstance(kind, str) or kind not in CONTEXTS or not isinstance(name, str) or not name:
		frappe.throw(_("Choose a lead or deal before saving."))
	dummy = frappe.get_doc({"doctype": "CRM Task"})
	celio_tasks._set_context(dummy, kind, name, current=current)
	doctype, field = CONTEXTS[kind]
	return {"kind": kind, "doctype": doctype, "name": name,
		"title": frappe.db.get_value(doctype, name, field) or name,
		"path": f"/crm/{'leads' if kind == 'lead' else 'deals'}/{quote(name, safe='')}"}


@frappe.whitelist()
def resolve_context(source=None):
	_require()
	source = frappe.parse_json(source) if isinstance(source, str) else source
	items = source if isinstance(source, list) else [source] if source else []
	if len(items) > 20:
		frappe.throw(_("Invalid customer context."))
	result = {}
	for item in items:
		if not isinstance(item, dict):
			frappe.throw(_("Invalid customer context."))
		doctype, name = item.get("doctype"), item.get("name")
		kind = next((key for key, (dt, _) in CONTEXTS.items() if dt == doctype), None)
		if kind:
			context = _context(kind, name)
			result[(doctype, name)] = context
		elif doctype == "Contact" and name:
			contact = frappe.get_doc("Contact", name)
			contact.check_permission("read")
			# Explicit links only; a matching phone never chooses a deal.
			linked = [(row.link_doctype, row.link_name) for row in contact.links]
			deal_names = frappe.get_all("CRM Contacts", filters={"contact": name, "parenttype": "CRM Deal"}, pluck="parent")
			linked.extend(("CRM Deal", value) for value in deal_names)
			for dt, value in linked:
				key = next((key for key, (model, _) in CONTEXTS.items() if model == dt), None)
				if key and value and frappe.has_permission(dt, "read", value):
					result[(dt, value)] = _context(key, value)
		else:
			frappe.throw(_("Invalid customer context."))
	return {"viewer": frappe.session.user, "contexts": list(result.values())}


@frappe.whitelist()
def search_contexts(kind="lead", query=""):
	_require()
	if not isinstance(kind, str) or kind not in CONTEXTS:
		frappe.throw(_("Invalid customer context."))
	doctype, field = CONTEXTS[kind]
	if not frappe.has_permission(doctype, "read"):
		return []
	pattern = "%" + str(query or "")[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
	return [_context(kind, row.name) for row in frappe.get_list(doctype, fields=["name"],
		filters={field: ["like", pattern]}, order_by="modified desc, name desc", limit_page_length=20)
		if frappe.has_permission(doctype, "read", row.name)]


@frappe.whitelist()
def options(kind, name):
	_require()
	context = _context(kind, name)
	return {"viewer": frappe.session.user, "context": context,
		"can_note": bool(frappe.has_permission("FCRM Note", "create")),
		"can_task": bool(frappe.has_permission("CRM Task", "create")),
		"people": celio_tasks.search_people(kind=kind, context=name) if celio_tasks.available() else [],
		"statuses": frappe.get_meta("CRM Task").get_field("status").options.splitlines(),
		"priorities": frappe.get_meta("CRM Task").get_field("priority").options.splitlines()}


def _lock_author():
	locked = frappe.db.get_value("User", frappe.session.user, ["modified", "enabled"], as_dict=True, for_update=True)
	if locked != frappe.db.get_value("User", frappe.session.user, ["modified", "enabled"], as_dict=True):
		raise frappe.QueryDeadlockError
	_require()


def _retry(action):
	for attempt in range(3):
		try:
			return action()
		except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
			request = getattr(frappe.local, "request", None)
			if attempt == 2 or not request or request.method != "POST" or frappe.form_dict.get("cmd") not in {
				"crm.api.call_work.save_note", "crm.api.call_work.save_task", "crm.api.call_drafts.save_draft", "crm.api.call_drafts.link_call", "crm.api.call_followups.save_outcome", "crm.api.call_followups.complete_task", "crm.call_analysis.workspace.confirm_task", "crm.call_analysis.workspace.start", "crm.call_analysis.api.start_analysis", "crm.call_analysis.analytics.link_callback"}:
				raise
			frappe.db.rollback()
			frappe.clear_cache(user=frappe.session.user)
			frappe.local.user_perms = None


def _note(name, lock=False, write=False):
	doc = frappe.get_doc("FCRM Note", name, for_update=lock)
	doc.check_permission("write" if write else "read")
	if doc.owner != frappe.session.user:
		frappe.throw(_("This note is not available in your call workspace."), frappe.PermissionError)
	kind = next((key for key, (dt, _) in CONTEXTS.items() if dt == doc.reference_doctype), None)
	_context(kind, doc.reference_docname, current=lock)
	return doc


def _plain_text(content):
	soup = BeautifulSoup(content or "", "html.parser")
	for line_break in soup.find_all("br"):
		line_break.replace_with("\n")
	for block in soup.find_all(["p", "div", "li"]):
		block.append("\n")
	return soup.get_text().strip()


def _project_note(doc):
	return {"name": doc.name, "title": doc.title, "text": _plain_text(doc.content),
		"modified": str(doc.modified), "reference_doctype": doc.reference_doctype, "reference_docname": doc.reference_docname}


@frappe.whitelist(methods=["POST"])
def save_note(values, mutation_id, expected_viewer, name=None, expected_modified=None):
	return _retry(lambda: _save_note(values, mutation_id, expected_viewer, name, expected_modified))


def _save_note(values, mutation_id, expected_viewer, name, expected_modified):
	_require(expected_viewer)
	values = frappe.parse_json(values) if isinstance(values, str) else values
	if (not isinstance(values, dict) or set(values) != {"title", "text", "context_kind", "context_name"}
		or not all(isinstance(value, str) for value in values.values()) or not isinstance(mutation_id, str)
		or not 16 <= len(mutation_id) <= 100):
		frappe.throw(_("Invalid call note changes."))
	if not values["title"].strip() or len(values["title"]) > 140 or not values["text"].strip() or len(values["text"]) > 100000:
		frappe.throw(_("Enter a note title and text."))
	request_hash = sha256(frappe.as_json([name, expected_modified, values]).encode()).hexdigest()
	operation = sha256(f"{frappe.session.user}\0{mutation_id}".encode()).hexdigest()
	_lock_author()
	previous = frappe.db.get_value("CRM Note Operation", operation, ["request_hash", "note"], as_dict=True, for_update=True, order_by=None)
	if previous:
		if previous.request_hash != request_hash:
			frappe.throw(_("This request was already used for different changes."))
		if not frappe.db.get_value("CRM Note Operation", operation, "name", order_by=None):
			raise frappe.QueryDeadlockError
		doc = _note(previous.note, lock=True)
		context = _context(values["context_kind"], values["context_name"], current=True)
		if doc.reference_doctype != context["doctype"] or doc.reference_docname != context["name"]:
			frappe.throw(_("Saved call work cannot be moved to another customer."), frappe.PermissionError)
		return {"note": _project_note(doc), "replayed": True}
	context = _context(values["context_kind"], values["context_name"], current=True)
	doc = _note(name, lock=True, write=True) if name else frappe.get_doc({"doctype": "FCRM Note"})
	if name:
		if doc.reference_doctype != context["doctype"] or doc.reference_docname != context["name"]:
			frappe.throw(_("Saved call work cannot be moved to another customer."))
		if not expected_modified or get_datetime(doc.modified) != get_datetime(expected_modified):
			frappe.throw(_("This note changed in another window. Your draft is kept."), frappe.TimestampMismatchError)
	else:
		doc.check_permission("create")
		doc.reference_doctype, doc.reference_docname = context["doctype"], context["name"]
	doc.title = values["title"].strip()
	doc.content = "<p>" + escape_html(values["text"].strip()).replace("\n", "<br>") + "</p>"
	doc.save()
	from crm.fcrm.doctype.crm_note_operation.crm_note_operation import internal_write
	with internal_write():
		frappe.get_doc({"doctype": "CRM Note Operation", "name": operation, "user": frappe.session.user,
			"request_hash": request_hash, "note": doc.name}).insert(ignore_permissions=True)
	return {"note": _project_note(doc), "replayed": False}


@frappe.whitelist(methods=["POST"])
def save_task(values, mutation_id, expected_viewer, name=None, expected_modified=None):
	def save():
		_require(expected_viewer)
		data = frappe.parse_json(values) if isinstance(values, str) else values
		if not isinstance(data, dict):
			frappe.throw(_("Invalid CRM task changes."))
		data = dict(data)
		kind, context_name = data.get("context_kind"), data.get("context_name")
		_lock_author()
		context = _context(kind, context_name, current=True)
		if name:
			doc = celio_tasks._task(name, lock=True)
			if doc.owner != frappe.session.user or doc.reference_doctype != context["doctype"] or doc.reference_docname != context["name"]:
				frappe.throw(_("Saved call work cannot be moved to another customer."), frappe.PermissionError)
			data.pop("context_kind", None)
			data.pop("context_name", None)
		if isinstance(data.get("description"), str):
			data["description"] = "<p>" + escape_html(data["description"].strip()).replace("\n", "<br>") + "</p>" if data["description"].strip() else ""
		result = celio_tasks._save_task(data, mutation_id, name, expected_modified, expected_viewer)
		result["task"]["description_text"] = _plain_text(result["task"]["description"])
		return result
	return _retry(save)


@frappe.whitelist()
def get_item(kind, name, context_kind, context_name):
	_require()
	context = _context(context_kind, context_name)
	if kind == "note":
		doc = _note(name)
		result = _project_note(doc)
	elif kind == "task":
		doc = celio_tasks._task(name)
		if doc.owner != frappe.session.user:
			frappe.throw(_("This task is not available in your call workspace."), frappe.PermissionError)
		result = celio_tasks.project(doc)
		result["description_text"] = _plain_text(doc.description)
	else:
		frappe.throw(_("Invalid call work item."))
	if doc.reference_doctype != context["doctype"] or doc.reference_docname != context["name"]:
		frappe.throw(_("Saved call work cannot be moved to another customer."), frappe.PermissionError)
	return {"viewer": frappe.session.user, kind: result}
