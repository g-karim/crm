# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from functools import partial

import frappe
from frappe.desk.reportview import build_match_conditions
from frappe.model.document import Document

MESSENGER_REFERENCE_DOCTYPES = {"CRM Deal", "CRM Lead"}


class CRMNotification(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		comment: DF.Link | None
		event_count: DF.Int
		from_user: DF.Link | None
		last_event_at: DF.Datetime | None
		message: DF.HTMLEditor | None
		notification_text: DF.Text | None
		notification_type_doc: DF.DynamicLink | None
		notification_type_doctype: DF.Link | None
		read: DF.Check
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		to_user: DF.Link
		type: DF.Literal["Mention", "Task", "Assignment", "WhatsApp", "Messenger"]
	# end: auto-generated types

	def on_update(self):
		if not self.to_user or not can_access_notification(self, user=self.to_user):
			return

		message = {"name": self.name, "type": self.type, "reference_name": self.reference_name}
		if self.type != "Messenger":
			frappe.publish_realtime("crm_notification", message, user=self.to_user, after_commit=True)
			return

		frappe.db.after_commit.add(
			partial(
				_publish_messenger_realtime,
				self.to_user,
				self.reference_doctype,
				self.reference_name,
				message,
			)
		)


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	visibility_condition = get_notification_visibility_condition(user)
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return visibility_condition

	return f"`tabCRM Notification`.`to_user` = {frappe.db.escape(user)} and {visibility_condition}"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if doc.type == "Messenger" and not can_access_notification(doc, user=user):
		return False

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if ptype == "create":
		return False

	if not doc.to_user:
		return True

	return doc.to_user == user


def get_notification_visibility_condition(user=None):
	"""Keep ordinary notifications and Messenger rows with a readable CRM reference."""
	if not user:
		user = frappe.session.user

	return (
		"("
		+ " or ".join(
			[
				"`tabCRM Notification`.`type` != 'Messenger'",
				_messenger_reference_visibility_condition(
					"CRM Lead", "`tabCRM Lead`", _get_read_permission_condition("CRM Lead", user)
				),
				_messenger_reference_visibility_condition(
					"CRM Deal", "`tabCRM Deal`", _get_read_permission_condition("CRM Deal", user)
				),
			]
		)
		+ ")"
	)


def _get_read_permission_condition(doctype, user):
	if not frappe.has_permission(doctype, "read", user=user):
		return "false"
	return build_match_conditions(doctype, user=user) or "true"


def _messenger_reference_visibility_condition(doctype, table, permission_condition):
	return f"""(
		`tabCRM Notification`.`reference_doctype` = '{doctype}'
		and `tabCRM Notification`.`type` = 'Messenger'
		and exists (
			select 1 from {table}
			where {table}.`name` = `tabCRM Notification`.`reference_name`
				and ({permission_condition})
		)
	)"""


def can_access_notification(notification, user=None):
	if notification.type != "Messenger":
		return True
	if (
		notification.reference_doctype not in MESSENGER_REFERENCE_DOCTYPES
		or not notification.reference_name
		or not frappe.db.exists(notification.reference_doctype, notification.reference_name)
	):
		return False
	doc = frappe.get_doc(notification.reference_doctype, notification.reference_name)
	return frappe.has_permission(notification.reference_doctype, "read", doc=doc, user=user)


def _publish_messenger_realtime(user, reference_doctype, reference_name, message):
	notification = frappe._dict(
		type="Messenger",
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)
	if can_access_notification(notification, user=user):
		frappe.publish_realtime("crm_notification", message, user=user)


def notify_user(notification):
	"""
	Notify the assigned user
	"""
	notification = frappe._dict(notification)
	if notification.owner == notification.assigned_to:
		return

	values = frappe._dict(
		doctype="CRM Notification",
		from_user=notification.owner,
		to_user=notification.assigned_to,
		type=notification.notification_type,
		message=notification.message,
		notification_text=notification.notification_text,
		notification_type_doctype=notification.reference_doctype,
		notification_type_doc=notification.reference_docname,
		reference_doctype=notification.redirect_to_doctype,
		reference_name=notification.redirect_to_docname,
	)

	if frappe.db.exists("CRM Notification", values):
		return
	frappe.get_doc(values).insert(ignore_permissions=True)
