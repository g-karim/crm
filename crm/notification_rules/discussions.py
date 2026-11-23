"""Native CRM comments are the single source for mentions and followed discussion events."""

import json

import frappe

from crm.notification_rules import engine
from crm.notification_rules.access import readable

KINDS = {"CRM Lead", "CRM Deal"}


def mentions(content):
	from crm.api.comment import extract_mentions

	return {row.email for row in extract_mentions(content) if isinstance(row.email, str) and row.email}


def changed(doc):
	from exp_theme.notifications import policy

	from crm.notification_rules.events import ready

	if not ready() or doc.reference_doctype not in KINDS or doc.comment_type != "Comment":
		return
	if not doc.reference_name or not frappe.db.exists(doc.reference_doctype, doc.reference_name):
		return
	previous = doc.get_doc_before_save()
	# Existing comments cannot be moved to another record to replay their audience.
	if previous and (previous.reference_doctype, previous.reference_name) != (
		doc.reference_doctype,
		doc.reference_name,
	):
		return
	current = mentions(doc.content)
	new_mentions = current - mentions(previous.content) if previous else current
	users = set(new_mentions)
	if not previous:
		users.update(frappe.get_all(policy.DOCTYPE, filters={"source": "crm"}, pluck="user"))
	for user in sorted(users):
		if not frappe.db.get_value("User", user, "enabled") or not readable(
			doc.reference_doctype, doc.reference_name, user
		):
			continue
		event = "record_mentioned" if user in current else "comment_added"
		facts = engine.snapshot(
			doc.reference_doctype,
			doc.reference_name,
			event,
			actor=frappe.session.user,
			occurred_at=doc.modified if previous else doc.creation,
		)
		facts.update(comment_id=doc.name, mention_recipient=user if user in current else None)
		result = engine.evaluate(facts, user)
		legacy_mention = (
			user in new_mentions and not policy.load(user, "crm").revision and user != facts["actor"]
		)
		if any(result["channels"].values()) or legacy_mention:
			_publish(doc, user, {**facts, "policy_epoch": result["epoch"]})


def _publish(doc, user, facts):
	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user

	text = frappe._(
		"You were mentioned in a CRM comment."
		if facts["mention_recipient"]
		else "A comment was added to a CRM record."
	)
	notify_user(
		{
			"owner": facts["actor"],
			"assigned_to": user,
			"notification_type": "Mention" if facts["mention_recipient"] else "Comment",
			"reference_doctype": "Comment",
			"reference_docname": doc.name,
			"redirect_to_doctype": doc.reference_doctype,
			"redirect_to_docname": doc.reference_name,
			"message": doc.content,
			"notification_text": text,
			"event_id": "crm-comment:" + doc.name,
			"event_at": facts["occurred_at"],
			"exp_notification_snapshot": json.dumps(facts, sort_keys=True),
			"allow_self_notification": True,
		}
	)


def refreshed(facts, user, lock=False):
	row = frappe.db.get_value("Comment", facts.get("comment_id"), "*", as_dict=True, for_update=lock)
	if (
		not row
		or row.comment_type != "Comment"
		or (row.reference_doctype, str(row.reference_name)) != (facts["object"], facts["record_id"])
	):
		return None
	if facts.get("mention_recipient") and user not in mentions(row.content):
		return None
	if not readable(row.reference_doctype, row.reference_name, user):
		return None
	current = engine.snapshot(
		row.reference_doctype,
		row.reference_name,
		facts["event"],
		actor=facts["actor"],
		occurred_at=facts["occurred_at"],
	)
	return {**facts, **current}
