# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe import client
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from crm.api.notifications import (
	cleanup_messenger_notifications,
	get_hash,
	get_notifications,
	mark_all_as_read,
	mark_messenger_as_read,
)
from crm.fcrm.doctype.crm_notification.crm_notification import CRMNotification, has_permission
from crm.patches.v1_0.migrate_messenger_notification_aggregates import execute as migrate_aggregates

SYSTEM_MANAGER = "crm.admin@example.com"  # System Manager from crm/tests/test_records.json
USER1 = "crm.user1@example.com"
USER2 = "crm.user2@example.com"


class TestCRMNotificationPermission(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_system_manager_can_create(self):
		self.assertTrue(has_permission(make_notification(USER1), "create", SYSTEM_MANAGER))

	def test_administrator_can_create(self):
		self.assertTrue(has_permission(make_notification(USER1), "create", "Administrator"))

	def test_regular_user_cannot_create(self):
		self.assertFalse(has_permission(make_notification(USER1), "create", USER1))

	def test_regular_user_cannot_create_notification_without_to_user(self):
		self.assertFalse(has_permission(make_notification(None), "create", USER1))

	def test_recipient_can_read_own_notification(self):
		self.assertTrue(has_permission(make_notification(USER1), "read", USER1))

	def test_user_cannot_read_others_notification(self):
		self.assertFalse(has_permission(make_notification(USER2), "read", USER1))

	def test_notification_without_to_user_is_readable(self):
		self.assertTrue(has_permission(make_notification(None), "read", USER1))


def make_notification(to_user):
	doc = frappe.get_doc({"doctype": "CRM Notification", "to_user": to_user, "type": "Mention"})
	doc.flags.ignore_mandatory = True
	return doc


class TestCRMNotification(UnitTestCase):
	def test_messenger_hash_opens_conversation_tab(self):
		self.assertEqual(get_hash(frappe._dict(type="Messenger")), "#messenger")

	def test_messenger_notification_with_unknown_or_missing_reference_is_not_readable(self):
		unknown = frappe._dict(
			type="Messenger",
			to_user=USER1,
			reference_doctype="CRM Contact",
			reference_name="CONTACT-1",
		)
		self.assertFalse(has_permission(unknown, "read", USER1))

		missing = frappe._dict(
			type="Messenger",
			to_user=USER1,
			reference_doctype="CRM Lead",
			reference_name="MISSING-LEAD",
		)
		with patch.object(frappe.db, "exists", return_value=False):
			self.assertFalse(has_permission(missing, "read", USER1))

	def test_ordinary_realtime_notification_is_published_after_commit(self):
		doc = frappe._dict(
			name="NOTIFICATION-1",
			type="Mention",
			to_user="manager@example.com",
			reference_name="LEAD-1",
		)
		with patch.object(frappe, "publish_realtime") as publish:
			CRMNotification.on_update(doc)

		publish.assert_called_once_with(
			"crm_notification",
			{"name": "NOTIFICATION-1", "type": "Mention", "reference_name": "LEAD-1"},
			user="manager@example.com",
			after_commit=True,
		)


class TestMessengerNotificationLifecycle(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.lead = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": "Notification API",
				"lead_owner": "Administrator",
			}
		)
		self.lead.flags.ignore_mandatory = True
		self.lead.insert(ignore_permissions=True)
		self.conversation = frappe.get_doc(
			{
				"doctype": "Messenger Conversation",
				"provider": "telegram_bot",
				"provider_chat_key": f"crm-notification:{frappe.generate_hash(length=12)}",
				"external_chat_id": frappe.generate_hash(length=8),
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"status": "Open",
				"unread_count": 4,
			}
		).insert(ignore_permissions=True)
		self.message = frappe.get_doc(
			{
				"doctype": "Messenger Message",
				"conversation": self.conversation.name,
				"provider": "telegram_bot",
				"provider_message_key": f"crm-notification:{frappe.generate_hash(length=16)}",
				"external_chat_id": self.conversation.external_chat_id,
				"external_message_id": frappe.generate_hash(length=8),
				"direction": "inbound",
				"message_type": "text",
				"text": "Viewed message",
				"status": "received",
				"message_datetime": now_datetime(),
			}
		).insert(ignore_permissions=True)
		self.notification = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": "Administrator",
				"type": "Messenger",
				"notification_type_doctype": "Messenger Conversation",
				"notification_type_doc": self.conversation.name,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"event_count": 3,
				"last_event_at": self.message.message_datetime,
				"last_event_id": self.message.name,
				"aggregation_key": frappe.generate_hash(length=64),
			}
		).insert(ignore_permissions=True)

	def test_read_requires_exact_loaded_event_and_does_not_touch_conversation_unread(self):
		stale = mark_messenger_as_read(self.conversation.name, "OLDER-MESSAGE")
		self.assertEqual(stale["marked"], 0)
		self.assertTrue(stale["stale"])

		result = mark_messenger_as_read(self.conversation.name, self.message.name)
		self.assertEqual(result["marked"], 1)
		self.notification.reload()
		self.assertTrue(self.notification.read)
		self.assertFalse(self.notification.aggregation_key)
		self.assertEqual(
			frappe.db.get_value("Messenger Conversation", self.conversation.name, "unread_count"),
			4,
		)

	def test_notifications_response_is_bounded_and_uses_server_unread_count(self):
		result = get_notifications(limit=1000)

		self.assertLessEqual(len(result["notifications"]), 100)
		self.assertIn("has_more", result)
		self.assertGreaterEqual(result["unread_count"], 3)
		row = next(item for item in result["notifications"] if item["name"] == self.notification.name)
		self.assertEqual(row["last_event_id"], self.message.name)

	def test_revoked_lead_access_hides_messenger_notification_and_unread_count(self):
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", USER1, update_modified=False)
		frappe.set_user(USER1)
		self.assertTrue(frappe.has_permission("CRM Lead", "read", doc=self.lead))
		notification = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": USER1,
				"type": "Messenger",
				"notification_type_doctype": "Messenger Conversation",
				"notification_type_doc": self.conversation.name,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"event_count": 3,
				"last_event_at": self.message.message_datetime,
				"last_event_id": self.message.name,
				"aggregation_key": frappe.generate_hash(length=64),
			}
		).insert(ignore_permissions=True)

		visible = get_notifications()
		self.assertIn(notification.name, {row["name"] for row in visible["notifications"]})
		self.assertGreaterEqual(visible["unread_count"], notification.event_count)

		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator", update_modified=False)
		frappe.set_user(USER1)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", doc=self.lead))

		hidden = get_notifications()
		self.assertNotIn(notification.name, {row["name"] for row in hidden["notifications"]})
		self.assertEqual(hidden["unread_count"], visible["unread_count"] - notification.event_count)

	def test_revoked_read_role_hides_owned_lead_messenger_notification(self):
		user = self._make_sales_user()
		messenger, _ordinary = self._make_user_notifications(user)
		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("CRM Lead", "read", doc=self.lead))

		self._revoke_user_sales_role(user)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", doc=self.lead))

		result = get_notifications()
		self.assertNotIn(messenger.name, {row["name"] for row in result["notifications"]})

	def test_mark_all_has_no_more_when_only_inaccessible_messenger_rows_remain(self):
		user = self._make_sales_user()
		messenger, ordinary = self._make_user_notifications(user)
		self._revoke_user_sales_role(user)

		result = mark_all_as_read()

		self.assertFalse(result["has_more"])
		self.assertEqual(result["marked"], 1)
		messenger.reload()
		ordinary.reload()
		self.assertFalse(messenger.read)
		self.assertTrue(ordinary.read)

	def test_standard_list_hides_revoked_messenger_but_keeps_ordinary_notification(self):
		messenger, ordinary = self._make_user_notifications()
		frappe.set_user(USER1)
		fields = ["name", "reference_name", "notification_text", "notification_type_doc", "last_event_id"]
		filters = {"name": ["in", [messenger.name, ordinary.name]]}

		readable = client.get_list("CRM Notification", fields=fields, filters=filters)
		self.assertEqual({row.name for row in readable}, {messenger.name, ordinary.name})

		self._revoke_user_lead_access()
		hidden = client.get_list("CRM Notification", fields=fields, filters=filters)
		self.assertEqual({row.name for row in hidden}, {ordinary.name})

	def test_standard_document_read_denies_revoked_messenger_but_keeps_ordinary_notification(self):
		messenger, ordinary = self._make_user_notifications()
		frappe.set_user(USER1)
		self.assertEqual(client.get("CRM Notification", messenger.name).name, messenger.name)
		self.assertEqual(client.get("CRM Notification", ordinary.name).name, ordinary.name)

		self._revoke_user_lead_access()
		with self.assertRaises(frappe.PermissionError):
			client.get("CRM Notification", messenger.name)
		self.assertEqual(client.get("CRM Notification", ordinary.name).name, ordinary.name)

	def test_realtime_suppresses_messenger_notification_after_access_is_revoked(self):
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", USER1, update_modified=False)
		doc = frappe._dict(
			name="NOTIFICATION-1",
			type="Messenger",
			to_user=USER1,
			reference_doctype="CRM Lead",
			reference_name=self.lead.name,
			notification_text="Sensitive preview",
			notification_type_doc=self.conversation.name,
			last_event_id=self.message.name,
		)
		with (
			patch.object(type(frappe.db.after_commit), "add", autospec=True) as add_after_commit,
			patch.object(frappe, "publish_realtime") as publish,
		):
			CRMNotification.on_update(doc)
			publish.assert_not_called()
			add_after_commit.assert_called_once()
			queued_callback = add_after_commit.call_args.args[1]

			self._revoke_user_lead_access()
			queued_callback()

			publish.assert_not_called()

	def test_retention_deletes_only_expired_messenger_notifications(self):
		old = add_to_date(now_datetime(), days=-100)
		whatsapp = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": "Administrator",
				"type": "WhatsApp",
				"notification_type_doctype": "CRM Lead",
				"notification_type_doc": self.lead.name,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("CRM Notification", self.notification.name, "last_event_at", old)
		frappe.db.set_value("CRM Notification", whatsapp.name, "creation", old, update_modified=False)

		cleanup_messenger_notifications()

		self.assertFalse(frappe.db.exists("CRM Notification", self.notification.name))
		self.assertTrue(frappe.db.exists("CRM Notification", whatsapp.name))

	def test_aggregate_migration_is_idempotent(self):
		frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": "Administrator",
				"type": "Messenger",
				"notification_type_doctype": "Messenger Conversation",
				"notification_type_doc": self.conversation.name,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"event_count": 2,
				"last_event_at": add_to_date(self.message.message_datetime, minutes=-1),
			}
		).insert(ignore_permissions=True)

		# DDL causes an implicit MariaDB commit and would persist all records created
		# by setUp. Index creation is migration plumbing, not part of this aggregate test.
		with patch("crm.patches.v1_0.migrate_messenger_notification_aggregates._add_notification_index"):
			migrate_aggregates()
			migrate_aggregates()

		rows = frappe.get_all(
			"CRM Notification",
			filters={
				"to_user": "Administrator",
				"type": "Messenger",
				"notification_type_doc": self.conversation.name,
				"read": False,
			},
			fields=["event_count", "aggregation_key", "last_event_id"],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].event_count, 5)
		self.assertEqual(len(rows[0].aggregation_key), 64)
		self.assertEqual(rows[0].last_event_id, self.message.name)

	def _make_user_notifications(self, user=USER1):
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", user, update_modified=False)
		messenger = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": user,
				"type": "Messenger",
				"notification_type_doctype": "Messenger Conversation",
				"notification_type_doc": self.conversation.name,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"notification_text": "Sensitive preview",
				"last_event_id": self.message.name,
				"aggregation_key": frappe.generate_hash(length=64),
			}
		).insert(ignore_permissions=True)
		ordinary = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": user,
				"type": "Mention",
				"notification_text": "Ordinary notification",
			}
		).insert(ignore_permissions=True)
		return messenger, ordinary

	def _revoke_user_lead_access(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator", update_modified=False)
		frappe.set_user(USER1)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", doc=self.lead))

	def _make_sales_user(self):
		frappe.set_user("Administrator")
		email = f"notification-permission-{frappe.generate_hash(length=8)}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Notification Permission",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		user.add_roles("Sales User")
		return email

	def _revoke_user_sales_role(self, user):
		frappe.set_user("Administrator")
		frappe.get_doc("User", user).remove_roles("Sales User")
		frappe.clear_cache(user=user)
		frappe.set_user(user)
