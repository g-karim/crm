"""Trusted CRM events; source records, native history and outboxes share one transaction."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from html import escape

import frappe

_ASSIGNMENT = ContextVar("crm_notification_assignment", default=None)
KINDS = {"CRM Lead": "lead_assigned", "CRM Deal": "deal_assigned", "CRM Task": "task_assigned"}


def ready():
	return "exp_theme" in frappe.get_installed_apps() and frappe.db.table_exists("EXP Notification Policy")


def owner_event_id(doc):
	from exp_theme.notifications.access import identity

	previous = doc.get_doc_before_save()
	field = "lead_owner" if doc.doctype == "CRM Lead" else "deal_owner"
	return (
		"crm-assignment:"
		+ identity(
			doc.doctype, doc.name, doc.modified, previous.get(field) if previous else None, doc.get(field)
		)
		+ ":assigned"
	)


@contextmanager
def assignment_context(doc):
	if not ready():
		yield
		return
	from crm.notification_rules.engine import snapshot_document

	facts = snapshot_document(doc, KINDS[doc.doctype], actor=frappe.session.user, occurred_at=doc.modified)
	token = _ASSIGNMENT.set(
		{"doctype": doc.doctype, "name": str(doc.name), "id": owner_event_id(doc), "facts": facts}
	)
	try:
		yield
	finally:
		_ASSIGNMENT.reset(token)


def assignment_id(todo):
	context = _ASSIGNMENT.get()
	if context and (context["doctype"], context["name"]) == (todo.reference_type, str(todo.reference_name)):
		return context["id"]
	previous = frappe.db.get_value(
		"CRM Notification", {"aggregation_key": assignment_key(todo)}, "last_event_id", for_update=True
	)
	if previous:
		return previous
	return f"crm-assignment:{todo.name}:assigned"


def assignment_key(todo):
	return sha256(f"crm-todo-assignment\0{todo.name}\0{todo.allocated_to}".encode()).hexdigest()


def allows_self_assignment(notification):
	if (
		not ready()
		or notification.reference_doctype not in KINDS
		or notification.notification_type != "Assignment"
	):
		return False
	if not (notification.event_id or "").endswith(":assigned"):
		return False
	from crm.notification_rules import engine

	facts = _assignment_facts(
		notification.reference_doctype,
		notification.reference_docname,
		notification.owner,
		notification.event_at or frappe.utils.now_datetime(),
		notification.assigned_to,
	)
	return any(engine.evaluate(facts, notification.assigned_to)["channels"].values())


def _assignment_facts(doctype, name, actor, occurred_at, assignee):
	from crm.notification_rules import engine

	context = _ASSIGNMENT.get()
	if context and (context["doctype"], context["name"]) == (doctype, str(name)):
		facts = dict(context["facts"])
	else:
		facts = engine.snapshot(doctype, name, KINDS[doctype], actor=actor, occurred_at=occurred_at)
	return {**facts, "assignee": assignee}


def capture_notification(doc, method=None):
	if not ready() or doc.get("exp_notification_snapshot") or doc.type != "Assignment":
		return
	if doc.notification_type_doctype not in KINDS or not (doc.last_event_id or "").endswith(":assigned"):
		return
	from exp_theme.notifications import policy

	facts = _assignment_facts(
		doc.notification_type_doctype,
		doc.notification_type_doc,
		doc.from_user,
		doc.last_event_at or doc.creation,
		doc.to_user,
	)
	facts["policy_epoch"] = policy.load(doc.to_user, "crm").delivery_epoch
	doc.exp_notification_snapshot = json.dumps(facts, sort_keys=True)


def _owner_changed(doc, previous):
	field = "lead_owner" if doc.doctype == "CRM Lead" else "deal_owner"
	owner = doc.get(field)
	if not owner or (previous and previous.get(field) == owner):
		return
	from exp_theme.notifications import policy

	from crm.notification_rules.engine import snapshot_document

	facts = snapshot_document(doc, KINDS[doc.doctype], actor=frappe.session.user, occurred_at=doc.modified)
	facts.update(assignee=owner, policy_epoch=policy.load(owner, "crm").delivery_epoch)
	_publish(doc, owner, owner_event_id(doc), facts, "Assignment")


def lead_changed(doc, method=None):
	_changed(doc, "lead_status_changed", "crm-lead-status:")


def deal_changed(doc, method=None):
	_changed(doc, "deal_stage_changed", "crm-deal-stage:")


def _changed(doc, event, prefix):
	if not ready():
		return
	from exp_theme.notifications import policy
	from exp_theme.notifications.access import identity

	from crm.notification_rules import engine

	previous = doc.get_doc_before_save()
	_owner_changed(doc, previous)
	if not previous or (previous.status == doc.status and previous.get("pipeline") == doc.get("pipeline")):
		return
	facts = engine.snapshot_document(
		doc,
		event,
		actor=frappe.session.user,
		occurred_at=doc.modified,
		previous_status=previous.status,
		previous_pipeline=previous.get("pipeline"),
	)
	parts = [doc.name, doc.modified, previous.status, doc.status]
	if doc.doctype == "CRM Deal":
		parts.extend([previous.pipeline, doc.pipeline])
	event_id = prefix + identity(*parts)
	for row in frappe.get_all(policy.DOCTYPE, filters={"source": "crm"}, fields=["user"]):
		if not frappe.db.get_value("User", row.user, "enabled"):
			continue
		result = engine.evaluate(facts, row.user)
		if any(result["channels"].values()):
			_publish(doc, row.user, event_id, {**facts, "policy_epoch": result["epoch"]}, "Status Change")


def _publish(doc, user, event_id, facts, kind):
	from crm.fcrm.doctype.crm_notification.crm_notification import notify_user

	if kind == "Assignment":
		text = frappe._("A CRM record was assigned to you.")
	else:
		text = frappe._(
			"Lead status changed: {0} → {1}" if doc.doctype == "CRM Lead" else "Deal stage changed: {0} → {1}"
		).format(escape(str(facts["previous_status"])), escape(str(facts["status"])))
	notify_user(
		{
			"owner": facts["actor"],
			"assigned_to": user,
			"notification_type": kind,
			"reference_doctype": doc.doctype,
			"reference_docname": doc.name,
			"redirect_to_doctype": doc.doctype,
			"redirect_to_docname": doc.name,
			"message": text,
			"notification_text": text,
			"event_id": event_id,
			"exp_notification_snapshot": json.dumps(facts, sort_keys=True),
			"allow_self_notification": kind != "Assignment",
		}
	)
