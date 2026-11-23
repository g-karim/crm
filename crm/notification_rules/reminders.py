"""Minute-based task reminders; native history is the durable per-schedule dedup ledger."""

import json
from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import cint, get_datetime, get_system_timezone, now_datetime

EVENTS = {"task_due_soon", "task_overdue"}
OFFSETS = (15, 60, 1440)
CLOSED = {"Done", "Canceled"}
GRACE_MINUTES = 15
PAGE_SIZE = 200


def generation(doc, method=None):
	"""Read-only field: clients cannot choose a schedule's identity."""
	previous = doc.get_doc_before_save()
	if not previous:
		doc.exp_reminder_epoch = 1
		doc.exp_reminder_activated_at = now_datetime()
		return
	changed = any(
		str(doc.get(key) or "") != str(previous.get(key) or "")
		for key in ("assigned_to", "reference_doctype", "reference_docname")
	)
	changed = changed or (
		(get_datetime(doc.due_date) if doc.due_date else None)
		!= (get_datetime(previous.due_date) if previous.due_date else None)
	)
	changed = changed or ((doc.status in CLOSED) != (previous.status in CLOSED))
	doc.exp_reminder_epoch = cint(previous.get("exp_reminder_epoch")) + int(changed)
	doc.exp_reminder_activated_at = now_datetime() if changed else previous.get("exp_reminder_activated_at")


def enabled():
	from crm.notification_rules.events import ready

	return bool(ready() and cint(frappe.conf.get("exp_crm_reminders_enabled")))


def clock():
	from exp_theme.notifications.access import event_time

	return event_time(now_datetime())


def system_time(value):
	return value.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def scheduled_at(task, event, minutes=0):
	from exp_theme.notifications.access import event_time

	return event_time(task.due_date) - timedelta(minutes=minutes if event == "task_due_soon" else 0)


def in_window(task, event, minutes, at):
	from exp_theme.notifications.access import event_time

	if not task.due_date or not task.assigned_to or task.status in CLOSED:
		return False
	fire = scheduled_at(task, event, minutes)
	if fire < event_time(task.get("exp_reminder_activated_at") or task.creation):
		return False
	if not fire <= at < fire + timedelta(minutes=GRACE_MINUTES):
		return False
	return event != "task_due_soon" or at < scheduled_at(task, "task_overdue")


def facts_for(task, event, minutes):
	from crm.notification_rules.engine import snapshot_document

	return {
		**snapshot_document(
			task, event, actor=None, occurred_at=system_time(scheduled_at(task, event, minutes))
		),
		"task_due_at": str(task.due_date),
		"task_epoch": cint(task.get("exp_reminder_epoch")),
		"reminder_minutes": minutes,
	}


def refreshed(facts, user, lock=False):
	"""Cancel outdated queues and re-evaluate the current task/parent conditions."""
	if not enabled() or not facts.get("task_id"):
		return None
	row = frappe.db.get_value("CRM Task", facts["task_id"], "*", as_dict=True, for_update=lock)
	if not row or row.assigned_to != user or str(row.due_date) != facts.get("task_due_at"):
		return None
	if cint(row.exp_reminder_epoch) != facts.get("task_epoch"):
		return None
	if not in_window(row, facts["event"], facts["reminder_minutes"], clock()):
		return None
	from crm.notification_rules.access import readable

	if not readable("CRM Task", row.name, user):
		return None
	row.doctype = "CRM Task"
	current = facts_for(row, facts["event"], facts["reminder_minutes"])
	if (current["object"], current["record_id"]) != (facts["object"], facts["record_id"]):
		return None
	return {**current, "occurred_at": facts["occurred_at"], "policy_epoch": facts.get("policy_epoch")}


def _bounds(event, minutes, at):
	# Query a superset if a UTC window straddles a timezone offset change.
	end = at + timedelta(minutes=minutes if event == "task_due_soon" else 0)
	start = end - timedelta(minutes=GRACE_MINUTES)
	zone = ZoneInfo(get_system_timezone())
	shift = abs(end.astimezone(zone).utcoffset() - start.astimezone(zone).utcoffset())
	left, right = sorted([system_time(start), system_time(end)])
	return left - shift, right + shift


def _phases():
	from exp_theme.notifications import policy

	result = set()
	for row in frappe.get_all(policy.DOCTYPE, filters={"source": "crm"}, fields=["configuration"]):
		values = policy.configuration(row)
		if values.get("mode") == "legacy":
			continue
		for rule in values.get("rules", []):
			if rule["enabled"] and rule["event"] in EVENTS:
				result.add((rule["event"], rule.get("reminder_minutes", 0)))
	return sorted(result)


def _job(method):
	@wraps(method)
	def wrapped(*args, **kwargs):
		if "exp_theme" not in frappe.get_installed_apps():
			return method(*args, **kwargs)
		from exp_theme.notifications.transactions import execute

		return execute(method, args, kwargs)

	return wrapped


@_job
def run():
	"""Trusted scheduler method; no caller-selected recipient and no HTTP whitelist."""
	if not enabled():
		return {"published": 0}
	at = clock()
	count = 0
	for event, minutes in _phases():
		last = 0
		while True:
			rows = frappe.get_all(
				"CRM Task",
				filters={
					"name": [">", last],
					"due_date": ["between", _bounds(event, minutes, at)],
					"status": ["not in", sorted(CLOSED)],
					"assigned_to": ["is", "set"],
				},
				fields=["name"],
				order_by="name asc",
				limit_page_length=PAGE_SIZE,
			)
			if not rows:
				break
			for row in rows:
				count += int(_process(row.name, event, minutes, at))
			last = rows[-1].name
	return {"published": count}


def _process(name, event, minutes, at):
	from exp_theme.notifications.access import identity

	from crm.notification_rules import engine

	task = frappe.db.get_value("CRM Task", name, "*", as_dict=True, for_update=True)
	if not task or not in_window(task, event, minutes, at):
		return False
	user = task.assigned_to
	if not frappe.db.get_value("User", user, "enabled"):
		return False
	task.doctype = "CRM Task"
	event_id = "crm-task-reminder:" + identity(
		frappe.local.site, name, task.exp_reminder_epoch, task.due_date, user, event, minutes
	)
	if frappe.db.get_value("CRM Notification", identity(event_id, user), "name", for_update=True):
		return False
	facts = facts_for(task, event, minutes)
	result = engine.evaluate(facts, user, lock=True)
	if not any(result["channels"].values()):
		return False
	_publish(task, user, event_id, {**facts, "policy_epoch": result["epoch"]})
	return True


def _publish(task, user, event_id, facts):
	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user

	text = frappe._(
		"A task deadline is approaching." if facts["event"] == "task_due_soon" else "A task is overdue."
	)
	parent = task.reference_doctype in {"CRM Lead", "CRM Deal"} and task.reference_docname
	notify_user(
		{
			"owner": None,
			"assigned_to": user,
			"notification_type": "Reminder",
			"reference_doctype": "CRM Task",
			"reference_docname": task.name,
			"redirect_to_doctype": task.reference_doctype if parent else None,
			"redirect_to_docname": task.reference_docname if parent else None,
			"message": text,
			"notification_text": text,
			"event_at": facts["occurred_at"],
			"event_id": event_id,
			"exp_notification_snapshot": json.dumps(facts, sort_keys=True),
			"allow_self_notification": True,
		}
	)
