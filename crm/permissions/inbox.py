"""Apply mailbox rights to native Communication/File reads as well as the inbox."""

import frappe


def communication_permission(doc, ptype="read", user=None, **kwargs):
	if doc.communication_medium != "Email" or not frappe.db.exists("DocType", "CRM Inbox Access"):
		return True
	from crm.api.inbox import _account_allowed

	if not _account_allowed(
		"email", doc.email_account, user=user, send=ptype not in {"read", "select", "report", "print"}
	):
		return False
	return True


def file_permission(doc, ptype="read", user=None, **kwargs):
	if doc.attached_to_doctype != "CRM Inbox State" or not doc.attached_to_name:
		return True
	from crm.api import inbox

	state = frappe.db.get_value(
		inbox.STATE, doc.attached_to_name, ["user", "source_kind", "source_name"], as_dict=True
	)
	u = user or frappe.session.user
	if not state or state.user != u:
		return False
	dt = "Communication" if state.source_kind == "email" else "Messenger Conversation"
	if not frappe.db.exists(dt, state.source_name):
		return False
	return inbox._source_allowed(state.source_kind, frappe.get_doc(dt, state.source_name), user=u)
