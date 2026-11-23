"""One-shot personal task reminders, explicitly independent of the task deadline."""

import json
from datetime import UTC, datetime, timedelta
from functools import wraps
from hashlib import sha256

import frappe
from frappe.utils import get_datetime

from crm.notification_rules.access import readable, require_record
from crm.notification_rules.reminders import CLOSED, GRACE_MINUTES, _job, clock, enabled, system_time

DOCTYPE = "CRM Personal Reminder"


def _rpc(method):
	@wraps(method)
	def wrapped(*args, **kwargs):
		from crm.notification_rules import mutation

		return mutation.rpc(method)(*args, **kwargs)

	return wrapped


def _iso(value):
	return get_datetime(value).replace(tzinfo=UTC).isoformat()


def _view(row):
	return {
		"id": row.name,
		"at": _iso(row.remind_at),
		"state": row.state,
		"revision": row.revision,
		"channels": json.loads(row.channels),
	}


@frappe.whitelist(methods=["GET"])
def list_reminders(task: str, expected_viewer: str):
	from crm.notification_rules.api import _state, viewer

	user = viewer(expected_viewer)
	require_record("CRM Task", task, user)
	rows = frappe.get_all(
		DOCTYPE,
		filters={"task": task, "user": user},
		fields=["*"],
		order_by="remind_at desc",
		limit_page_length=100,
	)
	state = _state(user)
	return {
		"viewer": user,
		"items": [_view(row) for row in rows],
		"available": enabled(),
		"effective_masters": state["effective_masters"],
		"masters": state["masters"],
	}


@frappe.whitelist(methods=["POST"])
@_rpc
def schedule(task: str, at: str, channels: dict, mutation_id: str, expected_viewer: str):
	from crm.notification_rules import schema
	from crm.notification_rules.api import viewer

	user = viewer(expected_viewer)
	require_record("CRM Task", task, user)
	schema.rule_id(mutation_id)
	request_channels = frappe.parse_json(channels)
	channels = schema.normalize_channels(request_channels)
	if (channels["one_push"] and not channels["one_message"]) or not (
		channels["crm_push"] or channels["one_message"] or channels["email"]
	):
		schema.invalid()
	try:
		if not isinstance(at, str) or len(at) > 40:
			raise ValueError
		instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
		if instant.tzinfo is None or instant.microsecond:
			raise ValueError
		instant = instant.astimezone(UTC)
	except (TypeError, ValueError, OverflowError):
		frappe.throw(frappe._("Choose a valid date and time with a timezone."))
	key = sha256(f"{frappe.local.site}\0{user}\0{mutation_id}".encode()).hexdigest()
	payload = json.dumps({"task": str(task), "at": instant.isoformat(), "channels": request_channels}, sort_keys=True)
	digest = sha256(payload.encode()).hexdigest()
	previous = frappe.db.get_value(DOCTYPE, key, "*", as_dict=True, for_update=True)
	if previous:
		if previous.user != user or previous.request_hash != digest:
			frappe.throw(frappe._("This request was already used with different values."))
		return {"viewer": user, "item": _view(previous), "replayed": True}
	if not clock() < instant <= clock() + timedelta(days=366):
		frappe.throw(frappe._("Choose a future time within one year."))
	if frappe.db.get_value("CRM Task", task, "status", for_update=True) in CLOSED:
		frappe.throw(frappe._("This task is already completed or cancelled."))
	if frappe.db.count(DOCTYPE, {"user": user, "state": "Scheduled"}) >= 100:
		frappe.throw(frappe._("The personal reminder limit is 100."))
	frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"user": user,
			"task": task,
			"remind_at": instant.replace(tzinfo=None),
			"channels": json.dumps(channels, sort_keys=True),
			"request_hash": digest,
			"state": "Scheduled",
			"revision": 1,
		}
	).insert(ignore_permissions=True, ignore_if_duplicate=True, set_name=key)
	stored = frappe.db.get_value(DOCTYPE, key, "*", as_dict=True, for_update=True)
	if stored.user != user or stored.request_hash != digest:
		frappe.throw(frappe._("This request was already used with different values."))
	return {"viewer": user, "item": _view(stored), "replayed": False}


