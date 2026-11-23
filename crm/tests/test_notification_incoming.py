"""Real Communication hooks and independent Test delivery, without a mailbox."""

import frappe

from crm.notification_rules import incoming
from crm.notification_source import CRMNotifications
from crm.tests.test_notification_email_channel import TestCRMEmailChannel


class TestCRMIncoming(TestCRMEmailChannel):
	def incoming_rule(self):
		self.mail_master()
		self.save(self.all_channels(event="message_received", to_statuses=[]))

	def message(self, **values):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		doc = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "customer@example.invalid",
				"recipients": self.user,
				"subject": "Local incoming request",
				"content": "<p>Local synthetic customer message</p>",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				**values,
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{
				"notification_type_doctype": "Communication",
				"notification_type_doc": doc.name,
				"to_user": self.user,
			},
			"*",
			as_dict=True,
		)
		return doc

	def test_incoming_creates_one_history_three_channels_and_exact_message_anchor(self):
		self.incoming_rule()
		doc = self.message()
		self.assertTrue(incoming.valid(doc, self.user))
		self.assertIn(
			"crm.notification_rules.incoming.changed",
			frappe.get_hooks("doc_events")["Communication"]["after_insert"],
		)
		self.assertIsNotNone(self.notice)
		item = CRMNotifications().get(self.notice.name, self.user)
		self.assertEqual(item["route"], f"/crm/leads/{self.lead.name}#{doc.name}")
		self.assertEqual(item["event_type"], "message_received")
		message = self.deliver_bot()
		self.drain()
		self.drain_mail()
		self.assertEqual(len(self.rows()), 2)
		self.assertEqual({r.status for r in self.rows()}, {"Test Accepted"})
		self.assertEqual([r.status for r in self.mail_rows()], ["Test Accepted"])
		self.assertIsNotNone(message)

	def test_incoming_is_available_in_the_common_inbox_filter(self):
		from exp_theme.notifications.api import list_notifications

		self.incoming_rule()
		message = self.message()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		items = list_notifications(source="crm", event_type="message_received")["items"]
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["route"], f"/crm/leads/{self.lead.name}#{message.name}")
		self.assertNotIn("_crm_snapshot", items[0])

	def test_insert_update_and_hook_replay_do_not_duplicate_incoming(self):
		self.incoming_rule()
		doc = self.message()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		incoming.changed(doc)
		doc.subject = "Updated synthetic subject"
		doc.save()
		self.assertEqual(frappe.db.count("CRM Notification", {"to_user": self.user, "type": "Message"}), 1)
		self.assertEqual(len(self.rows()), 1)
		self.assertEqual(len(self.mail_rows()), 1)

	def test_outbound_email_does_not_match_incoming_rule(self):
		self.incoming_rule()
		self.message(sent_or_received="Sent")
		self.assertIsNone(self.notice)
		self.assertEqual(self.rows(), [])

	def test_unselected_record_does_not_notify(self):
		self.incoming_rule()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		other = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Other message", "lead_owner": self.user}
		).insert()
		self.message(reference_name=other.name)
		self.assertIsNone(self.notice)

	def test_deleted_message_cancels_waiting_delivery_and_hides_source(self):
		self.incoming_rule()
		doc = self.message()
		frappe.db.delete("Communication", {"name": doc.name})
		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})
		self.assertEqual({r.status for r in self.mail_rows()}, {"Cancelled"})

	def test_message_moved_to_another_record_cannot_replay_old_audience(self):
		self.incoming_rule()
		doc = self.message()
		frappe.db.set_value("Communication", doc.name, "reference_name", "missing-local-record")
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})
