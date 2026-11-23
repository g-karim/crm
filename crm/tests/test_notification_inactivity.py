"""Activity epochs cancel outdated inactivity reminders; Test delivery only."""

from datetime import timedelta
from unittest.mock import patch

import frappe
from exp_theme.notifications.access import event_time
from frappe.utils import now_datetime

from crm.notification_rules import inactivity
from crm.notification_rules.reminders import system_time
from crm.tests.test_notification_email_channel import TestCRMEmailChannel


class TestCRMInactivity(TestCRMEmailChannel):
	def setUp(self):
		super().setUp()
		self.mail_master()
		self.now = event_time(now_datetime())
		self.save(self.all_channels(event="record_inactive", inactive_minutes=60, to_statuses=[]))
		self.flags = patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 1})
		self.flags.start()
		self.addCleanup(self.flags.stop)
		self.timer = patch.object(
			inactivity, "clock", return_value=self.now + timedelta(minutes=60, seconds=1)
		)
		self.clock = self.timer.start()
		self.addCleanup(self.timer.stop)
		frappe.db.set_value(
			"CRM Lead", self.lead.name, {inactivity.FIELD: system_time(self.now), inactivity.EPOCH: 2}
		)

	def fire(self):
		result = inactivity.run()
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"to_user": self.user, "type": "Reminder", "reference_name": self.lead.name},
			"*",
			as_dict=True,
		)
		return result

	def test_due_inactivity_delivers_three_channels_once(self):
		self.assertEqual(self.fire()["published"], 1)
		self.assertEqual(self.fire()["published"], 0)
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		self.assertEqual({r.status for r in self.rows()}, {"Test Accepted"})
		self.assertEqual({r.status for r in self.mail_rows()}, {"Test Accepted"})

	def test_new_activity_cancels_waiting_delivery(self):
		self.fire()
		frappe.db.set_value(
			"CRM Lead",
			self.lead.name,
			{inactivity.FIELD: system_time(self.clock.return_value), inactivity.EPOCH: 3},
		)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})
		self.assertEqual({r.status for r in self.mail_rows()}, {"Cancelled"})

	def test_not_yet_due_is_silent(self):
		self.clock.return_value = self.now + timedelta(minutes=59)
		self.assertEqual(self.fire()["published"], 0)
		self.assertIsNone(self.notice)

	def test_expired_window_does_not_backfill(self):
		self.clock.return_value = self.now + timedelta(minutes=76)
		self.assertEqual(self.fire()["published"], 0)

	def test_paused_processing_cannot_publish(self):
		with patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 0}):
			self.assertEqual(self.fire()["published"], 0)

	def test_native_comment_advances_parent_activity_epoch(self):
		before = frappe.db.get_value("CRM Lead", self.lead.name, inactivity.EPOCH)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"content": "Local new activity",
			}
		).insert()
		self.assertGreater(frappe.db.get_value("CRM Lead", self.lead.name, inactivity.EPOCH), before)

	def test_revoked_record_access_cannot_deliver(self):
		self.fire()
		frappe.db.set_value("CRM Lead", self.lead.name, {"lead_owner": "Administrator", "_assign": "[]"})
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.clear_cache(user=self.user)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})
