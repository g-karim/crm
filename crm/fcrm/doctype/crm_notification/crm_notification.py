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
		if self.type != "Messenger" and self.reference_doctype != "CRM Lead":
			frappe.publish_realtime("crm_notification", message, user=self.to_user, after_commit=True)
			return

		frappe.db.after_commit.add(
			partial(
				_publish_scoped_realtime,
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

	if ptype != "create" and not can_access_notification(doc, user=user):
		return False

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if ptype not in {"read", "select"}:
		return False

	if not doc.to_user:
		return True

	return doc.to_user == user


def get_notification_visibility_condition(user=None):
	"""Apply current CRM reference permissions to every notification category."""
	if not user:
		user = frappe.session.user

	return (
		"("
		+ " or ".join(
			[
				"(coalesce(`tabCRM Notification`.`reference_doctype`, '') = '' and coalesce(`tabCRM Notification`.`reference_name`, '') = '' and `tabCRM Notification`.`type` != 'Messenger')",
				_messenger_reference_visibility_condition(
					"CRM Lead", "`tabCRM Lead`", _get_read_permission_condition("CRM Lead", user)
				),
				_messenger_reference_visibility_condition(
					"CRM Deal", "`tabCRM Deal`", _get_read_permission_condition("CRM Deal", user)
				),
			]
		)
		+ ") and " + _task_visibility_condition(user)
	)


def _get_read_permission_condition(doctype, user):
	if not frappe.has_permission(doctype, "read", user=user):
		return "false"
	return build_match_conditions(doctype, user=user) or "true"


def _messenger_reference_visibility_condition(doctype, table, permission_condition):
	return f"""(
		`tabCRM Notification`.`reference_doctype` = '{doctype}'
		and exists (
			select 1 from {table}
			where {table}.`name` = `tabCRM Notification`.`reference_name`
				and ({permission_condition})
		)
	)"""


def _task_visibility_condition(user):
	condition = _get_read_permission_condition("CRM Task", user)
	return f"""(coalesce(`tabCRM Notification`.`notification_type_doctype`, '') != 'CRM Task' or exists (
		select 1 from `tabCRM Task` where `tabCRM Task`.`name` = `tabCRM Notification`.`notification_type_doc`
		and ({condition}) and (
			(coalesce(`tabCRM Task`.`reference_doctype`, '') = '' and coalesce(`tabCRM Task`.`reference_docname`, '') = '')
			or (`tabCRM Task`.`reference_doctype` = `tabCRM Notification`.`reference_doctype`
				and `tabCRM Task`.`reference_docname` = `tabCRM Notification`.`reference_name`)
		)))"""


def can_access_notification(notification, user=None):
	user = user or frappe.session.user
	if not frappe.db.get_value("User", user, "enabled") or not frappe.has_permission("CRM Notification", "read", user=user):
		return False
	reference_type, reference_name = notification.get("reference_doctype"), notification.get("reference_name")
	if reference_type or reference_name or notification.type == "Messenger":
		if reference_type not in MESSENGER_REFERENCE_DOCTYPES or not _readable(reference_type, reference_name, user):
			return False
	if notification.get("notification_type_doctype") == "CRM Task":
		name = notification.get("notification_type_doc")
		if not _readable("CRM Task", name, user):
			return False
		task = frappe.get_doc("CRM Task", name)
		if task.reference_doctype or task.reference_docname:
			return (task.reference_doctype == reference_type and task.reference_docname == reference_name
				and _readable(task.reference_doctype, task.reference_docname, user))
	return True


def _readable(doctype, name, user):
	if not name or not frappe.db.exists(doctype, name):
		return False
	return frappe.has_permission(doctype, "read", doc=frappe.get_doc(doctype, name), user=user)


def _publish_scoped_realtime(user, reference_doctype, reference_name, message):
	notification = frappe._dict(
		type=message["type"],
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)
	if can_access_notification(notification, user=user):
		frappe.publish_realtime("crm_notification", message, user=user)
	else:
		# Invalidate cached rows without exposing a revoked CRM reference.
		frappe.publish_realtime("crm_notification", {}, user=user)


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

	if notification.event_id:
		from hashlib import sha256

		values.last_event_id = notification.event_id
		name = sha256(f"{notification.event_id}\0{notification.assigned_to}".encode()).hexdigest()
		if not frappe.db.exists("CRM Notification", name):
			frappe.get_doc(values).insert(ignore_permissions=True, ignore_if_duplicate=True, set_name=name)
		return
	if frappe.db.exists("CRM Notification", values):
		return
	frappe.get_doc(values).insert(ignore_permissions=True)
