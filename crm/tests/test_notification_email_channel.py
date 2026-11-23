"""Three independent channels and source-native email; Test transport only."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications import email_channel, policy
from exp_theme.notifications.access import event_time, internal_write
from exp_theme.notifications.push import transport
from frappe.utils import now_datetime

from crm.notification_rules import api, controls, personal_reminders
from crm.tests.test_notification_rules import TestCRMNotificationRules


class TestCRMEmailChannel(TestCRMNotificationRules):
	def mail_master(self, enabled=True):
		frappe.db.set_value("Notification Settings", self.user, "enable_email_notifications", 1)
		frappe.clear_document_cache("Notification Settings", self.user)
		s = api.get_settings()
		return controls.save_channels(
			s["masters"]["crm_push"],
			s["masters"]["one_message"],
			s["masters"]["one_push"],
			self.sender.name,
			s["revision"],
			s["master_revisions"]["crm_push"],
			s["master_revisions"]["one_message"],
			uuid4().hex,
			self.user,
			email=enabled,
		)

	def mail_rows(self):
		return frappe.get_all(
			email_channel.DOCTYPE, filters={"user": self.user, "source": "crm"}, fields=["*"]
		)

	def drain_mail(self):
		for row in self.mail_rows():
			email_channel.queue_copy(row.name)
			email_channel.queue_copy(row.name)

	def all_channels(self, **changes):
		return self.rule(
			channels={"crm_push": True, "one_message": True, "one_push": True, "email": True}, **changes
		)

	def test_three_selected_channels_deliver_independently_once(self):
		self.mail_master()
		self.save(self.all_channels())
		self.transition()
		message = self.deliver_bot()
		with (
			patch.object(transport, "send", wraps=transport.send) as send,
			patch("frappe.sendmail", side_effect=AssertionError("Real email queued")),
		):
			self.drain()
			self.drain_mail()
		self.assertEqual(send.call_count, 2)  # CRM push plus the selected One message push.
		self.assertEqual(len(self.mail_rows()), 1)
		mail = self.mail_rows()[0]
		self.assertEqual(mail.status, "Test Accepted")
		self.assertEqual(mail.recipient, self.user)
		self.assertTrue(mail.receipt)
		self.assertFalse(mail.email_queue)
		self.assertEqual(
			frappe.db.count("Raven Message", {"channel_id": message.channel_id, "is_bot_message": 1}), 1
		)
		self.assertEqual(
			email_channel.payload(mail, email_channel.eligible(mail))["route"], f"/crm/leads/{self.lead.name}"
		)

	def test_email_only_does_not_require_push_or_one(self):
		self.mail_master()
		self.primary(False)
		self.one(False)
		self.save(
			self.rule(channels={"crm_push": False, "one_message": False, "one_push": False, "email": True})
		)
		self.transition()
		self.assertEqual(self.rows(), [])
		self.assertIsNone(self.deliver_bot())
		self.drain_mail()
		self.assertEqual([r.status for r in self.mail_rows()], ["Test Accepted"])

	def test_all_combinations_of_three_channels(self):
		self.mail_master()
		for push, one, email in [
			(True, False, False),
			(False, True, False),
			(False, False, True),
			(True, True, False),
			(True, False, True),
			(False, True, True),
			(True, True, True),
		]:
			with self.subTest(push=push, one=one, email=email):
				frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
				self.lead = frappe.get_doc(
					{"doctype": "CRM Lead", "first_name": "Channel matrix", "lead_owner": self.user}
				).insert()
				self.save(
					self.rule(
						channels={"crm_push": push, "one_message": one, "one_push": one, "email": email}
					)
				)
				self.transition()
				message = self.deliver_bot()
				with patch.object(transport, "send", wraps=transport.send) as send:
					self.drain()
				self.drain_mail()
				self.assertEqual(send.call_count, int(push) + int(one))
				self.assertEqual(bool(message), one)
				rows = [r for r in self.mail_rows() if r.record_id == self.notice.name]
				self.assertEqual(len(rows), int(email))
				if email:
					self.assertEqual(rows[0].status, "Test Accepted")

	def test_legacy_three_key_rules_do_not_enable_email(self):
		self.mail_master()
		self.save(self.rule())
		self.transition()
		self.assertEqual(self.mail_rows(), [])
		self.assertFalse(api.get_settings()["configuration"]["rules"][0]["channels"]["email"])

	def test_source_replay_and_overlapping_rules_never_duplicate_email(self):
		self.mail_master()
		self.save(self.all_channels())
		self.save(self.all_channels(scope="owned", record_ids=[]))
		self.transition()
		self.drain_mail()
		original = self.mail_rows()[0]
		for _ in range(3):
			email_channel.publish("crm", self.notice.name, self.user)
		self.drain_mail()
		self.assertEqual([(r.name, r.receipt) for r in self.mail_rows()], [(original.name, original.receipt)])

	def test_pending_email_rechecks_mute_and_policy_epoch(self):
		self.mail_master()
		self.save(self.all_channels())
		self.transition()
		api.set_record(
			"CRM Lead", self.lead.name, False, True, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.drain_mail()
		self.assertEqual([r.status for r in self.mail_rows()], ["Cancelled"])

	def test_global_email_opt_out_does_not_disable_crm_or_one(self):
		self.mail_master()
		frappe.db.set_value("Notification Settings", self.user, "enable_email_notifications", 0)
		self.save(self.all_channels())
		self.transition()
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.assertEqual(len(self.rows()), 2)
		self.assertEqual(self.mail_rows(), [])

	def test_unknown_email_is_terminal(self):
		self.mail_master()
		self.save(self.all_channels())
		self.transition()
		row = self.mail_rows()[0]
		with internal_write():
			frappe.db.set_value(email_channel.DOCTYPE, row.name, "status", "Unknown")
		with patch("frappe.sendmail", side_effect=AssertionError("Unknown mail replayed")):
			self.drain_mail()
		self.assertEqual(self.mail_rows()[0].status, "Unknown")

	def test_personal_email_only_reminder_preserves_task_and_replays(self):
		task = self.task()
		self.mail_master()
		before = frappe.db.get_value("CRM Task", task.name, "*", as_dict=True)
		at = event_time(now_datetime()).replace(microsecond=0) + timedelta(hours=1)
		args = {
			"task": str(task.name),
			"at": at.isoformat(),
			"channels": {"crm_push": False, "one_message": False, "one_push": False, "email": True},
			"mutation_id": uuid4().hex,
			"expected_viewer": self.user,
		}
		result = personal_reminders.schedule(**args)
		with (
			patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 1}),
			patch.object(personal_reminders, "clock", return_value=at + timedelta(seconds=1)),
		):
			self.assertEqual(personal_reminders.run()["published"], 1)
			self.assertEqual(personal_reminders.run()["published"], 0)
			self.drain_mail()
			self.assertTrue(personal_reminders.schedule(**args)["replayed"])
		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "*", as_dict=True), before)
		self.assertEqual(len(self.mail_rows()), 1)
		self.assertEqual(self.mail_rows()[0].status, "Test Accepted")
		self.assertEqual(frappe.db.count("CRM Personal Reminder", {"user": self.user}), 1)
		self.assertEqual(result["item"]["channels"]["email"], True)

	def test_comment_all_three_channels_use_exact_source_and_one_message(self):
		self.mail_master()
		self.save(self.all_channels(event="comment_added", to_statuses=[]))
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"content": "Local email discussion",
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"notification_type_doc": comment.name, "to_user": self.user},
			"*",
			as_dict=True,
		)
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		row = self.mail_rows()[0]
		self.assertEqual(
			email_channel.payload(row, email_channel.eligible(row))["route"],
			f"/crm/leads/{self.lead.name}#{comment.name}",
		)
		self.assertEqual(row.status, "Test Accepted")
		self.assertEqual(len(self.rows()), 2)

	def test_email_recipient_change_cancels_old_dispatch(self):
		self.mail_master()
		self.save(self.all_channels())
		self.transition()
		frappe.db.set_value("User", self.user, "email", "changed-" + uuid4().hex + "@example.invalid")
		self.drain_mail()
		self.assertEqual([row.status for row in self.mail_rows()], ["Cancelled"])

	def test_test_transport_cannot_send_a_previously_queued_native_email(self):
		from types import SimpleNamespace

		self.assertFalse(
			email_channel.allowed_queue(SimpleNamespace(status="Queued"), SimpleNamespace(name="fixture"))
		)

	def test_pre_email_rule_request_hash_survives_exact_replay(self):
		from exp_theme.notifications.access import identity

		from crm.notification_rules import schema

		rule, mutation = self.rule(), uuid4().hex
		legacy_rule = schema.validate(rule, self.user)
		legacy_rule["channels"].pop("email")
		self.save(rule, revision=0, mutation=mutation)
		stored = frappe.db.get_value(policy.OPERATION, identity(self.user, "crm", mutation), "request_hash")
		self.assertEqual(stored, policy.request_identity(mutation, ["crm", {"save_rule": legacy_rule}, 0]))
		self.assertTrue(self.save(rule, revision=0, mutation=mutation)["replayed"])
		with self.assertRaises(frappe.ValidationError):
			self.save(
				{**rule, "channels": {**rule["channels"], "email": False}}, revision=0, mutation=mutation
			)
