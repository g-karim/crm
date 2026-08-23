# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_to_date, now_datetime

from crm.api.notifications import (
	cleanup_messenger_notifications,
	get_hash,
	get_notifications,
	mark_messenger_as_read,
)
from crm.fcrm.doctype.crm_notification.crm_notification import CRMNotification
from crm.patches.v1_0.migrate_messenger_notification_aggregates import execute as migrate_aggregates


class TestCRMNotification(UnitTestCase):
	def test_messenger_hash_opens_conversation_tab(self):
		self.assertEqual(get_hash(frappe._dict(type="Messenger")), "#messenger")

	def test_realtime_notification_is_published_after_commit(self):
		doc = frappe._dict(
			name="NOTIFICATION-1",
			type="Messenger",
			to_user="manager@example.com",
			reference_name="LEAD-1",
		)
		with patch.object(frappe, "publish_realtime") as publish:
			CRMNotification.on_update(doc)

		publish.assert_called_once_with(
			"crm_notification",
			{"name": "NOTIFICATION-1", "type": "Messenger", "reference_name": "LEAD-1"},
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
