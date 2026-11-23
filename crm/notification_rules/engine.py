"""Pure matching of source facts, with fresh access and a versioned delivery barrier."""

import frappe
from exp_theme.notifications import policy
from exp_theme.notifications.access import event_time
from frappe.utils import cint

from crm.notification_rules.access import readable

EMPTY = {"crm_push": False, "one_message": False, "one_push": False, "email": False}


def snapshot(doctype, name, event, *, actor, occurred_at, previous_status=None):
	doc = frappe.get_doc(doctype, name)
	return snapshot_document(
		doc, event, actor=actor, occurred_at=occurred_at, previous_status=previous_status
	)


def snapshot_document(doc, event, *, actor, occurred_at, previous_status=None, previous_pipeline=None):
	doctype = doc.doctype
	context = doc
	if doctype == "CRM Task" and doc.reference_doctype in {"CRM Lead", "CRM Deal"} and doc.reference_docname:
		context = frappe.get_doc(doc.reference_doctype, doc.reference_docname)
	owner_field = {"CRM Lead": "lead_owner", "CRM Deal": "deal_owner", "CRM Task": "assigned_to"}[
		context.doctype
	]
	return {
		"object": context.doctype,
		"record_id": str(context.name),
		"event": event,
		"actor": actor,
		"occurred_at": str(occurred_at),
		"owner": context.get(owner_field),
		"status": context.get("status"),
		"previous_status": previous_status,
		"previous_pipeline": previous_pipeline,
		"source": context.get("source"),
		"pipeline": context.get("pipeline"),
		"task_id": str(doc.name) if doctype == "CRM Task" else None,
		"task_status": doc.get("status") if doctype == "CRM Task" else None,
		"assignee": doc.get("assigned_to") if doctype == "CRM Task" else doc.get(owner_field),
	}


def _record_setting(values, facts):
	return next(
		(
			row
			for row in values.get("records", [])
			if row["object"] == facts["object"] and row["record_id"] == facts["record_id"]
		),
		{},
	)


def matches(rule, facts, user, followed=False):
	event_match = rule["event"] == facts["event"] or (
		rule["event"] == "comment_added" and facts["event"] == "record_mentioned"
	)
	if not rule["enabled"] or rule["object"] != facts["object"] or not event_match:
		return False
	if facts.get("actor") == user and not rule["include_self"]:
		return False
	if (
		facts["event"] in {"lead_assigned", "deal_assigned", "task_assigned", "task_due_soon", "task_overdue"}
		and facts.get("assignee", user) != user
	):
		return False
	if facts["event"] == "task_due_soon" and facts.get("reminder_minutes") != rule.get("reminder_minutes"):
		return False
	if facts["event"] == "record_inactive" and facts.get("inactive_minutes") != rule.get("inactive_minutes"):
		return False
	if rule["event"] == "record_mentioned" and facts.get("mention_recipient") != user:
		return False
	scope = rule["scope"]
	if scope == "owned" and facts.get("owner") != user:
		return False
	if scope == "followed" and not followed:
		return False
	if scope == "selected" and facts["record_id"] not in rule["record_ids"]:
		return False
	if (
		facts["event"] in {"lead_status_changed", "deal_stage_changed"}
		and facts.get("previous_status") == facts.get("status")
		and facts.get("previous_pipeline") == facts.get("pipeline")
	):
		return False
	for key, field in [
		("statuses", "status"),
		("to_statuses", "status"),
		("owners", "owner"),
		("sources", "source"),
		("pipelines", "pipeline"),
	]:
		if rule[key] and facts.get(field) not in rule[key]:
			return False
	from crm.notification_rules.conditions import matches as match_conditions

	return match_conditions(rule, facts, user)


def evaluate(facts, user, expected_epoch=None, lock=False):
	result = {"channels": dict(EMPTY), "matched_rules": [], "reason": "no_matching_rule", "epoch": 0}
	if not readable(facts["object"], facts["record_id"], user) or (
		facts.get("task_id") and not readable("CRM Task", facts["task_id"], user)
	):
		return {**result, "reason": "record_unavailable"}
	row = policy.load(user, "crm", lock=lock)
	result["epoch"] = cint(row.delivery_epoch)
	if expected_epoch is not None and expected_epoch != cint(row.delivery_epoch):
		return {**result, "reason": "policy_changed"}
	values = policy.configuration(row)
	if facts["event"] == "task_reminder":
		if facts.get("reminder_user") != user or _record_setting(values, facts).get("muted"):
			return {**result, "reason": "record_muted"}
		return {**result, "channels": {**EMPTY, **facts["personal_channels"]}, "reason": "personal_reminder"}
	if not row.revision or values.get("mode") == "legacy":
		# Existing task assignments retain their explicit channel masters until opt-in.
		legacy = (
			facts["event"] == "task_assigned"
			and facts.get("actor") != user
			and not _record_setting(values, facts).get("muted")
		)
		return {
			**result,
			"reason": "legacy_settings" if legacy else "no_matching_rule",
			"channels": {**dict.fromkeys(EMPTY, legacy), "email": False},
		}
	if event_time(facts["occurred_at"]) < event_time(row.activated_at):
		return {**result, "reason": "before_activation"}
	return evaluate_rules(values, facts, user, result)


def evaluate_rules(values, facts, user, result=None):
	result = result or {
		"channels": dict(EMPTY),
		"matched_rules": [],
		"reason": "no_matching_rule",
		"epoch": 0,
	}
	record = _record_setting(values, facts)
	if record.get("muted"):
		return {**result, "reason": "record_muted"}
	for rule in values.get("rules", []):
		if matches(rule, facts, user, record.get("followed", False)):
			result["matched_rules"].append(rule["id"])
			for channel in EMPTY:
				result["channels"][channel] |= rule["channels"].get(channel, False)
	if result["matched_rules"]:
		result["reason"] = "matched"
	return result


def permitted(item, user, channel, lock=False):
	facts = item.get("_crm_snapshot")
	if not facts:
		# Pre-existing records remain compatible only while no rules have been saved.
		return not policy.load(user, "crm").revision and item.get("actor") != user
	if facts["event"] in {"task_due_soon", "task_overdue"}:
		from crm.notification_rules.reminders import refreshed

		facts = refreshed(facts, user, lock=lock)
		if not facts:
			return False
	if facts["event"] == "task_reminder":
		from crm.notification_rules.personal_reminders import refreshed

		facts = refreshed(facts, user, lock=lock)
		if not facts:
			return False
	if facts["event"] in {"record_mentioned", "comment_added"}:
		from crm.notification_rules.discussions import refreshed

		facts = refreshed(facts, user, lock=lock)
		if not facts:
			return False
	if facts["event"] == "record_inactive":
		from crm.notification_rules.inactivity import refreshed

		facts = refreshed(facts, user, lock=lock)
		if not facts:
			return False
	if facts["event"] == "message_received":
		from crm.notification_rules.incoming import refreshed

		facts = refreshed(facts, user, lock=lock)
		if not facts:
			return False
	result = evaluate(facts, user, expected_epoch=cint(facts.get("policy_epoch")), lock=lock)
	key = {
		"source_push": "crm_push",
		"one_message": "one_message",
		"one_message_push": "one_push",
		"email": "email",
	}[channel]
	return result["channels"][key]
