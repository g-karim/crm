"""Work from the native CRM call, outcome and task records used by analytics."""

from datetime import timedelta, timezone
from hashlib import sha256
import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from crm.analytics.call_reporting import (
	CALL, MISSED, OUTCOME, OUTCOMES, REFERENCES, TERMINAL, _context_scope, _employee,
	_filters, _has_context, _make_report, read_named,
)
from crm.analytics.engine import timestamp
from crm.analytics.sales_plans import plan_scope
from crm.analytics.service import coherent_read, exact_json
from crm.api import celio_tasks
from crm.call_work_storage import internal_write
from crm.integrations.exolve.api import _lock_call
from crm.utils import sales_user_only

CALL_READ = ["name", "type", "status", "caller", "receiver", "reference_doctype",
	"reference_docname", "start_time", "creation", "from", "to"]
CLOSED_TASKS = {"Done", "Canceled", "Cancelled", "Completed"}


def _unavailable():
	frappe.throw(_("This call is unavailable with your current access."), frappe.PermissionError)


def _assert_context(kind, name, *, lock=False):
	if not name and kind in ("", None, "CRM Lead"):
		return
	if not name or kind not in REFERENCES or not frappe.has_permission(kind, "read"):
		_unavailable()
	if not frappe.db.get_value(kind, name, "name", order_by=None, for_update=lock):
		_unavailable()
	doc = frappe.get_doc(kind, name, for_update=lock)
	doc.check_permission("read")


def _call(name, *, write=False, lock=False):
	if not name or not frappe.has_permission(CALL, "read"):
		_unavailable()
	if not frappe.db.get_value(CALL, name, "name", order_by=None, for_update=lock):
		_unavailable()
	doc = frappe.get_doc(CALL, name, for_update=lock)
	doc.check_permission("write" if write else "read")
	_, owners = plan_scope()
	if owners is not None and _employee(doc) not in owners:
		_unavailable()
	_assert_context(doc.reference_doctype, doc.reference_docname, lock=lock)
	return doc


def _review(name, *, lock=False):
	if not frappe.db.table_exists(OUTCOME):
		frappe.throw(_("Call outcomes are not installed on this site."), frappe.ValidationError)
	if frappe.db.get_value(OUTCOME, name, "name", order_by=None, for_update=lock):
		doc = frappe.get_doc(OUTCOME, name, for_update=lock)
		_assert_context(doc.reference_doctype, doc.reference_docname, lock=lock)
		return doc
	return None


def _zone():
	return frappe.db.get_single_value("System Settings", "time_zone") or "UTC"


def _number(value):
	if not isinstance(value, str) or not re.fullmatch(r"[+0-9(). -]{6,30}", value):
		return ""
	digits = re.sub(r"\D", "", value)
	if len(digits) == 11 and digits.startswith("8"):
		digits = "7" + digits[1:]
	return digits if 7 <= len(digits) <= 15 else ""


def _at(row, zone):
	return timestamp(row.get("start_time") or row.get("creation"), zone)


def _eligible_reply(incoming, outgoing, zone):
	received, called = _at(incoming, zone), _at(outgoing, zone)
	peer = _number(incoming.get("from"))
	return bool(
		incoming.get("type") == "Incoming" and incoming.get("status") in MISSED
		and outgoing.get("type") == "Outgoing" and outgoing.get("status") in TERMINAL
		and peer and peer == _number(outgoing.get("to"))
		and received and called and received.astimezone(timezone.utc) < called.astimezone(timezone.utc)
		<= timestamp(now_datetime(), zone).astimezone(timezone.utc)
	)


def _peer_readable(call, field):
	return call.has_permlevel_access_to(field) and not any(
		df.fieldname == field for df in call.meta.get_masked_fields())


