import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.utils import add_to_date, cint, now_datetime

from crm.fcrm.doctype.crm_notification.crm_notification import (
	can_access_notification,
)


@frappe.whitelist()
def get_notifications(limit: int = 100):
	user = _require_viewer()
	limit = min(max(cint(limit) or 100, 1), 100)
	Notification = frappe.qb.DocType("CRM Notification")
	rows = (
		_visible_notifications_query(Notification)
		.select(
			Notification.name,
			Notification.creation,
			Notification.last_event_at,
			Notification.last_event_id,
			Notification.event_count,
			Notification.from_user,
			Notification.type,
			Notification.to_user,
			Notification.read,
			Notification.notification_text,
			Notification.notification_type_doctype,
			Notification.notification_type_doc,
			Notification.reference_doctype,
			Notification.reference_name,
			Notification.message,
		)
		.orderby(Coalesce(Notification.last_event_at, Notification.creation), order=frappe.qb.desc)
		.run(as_dict=True)
	)
	rows = [row for row in rows if can_access_notification(row, user=user)]
	unread_count = sum(max(cint(row.event_count), 1) if row.type == "Messenger" else 1 for row in rows if not row.read)
	snapshot_token = _snapshot(user, [row for row in rows if not row.read])
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
				"head": _head(row),
				"path": _route(row),
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

	return {"viewer": user, "notifications": notifications, "unread_count": unread_count,
		"has_more": has_more, "snapshot_token": snapshot_token}


@frappe.whitelist(methods=["POST"])
def mark_messenger_as_read(conversation: str, last_event_id: str):
	_require_viewer()
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


def mark_messenger_notifications_through(conversation: str, up_to_message: str | None = None):
	"""Read only this user's notifications covered by a successful chat read."""
	conversation_row = frappe.db.get_value(
		"Messenger Conversation",
		conversation,
		["reference_doctype", "reference_name", "local_inbound_sequence"],
		as_dict=True,
	)
	if not conversation_row or conversation_row.reference_doctype != "CRM Lead":
		return 0

	boundary = (
		frappe.db.get_value("Messenger Message", up_to_message, "local_inbound_sequence")
		if up_to_message
		else conversation_row.local_inbound_sequence
	)
	if not cint(boundary):
		return 0

	rows = frappe.db.sql(
		"""
		select notification.name
		from `tabCRM Notification` notification
		join `tabMessenger Message` message
			on message.name = notification.last_event_id
			and message.conversation = %(conversation)s
		where notification.to_user = %(user)s
			and notification.type = 'Messenger' and notification.`read` = 0
			and notification.notification_type_doctype = 'Messenger Conversation'
			and notification.notification_type_doc = %(conversation)s
			and notification.reference_doctype = 'CRM Lead'
			and notification.reference_name = %(lead)s
			and message.local_inbound_sequence > 0
			and message.local_inbound_sequence <= %(boundary)s
		for update
		""",
		{
			"conversation": conversation,
			"user": frappe.session.user,
			"lead": conversation_row.reference_name,
			"boundary": cint(boundary),
		},
		as_dict=True,
	)
	for row in rows:
		_mark_locked_notification_read(row.name)
	return len(rows)


@frappe.whitelist(methods=["POST"])
def mark_as_read(notification: str, observed_head: str | None = None, expected_viewer: str | None = None):
	_require_viewer(expected_viewer)
	row = _lock_notification(notification)
	if not row or row.to_user != frappe.session.user or row.read or not can_access_notification(row):
		return {"ok": True, "marked": 0}
	if (row.type == "Messenger" and observed_head is None) or (observed_head is not None and observed_head != _head(row)):
		return {"ok": True, "marked": 0, "stale": True}
	_mark_locked_notification_read(row.name)
	return {"ok": True, "marked": 1}


@frappe.whitelist(methods=["POST"])
def mark_all_as_read(limit: int = 500, snapshot_token: str | None = None, cursor: int = 0, expected_viewer: str | None = None):
	user = _require_viewer(expected_viewer)
	limit = min(max(cint(limit) or 500, 1), 500)
	if not snapshot_token:
		rows = frappe.get_all("CRM Notification", filters={"to_user": user, "read": 0}, fields=["*"], limit=0)
		snapshot_token = _snapshot(user, [row for row in rows if can_access_notification(row)])
	rows = _read_snapshot(user, snapshot_token)
	cursor = max(cint(cursor), 0)
	marked = 0
	for candidate in rows[cursor:cursor + limit]:
		row = _lock_notification(candidate.name)
		if row and row.to_user == user and not row.read and _head(row) == candidate.head and can_access_notification(row):
			_mark_locked_notification_read(row.name)
			marked += 1
	return {"ok": True, "marked": marked, "has_more": cursor + limit < len(rows),
		"snapshot_token": snapshot_token, "cursor": cursor + limit}


def _visible_notifications_query(Notification):
	visibility = (Notification.type != "Messenger") & (
		Coalesce(Notification.reference_doctype, "") != "CRM Lead"
	)
	for doctype in ("CRM Lead", "CRM Deal"):
		if not frappe.has_permission(doctype, "read"):
			continue

		Reference = frappe.qb.DocType(doctype)
		readable_references = frappe.get_list(
			doctype,
			fields=[Reference.name],
			order_by=None,
			run=False,
		)
		condition = (Notification.reference_doctype == doctype) & Notification.reference_name.isin(
			readable_references
		)
		if doctype == "CRM Deal":
			condition &= Notification.type == "Messenger"
		visibility |= condition

	return frappe.qb.from_(Notification).where(Notification.to_user == frappe.session.user).where(visibility)


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
		select *
		from `tabCRM Notification`
		where name = %s
		for update
		""",
		name,
		as_dict=True,
	)
	return rows[0] if rows else None


def _head(row):
	from crm.notification_source import notification_head

	return notification_head(row)


def _route(row):
	from crm.notification_source import notification_route

	return notification_route(row)


def _require_viewer(expected_viewer=None):
	user = frappe.session.user
	if user == "Guest" or not frappe.db.get_value("User", user, "enabled") or (expected_viewer is not None and expected_viewer != user):
		frappe.throw(_("Your session changed. Reload this page."), frappe.AuthenticationError)
	if not frappe.has_permission("CRM Notification", "read", user=user):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
	return user


def _snapshot(user, rows):
	token = frappe.generate_hash(length=32)
	frappe.cache.set_value(f"crm_notification_snapshot:{user}:{token}",
		[{"name": row.name, "head": _head(row)} for row in rows], expires_in_sec=900)
	return token


def _read_snapshot(user, token):
	if not isinstance(token, str) or len(token) != 32 or not token.isalnum():
		frappe.throw(_("Invalid notification snapshot."))
	rows = frappe.cache.get_value(f"crm_notification_snapshot:{user}:{token}")
	if rows is None:
		frappe.throw(_("This notification view expired. Refresh it before continuing."))
	return [frappe._dict(row) for row in rows]


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
