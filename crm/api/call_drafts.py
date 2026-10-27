"""Personal, revisioned conversation drafts and explicit verified-call linking."""

from hashlib import sha256
from uuid import UUID

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import get_datetime

from crm.api import call_work
from crm.call_work_storage import internal_write

DOCTYPE = "CRM Call Work"


def _id(work_id):
	try:
		UUID(work_id)
	except (ValueError, TypeError, AttributeError):
		frappe.throw(_("Invalid conversation draft."))
	return sha256(f"{frappe.session.user}\0{work_id}".encode()).hexdigest()


def _doc(work_id, lock=False):
	doc = frappe.get_doc(DOCTYPE, _id(work_id), for_update=lock)
	if doc.user != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


def _string(value, limit):
	if not isinstance(value, str) or len(value) > limit:
		frappe.throw(_("Invalid conversation draft."))
	return value


def _item(raw, kind, context):
	if not isinstance(raw, dict) or raw.get("kind") != kind:
		frappe.throw(_("Invalid conversation draft."))
	_id(raw.get("key"))
	values = raw.get("values")
	fields = (
		{"title": 140, "text": 100000}
		if kind == "note"
		else {
			"title": 140,
			"description": 30000,
			"assigned_to": 140,
			"due_date": 40,
			"status": 40,
			"priority": 40,
		}
	)
	if not isinstance(values, dict) or set(values) != set(fields):
		frappe.throw(_("Invalid conversation draft."))
	values = {field: _string(values[field], size) for field, size in fields.items()}
	name, modified = raw.get("name"), raw.get("modified")
	if name:
		if not context:
			frappe.throw(_("Choose a lead or deal before saving."))
		# Native ownership, customer permissions and immutable context are checked again.
		call_work.get_item(kind, str(name), context["kind"], context["name"])
		_string(modified, 60)
	pending = raw.get("pending")
	if pending:
		if (
			not isinstance(pending, dict)
			or not context
			or pending.get("expected_viewer") != frappe.session.user
		):
			frappe.throw(_("Invalid conversation draft."))
		_id(pending.get("mutation_id"))
		pvalues = pending.get("values")
		if not isinstance(pvalues, dict) or set(pvalues) != set(fields) | {"context_kind", "context_name"}:
			frappe.throw(_("Invalid conversation draft."))
		if (pvalues["context_kind"], str(pvalues["context_name"])) != (context["kind"], context["name"]):
			frappe.throw(_("Invalid conversation draft."))
		for field, size in fields.items():
			_string(pvalues[field], size)
		if pending.get("name") and str(pending["name"]) != str(name):
			frappe.throw(_("Invalid conversation draft."))
		pending = {
			key: pending.get(key)
			for key in ("name", "expected_modified", "expected_viewer", "mutation_id", "values")
		}
	backup = raw.get("backup")
	if backup is not None:
		if not isinstance(backup, dict) or set(backup) != set(fields):
			frappe.throw(_("Invalid conversation draft."))
		backup = {field: _string(backup[field], size) for field, size in fields.items()}
	return {
		"key": raw["key"],
		"kind": kind,
		"values": values,
		"name": str(name) if name else None,
		"modified": modified or None,
		"snapshot": _string(raw.get("snapshot"), 150000),
		"pending": pending,
		"conflict": bool(raw.get("conflict")),
		"backup": backup,
	}


def _snapshot(raw):
	if isinstance(raw, str):
		if len(raw) > 1200000:
			frappe.throw(_("Conversation draft is too large."))
		raw = frappe.parse_json(raw)
	if not isinstance(raw, dict) or len(frappe.as_json(raw)) > 1200000:
		frappe.throw(_("Invalid conversation draft."))
	_id(raw.get("id"))
	context = raw.get("context")
	if context:
		if not isinstance(context, dict):
			frappe.throw(_("Invalid conversation draft."))
		context = call_work._context(context.get("kind"), str(context.get("name")))
	context = {"kind": context["kind"], "name": context["name"]} if context else None
	tasks = raw.get("tasks")
	if not isinstance(tasks, list) or len(tasks) > 30:
		frappe.throw(_("Invalid conversation draft."))
	result = {
		"id": raw["id"],
		"number": _string(raw.get("number"), 100),
		"created": _string(raw.get("created"), 60),
		"started": bool(raw.get("started")),
		"ended": bool(raw.get("ended")),
		"incoming": bool(raw.get("incoming")),
		"context": context,
		"note": _item(raw.get("note"), "note", context),
		"tasks": [_item(item, "task", context) for item in tasks],
	}
	try:
		get_datetime(result["created"])
	except (ValueError, TypeError):
		frappe.throw(_("Invalid conversation draft."))
	if len({item["key"] for item in [result["note"], *result["tasks"]]}) != len(tasks) + 1:
		frappe.throw(_("Invalid conversation draft."))
	return result