@frappe.whitelist(methods=["POST"])
@_rpc
def cancel(reminder: str, expected_revision: int, expected_viewer: str):
	from crm.notification_rules.api import viewer

	user = viewer(expected_viewer)
	row = frappe.db.get_value(DOCTYPE, {"name": reminder, "user": user}, "*", as_dict=True, for_update=True)
	if not row:
		frappe.throw(frappe._("This reminder is not available."), frappe.PermissionError)
	if row.state == "Cancelled":
		return {"viewer": user, "item": _view(row)}
	if type(expected_revision) is not int or expected_revision != row.revision:
		frappe.throw(
			frappe._("This reminder changed. Reload before cancelling."), frappe.TimestampMismatchError
		)
	frappe.db.set_value(DOCTYPE, row.name, {"state": "Cancelled", "revision": row.revision + 1})
	return {"viewer": user, "item": _view(frappe.db.get_value(DOCTYPE, row.name, "*", as_dict=True))}


def _facts(row, task):
	from crm.notification_rules import engine

	# No due_date/assignee/generation dependency: this reminder belongs to its creator.
	return {
		**engine.snapshot_document(
			task,
			"task_reminder",
			actor=None,
			occurred_at=system_time(get_datetime(row.remind_at).replace(tzinfo=UTC)),
		),
		"personal_reminder_id": row.name,
		"personal_channels": json.loads(row.channels),
		"reminder_user": row.user,
	}


def refreshed(facts, user, lock=False):
	if not enabled():
		return None
	row = frappe.db.get_value(
		DOCTYPE, {"name": facts.get("personal_reminder_id"), "user": user}, "*", as_dict=True, for_update=lock
	)
	if not row or row.state != "Fired" or row.task != facts.get("task_id"):
		return None
	if (
		not get_datetime(row.remind_at).replace(tzinfo=UTC)
		<= clock()
		< get_datetime(row.remind_at).replace(tzinfo=UTC) + timedelta(minutes=GRACE_MINUTES)
	):
		return None
	if not readable("CRM Task", row.task, user):
		return None
	task = frappe.get_doc("CRM Task", row.task)
	if task.status in CLOSED:
		return None
	return {**_facts(row, task), "policy_epoch": facts.get("policy_epoch")}


@_job
def run():
	if not enabled():
		return {"published": 0}
	count, last = 0, ""
	while True:
		rows = frappe.get_all(
			DOCTYPE,
			filters={
				"state": "Scheduled",
				"remind_at": ["<=", clock().replace(tzinfo=None)],
				"name": [">", last],
			},
			pluck="name",
			order_by="name asc",
			limit_page_length=200,
		)
		if not rows:
			break
		for name in rows:
			count += int(_fire(name))
		last = rows[-1]
	return {"published": count}


def _fire(name):
	from exp_theme.notifications import policy

	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user
	from crm.notification_rules import engine

	row = frappe.db.get_value(DOCTYPE, name, "*", as_dict=True, for_update=True)
	if not row or row.state != "Scheduled":
		return False
	at = get_datetime(row.remind_at).replace(tzinfo=UTC)
	if clock() < at:
		return False
	state = "Expired" if clock() >= at + timedelta(minutes=GRACE_MINUTES) else "Cancelled"
	if (
		state != "Expired"
		and frappe.db.get_value("User", row.user, "enabled")
		and readable("CRM Task", row.task, row.user)
		and frappe.db.get_value("CRM Task", row.task, "status") not in CLOSED
	):
		task = frappe.get_doc("CRM Task", row.task)
		facts = {**_facts(row, task), "policy_epoch": policy.load(row.user, "crm").delivery_epoch}
		result = engine.evaluate(facts, row.user, expected_epoch=facts["policy_epoch"], lock=True)
		if any(result["channels"].values()):
			state = "Fired"
	frappe.db.set_value(DOCTYPE, row.name, {"state": state, "revision": row.revision + 1})
	if state != "Fired":
		return False
	notify_user(
		{
			"owner": None,
			"assigned_to": row.user,
			"notification_type": "Reminder",
			"reference_doctype": "CRM Task",
			"reference_docname": task.name,
			"redirect_to_doctype": task.reference_doctype
			if task.reference_doctype in {"CRM Lead", "CRM Deal"}
			else None,
			"redirect_to_docname": task.reference_docname
			if task.reference_doctype in {"CRM Lead", "CRM Deal"}
			else None,
			"message": frappe._("Your personal task reminder."),
			"notification_text": frappe._("Your personal task reminder."),
			"event_id": "crm-personal-reminder:" + row.name,
			"event_at": str(system_time(get_datetime(row.remind_at).replace(tzinfo=UTC))),
			"exp_notification_snapshot": json.dumps(facts, sort_keys=True),
			"allow_self_notification": True,
		}
	)
	return True
