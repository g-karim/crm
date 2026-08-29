import hashlib

import frappe
from frappe.utils import cint


def execute():
	if not frappe.db.table_exists("CRM Notification"):
		return
	groups = frappe.db.sql(
		"""
		select to_user, notification_type_doc
		from `tabCRM Notification`
		where type = 'Messenger' and `read` = 0
			and notification_type_doctype = 'Messenger Conversation'
		group by to_user, notification_type_doc
		""",
		as_dict=True,
	)
	for group in groups:
		_migrate_group(group.to_user, group.notification_type_doc)
	_add_notification_index()


def _add_notification_index():
	index_name = "crm_notification_user_read_event"
	table_name = "tabCRM Notification"
	if frappe.db.has_index(table_name, index_name):
		return
	if frappe.db.db_type == "mariadb":
		frappe.db.sql_ddl(
			f"alter table `{table_name}` add index `{index_name}` (`to_user`, `read`, `last_event_at`)"
		)
		return
	frappe.db.add_index(
		"CRM Notification",
		['"to_user"', '"read"', '"last_event_at"'],
		index_name=index_name,
	)


def _migrate_group(user, conversation):
	rows = frappe.get_all(
		"CRM Notification",
		filters={
			"to_user": user,
			"type": "Messenger",
			"read": False,
			"notification_type_doctype": "Messenger Conversation",
			"notification_type_doc": conversation,
		},
		fields=["name", "event_count", "last_event_at", "creation", "notification_text", "last_event_id"],
		order_by="last_event_at desc, creation desc",
	)
	if not rows:
		return
	winner = rows[0]
	event_count = sum(max(cint(row.event_count), 1) for row in rows)
	last_event_id = winner.last_event_id or _latest_message(conversation)
	for row in rows[1:]:
		frappe.delete_doc("CRM Notification", row.name, ignore_permissions=True, force=True)
	frappe.db.set_value(
		"CRM Notification",
		winner.name,
		{
			"event_count": event_count,
			"last_event_id": last_event_id,
			"aggregation_key": _aggregation_key(user, conversation),
		},
		update_modified=False,
	)


def _latest_message(conversation):
	if not frappe.db.table_exists("Messenger Message"):
		return None
	return frappe.db.get_value(
		"Messenger Message",
		{"conversation": conversation, "direction": "inbound", "status": ["!=", "deleted"]},
		"name",
		order_by="message_datetime desc, creation desc",
	)


def _aggregation_key(user, conversation):
	return hashlib.sha256(f"{user}\0{conversation}".encode()).hexdigest()
