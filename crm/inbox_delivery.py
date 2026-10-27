"""Run only explicitly submitted inbox messages, never the general queue."""

import frappe

from crm.api import inbox


def work():
	from crm_messenger.services.outbound import process_outbound_message

	admin = frappe.session.user
	try:
		for row in frappe.get_all(
			"Messenger Message",
			filters={
				"client_request_id": ["like", "crm-inbox-%"],
				"direction": "outbound",
				"status": ["in", ["queued", "retrying", "sending"]],
			},
			fields=["name", "crm_user", "conversation"],
			order_by="creation asc",
			limit_page_length=20,
		):
			if not row.crm_user or not frappe.db.get_value("User", row.crm_user, "enabled"):
				continue
			frappe.set_user(row.crm_user)
			try:
				source, _ = inbox._load("messenger", row.conversation, write=True)
				if not inbox._is_demo("messenger", source):
					process_outbound_message(row.name)
					frappe.db.commit()
			except (frappe.PermissionError, frappe.DoesNotExistError):
				frappe.db.rollback()
			finally:
				frappe.set_user(admin)
	finally:
		frappe.set_user(admin)
