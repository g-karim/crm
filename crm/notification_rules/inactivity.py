"""Indexed activity deadlines; new rules never backfill old, inactive records."""

import json
from datetime import timedelta

import frappe
from frappe.utils import cint, get_datetime

from crm.notification_rules.reminders import GRACE_MINUTES, _job, clock, enabled, system_time

KINDS = {"CRM Lead", "CRM Deal"}
FIELD = "exp_notification_activity_at"
EPOCH = "exp_notification_activity_epoch"


def available(doctype):
	return doctype in KINDS and frappe.db.has_column(doctype, FIELD) and frappe.db.has_column(doctype, EPOCH)


def generation(doc, method=None):
	if not available(doc.doctype):
		return
	previous = doc.get_doc_before_save()
	doc.set(FIELD, doc.modified)
	doc.set(EPOCH, cint(previous.get(EPOCH)) + 1 if previous else 1)


def touch(doc, method=None):
	if doc.reference_doctype not in KINDS or not doc.reference_name or not available(doc.reference_doctype):
		return
	if doc.doctype == "Comment" and doc.comment_type != "Comment":
		return
	if doc.doctype == "Communication" and doc.communication_type != "Communication":
		return
	previous = doc.get_doc_before_save()
	if previous and (previous.reference_doctype, previous.reference_name) != (
		doc.reference_doctype,
		doc.reference_name,
	):
		return
	if previous and previous.content == doc.content:
		return
	at = doc.modified if previous else doc.creation
	row = frappe.db.get_value(
		doc.reference_doctype, doc.reference_name, [FIELD, EPOCH], as_dict=True, for_update=True
	)
	if row and (not row.get(FIELD) or get_datetime(row[FIELD]) < get_datetime(at)):
		frappe.db.set_value(
			doc.reference_doctype,
			doc.reference_name,
			{FIELD: at, EPOCH: cint(row[EPOCH]) + 1},
			update_modified=False,
		)


def facts_for(doc, minutes):
	from exp_theme.notifications.access import event_time

	from crm.notification_rules import engine

	at = event_time(doc.get(FIELD)) + timedelta(minutes=minutes)
	return {
		**engine.snapshot_document(doc, "record_inactive", actor=None, occurred_at=system_time(at)),
		"inactive_minutes": minutes,
		"activity_at": str(doc.get(FIELD)),
		"activity_epoch": cint(doc.get(EPOCH)),
	}


def refreshed(facts, user, lock=False):
	from crm.notification_rules.access import readable

	if (
		not enabled()
		or not available(facts["object"])
		or not readable(facts["object"], facts["record_id"], user)
	):
		return None
	from exp_theme.notifications.access import event_time

	if lock:
		frappe.db.get_value(facts["object"], facts["record_id"], "name", for_update=True)
	doc = frappe.get_doc(facts["object"], facts["record_id"])
	if str(doc.get(FIELD)) != facts.get("activity_at") or cint(doc.get(EPOCH)) != facts.get("activity_epoch"):
		return None
	fire = event_time(doc.get(FIELD)) + timedelta(minutes=facts["inactive_minutes"])
	if not fire <= clock() < fire + timedelta(minutes=GRACE_MINUTES):
		return None
	return {**facts, **facts_for(doc, facts["inactive_minutes"])}


def _publish(doc, user, facts, epoch):
	from exp_theme.notifications.access import identity

	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user

	event_id = "crm-inactivity:" + identity(
		doc.doctype, doc.name, facts["activity_epoch"], facts["inactive_minutes"]
	)
	if frappe.db.exists("CRM Notification", identity(event_id, user)):
		return False
	notify_user(
		{
			"owner": None,
			"assigned_to": user,
			"notification_type": "Reminder",
			"reference_doctype": doc.doctype,
			"reference_docname": doc.name,
			"redirect_to_doctype": doc.doctype,
			"redirect_to_docname": doc.name,
			"message": frappe._("No recent activity on a CRM record."),
			"notification_text": frappe._("No recent activity on a CRM record."),
			"event_id": event_id,
			"event_at": facts["occurred_at"],
			"exp_notification_snapshot": json.dumps({**facts, "policy_epoch": epoch}, sort_keys=True),
			"allow_self_notification": True,
		}
	)
	return True


@_job
def run():
	if not enabled():
		return {"published": 0, "scanned": 0}
	from exp_theme.notifications import policy
	from exp_theme.notifications.access import event_time

	from crm.notification_rules import engine

	counts = {"published": 0, "scanned": 0}
	now = clock()
	for row in frappe.get_all(policy.DOCTYPE, filters={"source": "crm"}, fields=["*"]):
		if not frappe.db.get_value("User", row.user, "enabled"):
			continue
		rules = [
			r
			for r in policy.configuration(row).get("rules", [])
			if r["enabled"] and r["event"] == "record_inactive"
		]
		for kind, minutes in sorted({(r["object"], r["inactive_minutes"]) for r in rules}):
			if not available(kind):
				continue
			cutoff = now - timedelta(minutes=minutes)
			start = max(
				cutoff - timedelta(minutes=GRACE_MINUTES),
				event_time(row.activated_at) - timedelta(minutes=minutes),
			)
			offset = 0
			while True:
				names = frappe.get_all(
					kind,
					filters={FIELD: ["between", [system_time(start), system_time(cutoff)]]},
					pluck="name",
					order_by=FIELD + ", name",
					start=offset,
					limit=200,
				)
				for name in names:
					counts["scanned"] += 1
					doc = frappe.get_doc(kind, name)
					facts = facts_for(doc, minutes)
					matched = engine.evaluate(facts, row.user)
					if any(matched["channels"].values()) and refreshed(facts, row.user):
						counts["published"] += int(_publish(doc, row.user, facts, matched["epoch"]))
				if len(names) < 200:
					break
				offset += len(names)
	return counts