def _project(doc):
	data = frappe.parse_json(doc.data)
	# Never expose a now-private customer, its titles or saved records through an old draft.
	if data["context"]:
		data["context"] = call_work._context(data["context"]["kind"], data["context"]["name"])
	latest = {}
	for item in [data["note"], *data["tasks"]]:
		if item.get("name"):
			latest[item["key"]] = call_work.get_item(
				item["kind"], item["name"], data["context"]["kind"], data["context"]["name"]
			)[item["kind"]]
	return {
		"snapshot": data,
		"latest": latest,
		"revision": doc.revision,
		"modified": str(doc.modified),
		"call_log": doc.call_log or None,
	}


@frappe.whitelist(methods=["POST"])
def save_draft(snapshot, expected_revision, mutation_id, expected_viewer):
	return call_work._retry(lambda: _save_draft(snapshot, expected_revision, mutation_id, expected_viewer))


def _save_draft(snapshot, expected_revision, mutation_id, expected_viewer):
	call_work._require(expected_viewer)
	data = _snapshot(snapshot)
	name = _id(data["id"])
	_id(mutation_id)
	payload = frappe.as_json(data)
	digest = sha256(payload.encode()).hexdigest()
	call_work._lock_author()
	if data["context"]:
		call_work._context(data["context"]["kind"], data["context"]["name"], current=True)
	exists = frappe.db.get_value(DOCTYPE, name, "name", for_update=True, order_by=None)
	doc = (
		_doc(data["id"], lock=True)
		if exists
		else frappe.get_doc(
			{"doctype": DOCTYPE, "name": name, "user": frappe.session.user, "revision": 0, "__islocal": 1}
		)
	)
	if doc.last_mutation == mutation_id:
		if doc.last_hash != digest:
			frappe.throw(_("This request was already used for different changes."))
		return {
			"viewer": frappe.session.user,
			"revision": doc.revision,
			"modified": str(doc.modified),
			"replayed": True,
		}
	if str(doc.revision or 0) != str(expected_revision):
		frappe.throw(_("This conversation draft changed in another window."), frappe.TimestampMismatchError)
	old = frappe.parse_json(doc.data) if doc.data else None
	if (
		old
		and old["started"]
		and (old["number"] != data["number"] or old["incoming"] != data["incoming"] or not data["started"])
	):
		frappe.throw(_("A started conversation keeps its original call details."))
	if old and _context_locked(old) and old["context"] != data["context"]:
		frappe.throw(_("Saved call work cannot be moved to another customer."), frappe.PermissionError)
	doc.data = payload
	doc.revision = (doc.revision or 0) + 1
	doc.last_mutation = mutation_id
	doc.last_hash = digest
	with internal_write():
		doc.save(ignore_permissions=True)
	if doc.call_log:
		_attach_materials(doc, data)
	return {
		"viewer": frappe.session.user,
		"revision": doc.revision,
		"modified": str(doc.modified),
		"replayed": False,
	}


def _context_locked(data):
	return any(item.get("name") or item.get("pending") for item in [data["note"], *data["tasks"]])


@frappe.whitelist()
def list_drafts(offset=0):
	call_work._require()
	rows = frappe.get_all(
		DOCTYPE,
		filters={"user": frappe.session.user},
		fields=["name"],
		order_by="modified desc,name desc",
		limit_start=max(0, frappe.utils.cint(offset)),
		limit_page_length=31,
	)
	result = []
	for row in rows[:30]:
		try:
			result.append(_project(frappe.get_doc(DOCTYPE, row.name)))
		except (frappe.PermissionError, frappe.DoesNotExistError):
			continue
	return {
		"viewer": frappe.session.user,
		"drafts": result,
		"has_more": len(rows) > 30,
		"next_offset": max(0, frappe.utils.cint(offset)) + 30,
	}


