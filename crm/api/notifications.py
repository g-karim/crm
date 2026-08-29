import frappe
from frappe import _
from frappe.utils import add_to_date, cint, now_datetime

from crm.fcrm.doctype.crm_notification.crm_notification import (
	can_access_notification,
	get_notification_visibility_condition,
)


@frappe.whitelist()
def get_notifications(limit: int = 100):
	limit = min(max(cint(limit) or 100, 1), 100)
	visibility_condition = get_notification_visibility_condition()
	rows = frappe.db.sql(
		f"""
		select
			name, creation, last_event_at, last_event_id, event_count, from_user,
			type, to_user, `read`, notification_text, notification_type_doctype,
			notification_type_doc, reference_doctype, reference_name, message
		from `tabCRM Notification`
		where to_user = %s and {visibility_condition}
		order by coalesce(last_event_at, creation) desc
		limit %s
		""",
		(frappe.session.user, limit + 1),
		as_dict=True,
	)
	has_more = len(rows) > limit
	rows = rows[:limit]
	from_users = {row.from_user for row in rows if row.from_user}
	full_names = (
		{
			row.name: row.full_name
			for row in frappe.get_all(
				"User", filters={"name": ["in", sorted(from_users)]}, fields=["name", "full_name"]
			)
		}
		if from_users
		else {}
	)

	notifications = []
	for row in rows:
		notifications.append(
			{
				"name": row.name,
				"creation": row.creation,
				"last_event_at": row.last_event_at,
				"last_event_id": row.last_event_id,
				"event_count": max(cint(row.event_count), 1),
				"from_user": {"name": row.from_user, "full_name": full_names.get(row.from_user)},
				"type": row.type,
				"to_user": row.to_user,
				"read": row.read,
				"hash": get_hash(row),
				"notification_text": row.notification_text,
				"notification_type_doctype": row.notification_type_doctype,
				"notification_type_doc": row.notification_type_doc,
				"reference_doctype": "deal" if row.reference_doctype == "CRM Deal" else "lead",
				"reference_name": row.reference_name,
				"route_name": "Deal" if row.reference_doctype == "CRM Deal" else "Lead",
			}
		)

	unread_count = frappe.db.sql(
		f"""
		select coalesce(sum(case when type = 'Messenger' then greatest(coalesce(event_count, 1), 1) else 1 end), 0)
		from `tabCRM Notification`
		where to_user = %s and `read` = 0 and {visibility_condition}
		""",
		frappe.session.user,
	)[0][0]
	return {"notifications": notifications, "unread_count": cint(unread_count), "has_more": has_more}


@frappe.whitelist(methods=["POST"])
def mark_messenger_as_read(conversation: str, last_event_id: str):
	conversation_row = frappe.db.get_value(
		"Messenger Conversation",
		conversation,
		["reference_doctype", "reference_name"],
		as_dict=True,
	)
	if not conversation_row or conversation_row.reference_doctype != "CRM Lead":
		frappe.throw(_("Conversation was not found."), frappe.DoesNotExistError)
	lead = frappe.get_doc("CRM Lead", conversation_row.reference_name)
	if not frappe.has_permission("CRM Lead", "read", doc=lead):
		frappe.throw(_("You are not permitted to access this CRM record."), frappe.PermissionError)

	rows = frappe.db.sql(
		"""
		select name, last_event_id
		from `tabCRM Notification`
		where to_user = %s and type = 'Messenger'
			and notification_type_doctype = 'Messenger Conversation'
			and notification_type_doc = %s
			and reference_doctype = 'CRM Lead'
			and reference_name = %s and `read` = 0
		for update
		""",
		(frappe.session.user, conversation, conversation_row.reference_name),
		as_dict=True,
	)
	if not rows or any(row.last_event_id != last_event_id for row in rows):
		return {"ok": True, "marked": 0, "stale": bool(rows)}
	for row in rows:
		_mark_locked_notification_read(row.name)
	return {"ok": True, "marked": len(rows), "stale": False}


@frappe.whitelist(methods=["POST"])
def mark_as_read(notification: str):
	row = _lock_notification(notification)
	if not row or row.to_user != frappe.session.user or row.read or not can_access_notification(row):
		return {"ok": True, "marked": 0}
	_mark_locked_notification_read(row.name)
	return {"ok": True, "marked": 1}


@frappe.whitelist(methods=["POST"])
def mark_all_as_read(limit: int = 500):
	limit = min(max(cint(limit) or 500, 1), 500)
	visibility_condition = get_notification_visibility_condition()
	rows = frappe.db.sql(
		f"""
		select name
		from `tabCRM Notification`
		where to_user = %s and `read` = 0 and {visibility_condition}
		order by creation asc
		limit %s
		""",
		(frappe.session.user, limit),
		as_dict=True,
	)
	marked = 0
	for candidate in rows:
		row = _lock_notification(candidate.name)
		if row and row.to_user == frappe.session.user and not row.read and can_access_notification(row):
			_mark_locked_notification_read(row.name)
			marked += 1
	has_more = bool(
		frappe.db.sql(
			f"""
			select 1
			from `tabCRM Notification`
			where to_user = %s and `read` = 0 and {visibility_condition}
			limit 1
			""",
			frappe.session.user,
		)
	)
	return {"ok": True, "marked": marked, "has_more": has_more}


def get_hash(notification):
	_hash = ""
	if notification.type == "Mention" and notification.notification_type_doc:
		_hash = "#" + notification.notification_type_doc
	if notification.type == "WhatsApp":
		_hash = "#whatsapp"
	if notification.type == "Messenger":
		_hash = "#messenger"
	if notification.type == "Assignment" and notification.notification_type_doctype == "CRM Task":
		_hash = "#tasks"
		if "has been removed by" in (notification.message or ""):
			_hash = ""
	return _hash


def _lock_notification(name):
	rows = frappe.db.sql(
		"""
		select name, to_user, `read`, type, reference_doctype, reference_name
		from `tabCRM Notification`
		where name = %s
		for update
		""",
		name,
		as_dict=True,
	)
	return rows[0] if rows else None


def _mark_locked_notification_read(name):
	notification = frappe.get_doc("CRM Notification", name)
	notification.read = True
	if notification.type == "Messenger":
		notification.aggregation_key = None
	notification.save(ignore_permissions=True)


def cleanup_messenger_notifications(limit=1000):
	limit = min(max(cint(limit) or 1000, 1), 1000)
	now = now_datetime()
	read_cutoff = add_to_date(now, days=-30)
	unread_cutoff = add_to_date(now, days=-90)
	rows = frappe.db.sql(
		"""
		select name
		from `tabCRM Notification`
		where type = 'Messenger'
			and ((`read` = 1 and coalesce(last_event_at, creation) <= %s)
				or (`read` = 0 and coalesce(last_event_at, creation) <= %s))
		order by coalesce(last_event_at, creation) asc
		limit %s
		""",
		(read_cutoff, unread_cutoff, limit),
		as_dict=True,
	)
	for row in rows:
		frappe.delete_doc("CRM Notification", row.name, ignore_permissions=True, force=True)
	return len(rows)
