import frappe
from frappe.query_builder import Order
from frappe.query_builder.functions import Coalesce


@frappe.whitelist()
def get_notifications():
	Notification = frappe.qb.DocType("CRM Notification")
	query = (
		frappe.qb.from_(Notification)
		.select("*")
		.where(Notification.to_user == frappe.session.user)
		.orderby(Coalesce(Notification.last_event_at, Notification.creation), order=Order.desc)
	)
	notifications = query.run(as_dict=True)

	_notifications = []
	for notification in notifications:
		from_user = notification.from_user
		_notifications.append(
			{
				"name": notification.name,
				"creation": notification.creation,
				"last_event_at": notification.last_event_at,
				"event_count": max(int(notification.event_count or 1), 1),
				"from_user": {
					"name": from_user,
					"full_name": frappe.get_value("User", from_user, "full_name")
					if from_user
					else None,
				},
				"type": notification.type,
				"to_user": notification.to_user,
				"read": notification.read,
				"hash": get_hash(notification),
				"notification_text": notification.notification_text,
				"notification_type_doctype": notification.notification_type_doctype,
				"notification_type_doc": notification.notification_type_doc,
				"reference_doctype": ("deal" if notification.reference_doctype == "CRM Deal" else "lead"),
				"reference_name": notification.reference_name,
				"route_name": ("Deal" if notification.reference_doctype == "CRM Deal" else "Lead"),
			}
		)

	return _notifications


@frappe.whitelist()
def mark_messenger_as_read(reference_name: str):
	lead = frappe.get_doc("CRM Lead", reference_name)
	if not frappe.has_permission("CRM Lead", "read", doc=lead):
		frappe.throw("You are not permitted to access this CRM record.", frappe.PermissionError)

	rows = frappe.get_all(
		"CRM Notification",
		filters={
			"to_user": frappe.session.user,
			"type": "Messenger",
			"reference_doctype": "CRM Lead",
			"reference_name": reference_name,
			"read": False,
		},
		fields=["name", "notification_type_doc"],
	)
	marked = 0
	for row in rows:
		marked += _mark_notification_read(
			row.name,
			frappe.session.user,
			conversation=row.notification_type_doc,
		)

	return {"ok": True, "marked": marked}


@frappe.whitelist()
def mark_as_read(user: str | None = None, doc: str | None = None):
	user = user or frappe.session.user
	filters = {"to_user": user, "read": False}
	or_filters = []
	if doc:
		or_filters = [
			{"comment": doc},
			{"notification_type_doc": doc},
		]
	for row in frappe.get_all(
		"CRM Notification",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "type", "notification_type_doc"],
	):
		if row.type == "Messenger":
			_mark_notification_read(
				row.name,
				frappe.session.user,
				conversation=row.notification_type_doc,
			)
			continue
		doc = frappe.get_doc("CRM Notification", row.name)
		doc.read = True
		doc.save()


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
		if "has been removed by" in notification.message:
			_hash = ""
	return _hash


def _messenger_notification_lock(user, conversation):
	cache = frappe.cache
	key = cache.make_key(f"crm_messenger:notification:{user}:{conversation}")
	return cache.lock(key, timeout=30, blocking_timeout=5, thread_local=False)


def _mark_notification_read(name, user, *, conversation):
	lock = _messenger_notification_lock(user, conversation)
	acquired = bool(lock.acquire())
	if not acquired:
		return 0
	try:
		notification = frappe.get_doc("CRM Notification", name)
		if notification.to_user != user or notification.read:
			lock.release()
			return 0
		notification.read = True
		notification.save(ignore_permissions=True)
	except Exception:
		lock.release()
		raise

	_release_lock_after_transaction(lock)
	return 1


def _release_lock_after_transaction(lock):
	released = False

	def release():
		nonlocal released
		if not released:
			lock.release()
			released = True

	frappe.db.after_commit.add(release)
	frappe.db.after_rollback.add(release)