@frappe.whitelist()
def get_draft(work_id=None, call_log=None):
	call_work._require()
	if call_log:
		from crm.api.telephony import get_call

		get_call(call_log)
		name = frappe.db.get_value(DOCTYPE, {"user": frappe.session.user, "call_log": call_log}, "name")
		if not name:
			return {"viewer": frappe.session.user, "draft": None}
		doc = frappe.get_doc(DOCTYPE, name)
	else:
		doc = _doc(work_id)
	return {"viewer": frappe.session.user, "draft": _project(doc)}


def _owned_call(name):
	from crm.api.telephony import get_call

	get_call(name)
	doc = frappe.get_doc("CRM Call Log", name)
	participant = doc.receiver if doc.type == "Incoming" else doc.caller
	if doc.telephony_medium != "Exolve" or participant != frappe.session.user:
		frappe.throw(_("Choose one of your Exolve calls."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def call_candidates(work_id):
	call_work._require()
	doc = _doc(work_id)
	data = frappe.parse_json(doc.data)
	from crm.api.telephony import _base_query, _rows
	from crm.integrations.exolve.utils import normalize_phone

	try:
		number = normalize_phone(data["number"])
	except ValueError:
		return {"viewer": frappe.session.user, "calls": []}
	t = frappe.qb.DocType("CRM Call Log")
	query = _base_query().where(
		(t.telephony_medium == "Exolve")
		& (
			((t.type == "Outgoing") & (t.caller == frappe.session.user) & (t.to == number))
			| ((t.type == "Incoming") & (t.receiver == frappe.session.user) & (t["from"] == number))
		)
	)
	if data["started"]:
		query = query.where(t.type == ("Incoming" if data["incoming"] else "Outgoing"))
	rows = query.orderby(t.start_time, order=Order.desc).limit(50).run(as_dict=True)
	return {"viewer": frappe.session.user, "calls": _rows(rows)}


@frappe.whitelist(methods=["POST"])
def link_call(work_id, call_log, expected_revision, expected_viewer):
	return call_work._retry(lambda: _link_call(work_id, call_log, expected_revision, expected_viewer))


def _link_call(work_id, call_log, expected_revision, expected_viewer):
	call_work._require(expected_viewer)
	call_work._lock_author()
	doc = _doc(work_id, lock=True)
	if str(doc.revision) != str(expected_revision):
		frappe.throw(_("This conversation draft changed in another window."), frappe.TimestampMismatchError)
	_owned_call(call_log)
	from crm.integrations.exolve.api import _lock_call

	_lock_call(call_log)
	if doc.call_log and doc.call_log != call_log:
		frappe.throw(_("This conversation already has a linked call."))
	other = frappe.db.get_value(DOCTYPE, {"call_log": call_log}, "name", for_update=True, order_by=None)
	if other and other != doc.name:
		frappe.throw(_("This call is already linked to another conversation."))
	data = _project(doc)["snapshot"]
	from crm.integrations.exolve.utils import normalize_phone

	call_doc = _owned_call(call_log)
	if data["started"] and call_doc.type != ("Incoming" if data["incoming"] else "Outgoing"):
		frappe.throw(_("The selected call has a different direction."))
	try:
		if normalize_phone(data["number"]) != normalize_phone(
			call_doc.to if call_doc.type == "Outgoing" else call_doc.get("from")
		):
			raise ValueError
	except ValueError:
		frappe.throw(_("The selected call has a different customer number."))
	doc.call_log = call_log
	with internal_write():
		doc.save(ignore_permissions=True)
	_attach_materials(doc, data)
	return {"viewer": frappe.session.user, "draft": _project(doc)}


def _attach_materials(work, data):
	call_doc = _owned_call(work.call_log)
	from crm.integrations.exolve.api import _lock_call

	_lock_call(call_doc.name)
	call_doc = frappe.get_doc("CRM Call Log", call_doc.name, for_update=True)
	changed = False
	for item in [data["note"], *data["tasks"]]:
		if not item.get("name"):
			continue
		call_work.get_item(item["kind"], item["name"], data["context"]["kind"], data["context"]["name"])
		doctype = "FCRM Note" if item["kind"] == "note" else "CRM Task"
		if not call_doc.has_link(doctype, item["name"]):
			call_doc.link_with_reference_doc(doctype, item["name"])
			changed = True
	if changed:
		# Relationship update only; no AI or provider-state mutation.
		flag = frappe.flags.in_exolve_sync
		frappe.flags.in_exolve_sync = True
		try:
			call_doc.save(ignore_permissions=True)
		finally:
			frappe.flags.in_exolve_sync = flag