def _candidates(call, zone):
	received = _at(call, zone)
	_, owners = plan_scope()
	# Use standard persisted phone representations. A candidate is never evidence
	# by itself. Recheck number, access and ordering under locks when confirming.
	peer = _number(call.get("from")) if _peer_readable(call, "from") else ""
	if not received or not peer:
		return []
	begin = received.replace(tzinfo=None)
	end = min(received + timedelta(days=30), timestamp(now_datetime(), zone)).replace(tzinfo=None)
	representations = {call.get("from"), peer, "+" + peer}
	if len(peer) == 11 and peer.startswith("7"):
		representations.add("8" + peer[1:])
	rows = frappe.get_list(CALL, filters={"type": "Outgoing", "to": ["in", sorted(representations)],
		"start_time": ["between", [begin, end]], "status": ["in", sorted(TERMINAL)]},
		fields=["name"], order_by="start_time asc, name asc", limit_page_length=120)
	allowed = list(read_named(CALL, CALL_READ, (row.name for row in rows)))
	context = _context_scope(allowed)
	candidates = []
	for item in allowed:
		if (owners is not None and _employee(item) not in owners) or not _has_context(item, context):
			continue
		if _eligible_reply(call, item, zone):
			agent = _employee(item)
			candidates.append({"name": item["name"], "at": _at(item, zone), "status": item["status"],
				"employee": frappe.get_cached_value("User", agent, "full_name") if agent else ""})
	return sorted(candidates, key=lambda row: (row["at"], row["name"]))[:20]


def _workspace(call, review):
	zone = _zone()
	result = {
		"viewer": frappe.session.user,
		"revision": (review.revision or 0) if review else 0,
		"can_manage": call.status in TERMINAL and frappe.has_permission(CALL, "write", doc=call),
		"outcome": review.outcome if review else "",
		"can_confirm": call.type == "Incoming" and call.status in MISSED,
		"can_schedule": call.reference_doctype in {value[0] for value in celio_tasks.CONTEXTS.values()}
			and bool(call.reference_docname) and frappe.has_permission("CRM Task", "create"),
		"timezone": zone,
		"candidates": [],
		"linked": None,
		"task": None,
	}
	if review and review.callback_task:
		try:
			task = celio_tasks._task(review.callback_task)
			result["task"] = {"name": str(task.name), "title": task.title, "status": task.status}
		except (frappe.PermissionError, frappe.DoesNotExistError):
			pass
	if result["outcome"] == "Callback" and result["can_confirm"]:
		if review.callback_call:
			try:
				reply = _call(review.callback_call)
				result["linked"] = {"name": reply.name, "at": _at(reply, zone), "status": reply.status}
			except (frappe.PermissionError, frappe.DoesNotExistError):
				result["linked"] = {"unavailable": True}
		if result["can_manage"]:
			result["candidates"] = _candidates(call, zone)
	return exact_json(result)


def _write_guard(viewer):
	if viewer != frappe.session.user:
		_unavailable()
	locked = frappe.db.get_value("User", viewer, ["enabled", "modified"], as_dict=True, for_update=True)
	if locked != frappe.db.get_value("User", viewer, ["enabled", "modified"], as_dict=True):
		raise frappe.QueryDeadlockError
	if not locked or not locked.enabled:
		_unavailable()


def _ensure_version(review, revision):
	if str((review.revision or 0) if review else 0) != str(revision):
		frappe.throw(_("The call outcome changed. Reload before saving."), frappe.TimestampMismatchError)


