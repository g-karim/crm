"""Canonical incoming CRM messages; metadata edits never create another event."""

import json

import frappe

from crm.notification_rules.access import readable

KINDS = {"CRM Lead", "CRM Deal"}


def valid(doc, user=None):
	if doc.doctype != "Communication":
		return False
	if (
		doc.communication_type != "Communication"
		or doc.sent_or_received != "Received"
		or doc.communication_medium != "Email"
		or doc.reference_doctype not in KINDS
		or not doc.reference_name
	):
		return False
	# Match CRM activities/get_docinfo: a linked timeline inherits its CRM record ACL.
	# This does not grant standalone Inbox/Communication access.
	return not user or readable(doc.reference_doctype, doc.reference_name, user)


def changed(doc, method=None):
	from crm.notification_rules.events import ready

	if not ready() or not valid(doc):
		return
	from exp_theme.notifications import policy

	from crm.notification_rules import engine

	previous = doc.get_doc_before_save()
	if previous and (previous.reference_doctype, previous.reference_name) != (
		doc.reference_doctype,
		doc.reference_name,
	):
		return  # Moving an old message cannot replay it to another audience.
	for user in frappe.get_all(policy.DOCTYPE, filters={"source": "crm"}, pluck="user"):
		if not frappe.db.get_value("User", user, "enabled") or not valid(doc, user):
			continue
		facts = engine.snapshot(
			doc.reference_doctype,
			doc.reference_name,
			"message_received",
			actor=None,
			occurred_at=doc.creation,
		)
		facts.update(message_doctype="Communication", message_id=doc.name)
		result = engine.evaluate(facts, user)
		if any(result["channels"].values()):
			_publish(doc, user, {**facts, "policy_epoch": result["epoch"]})


def _publish(doc, user, facts):
	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user

	notify_user(
		{
			"owner": None,
			"assigned_to": user,
			"notification_type": "Message",
			"reference_doctype": "Communication",
			"reference_docname": doc.name,
			"redirect_to_doctype": doc.reference_doctype,
			"redirect_to_docname": doc.reference_name,
			"message": frappe._("An incoming customer message was received."),
			"notification_text": frappe._("An incoming customer message was received."),
			"event_id": "crm-incoming:Communication:" + doc.name,
			"event_at": doc.creation,
			"exp_notification_snapshot": json.dumps(facts, sort_keys=True),
			"allow_self_notification": True,
		}
	)


def refreshed(facts, user, lock=False):
	from crm.notification_rules import engine

	name = facts.get("message_id")
	if facts.get("message_doctype") != "Communication" or not frappe.db.exists("Communication", name):
		return None
	if lock:
		frappe.db.get_value("Communication", name, "name", for_update=True)
	doc = frappe.get_doc("Communication", name)
	if not valid(doc, user) or (doc.reference_doctype, str(doc.reference_name)) != (
		facts["object"],
		facts["record_id"],
	):
		return None
	current = engine.snapshot(
		doc.reference_doctype,
		doc.reference_name,
		facts["event"],
		actor=None,
		occurred_at=facts["occurred_at"],
	)
	return {**facts, **current}