def _task_for_review(call, due_at, mutation_id, viewer):
	kind = next((key for key, (doctype, _label) in celio_tasks.CONTEXTS.items()
		if doctype == call.reference_doctype), None)
	if not kind or not call.reference_docname:
		frappe.throw(_("Connect the call to a lead or deal before scheduling a callback."), frappe.ValidationError)
	zone = _zone()
	due = timestamp(due_at, zone)
	if not due or due <= timestamp(now_datetime(), zone):
		frappe.throw(_("Choose a future callback time."), frappe.ValidationError)
	operation = sha256(f"call-journal-task\0{call.name}\0{mutation_id}".encode()).hexdigest()
	result = celio_tasks._save_task({
		"context_kind": kind, "context_name": call.reference_docname, "title": _("Callback"),
		"status": "Todo", "priority": "Medium", "assigned_to": _employee(call) or viewer,
		"due_date": str(due.replace(tzinfo=None)),
	}, operation, None, None, viewer)
	return result["task"]["name"]


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_workspace(name: str):
	return _workspace(_call(name), _review(name))


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_scoped_call_log(name: str):
	_call(name)
	from crm.fcrm.doctype.crm_call_log.crm_call_log import get_call_log

	return get_call_log(name)


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_journal(filters: dict | str | None = None, start: int = 0, limit: int = 25):
	report, rows, _revision = _make_report(_filters(filters))
	start, limit = max(0, start), min(100, max(1, limit))
	labels = {row["key"]: row["label"] for row in report["groups"]["employees"]}
	return exact_json({"total": len(rows), "period": report["period"], "rows": [
		{**row, "employee_label": labels.get(row["employee"], row["employee"])}
		for row in rows[start:start + limit]
	]})


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_outcome(name: str, outcome: str, expected_revision: int, mutation_id: str, expected_viewer: str,
	due_at: str | None = None):
	if outcome not in OUTCOMES or not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", mutation_id or ""):
		frappe.throw(_("Choose a valid call outcome."), frappe.ValidationError)
	if due_at and (outcome != "Callback" or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", due_at)):
		frappe.throw(_("Choose a valid callback date and time."), frappe.ValidationError)
	_write_guard(expected_viewer)
	_lock_call(name)
	call = _call(name, write=True, lock=True)
	review = _review(name, lock=True)
	if call.status not in TERMINAL:
		frappe.throw(_("Finish the call before saving its outcome."), frappe.ValidationError)
	payload = sha256(frappe.as_json([name, outcome, expected_revision, due_at]).encode()).hexdigest()
	if review and review.last_mutation == mutation_id:
		if review.last_hash != payload or review.processed_by != frappe.session.user:
			frappe.throw(_("This request was already used for different changes."), frappe.ValidationError)
		return _workspace(call, review)
	_ensure_version(review, expected_revision)
	if review and review.outcome == outcome and not due_at:
		return _workspace(call, review)
	if review and review.callback_task:
		task = celio_tasks._task(review.callback_task, lock=True)
		if task.status not in CLOSED_TASKS:
			frappe.throw(_("Complete or cancel the existing callback task before making this change."), frappe.ValidationError)
	if not review:
		review = frappe.get_doc({"doctype": OUTCOME, "name": name, "__islocal": 1, "call_log": name})
	if review.outcome != outcome:
		review.update({"callback_call": None, "callback_linked_by": None, "callback_linked_at": None, "callback_task": None})
	if due_at:
		task_name = _task_for_review(call, due_at, mutation_id, expected_viewer)
		review.callback_task = task_name
		if not call.has_link("CRM Task", task_name):
			call.link_with_reference_doc("CRM Task", task_name)
			# An outcome edit is independent of automatic transcription.
			old_flag = frappe.flags.in_exolve_sync
			try:
				frappe.flags.in_exolve_sync = True
				call.save()
			finally:
				frappe.flags.in_exolve_sync = old_flag
	review.update({
		"outcome": outcome, "reference_doctype": call.reference_doctype if call.reference_docname else None,
		"reference_docname": call.reference_docname, "processed_by": frappe.session.user, "processed_at": now_datetime(),
		"last_mutation": mutation_id, "last_hash": payload, "revision": (review.revision or 0) + 1,
	})
	with internal_write():
		review.save(ignore_permissions=True)
	return _workspace(call, review)


@frappe.whitelist(methods=["POST"])
@sales_user_only
def confirm_callback(name: str, outgoing: str, expected_revision: int, expected_viewer: str):
	_write_guard(expected_viewer)
	for identity in sorted({name, outgoing}):
		_lock_call(identity)
	call = _call(name, write=True, lock=True)
	reply = _call(outgoing, lock=True)
	review = _review(name, lock=True)
	if (not review or review.outcome != "Callback" or not _peer_readable(call, "from")
		or not _peer_readable(reply, "to") or not _eligible_reply(call, reply, _zone())):
		frappe.throw(_("Choose a permitted later outgoing call to the same number."), frappe.ValidationError)
	assert review is not None
	if review.callback_call == outgoing:
		return _workspace(call, review)
	_ensure_version(review, expected_revision)
	if frappe.db.get_value(OUTCOME, {"callback_call": outgoing, "name": ["!=", name]}, "name", for_update=True):
		frappe.throw(_("This outgoing attempt is already linked to a missed call."), frappe.ValidationError)
	review.update({
		"callback_call": outgoing, "callback_linked_by": expected_viewer,
		"callback_linked_at": now_datetime(), "revision": (review.revision or 0) + 1,
	})
	with internal_write():
		review.save(ignore_permissions=True)
	return _workspace(call, review)
