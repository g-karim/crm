"""Independent reminder time, replay, current permission and atomic Test delivery."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications.access import event_time
from exp_theme.notifications.push import transport
from frappe.utils import now_datetime
from raven.tests.common_push_fixtures import CommonPushFixture

import crm.tests.test_notification_rules as baseline
from crm.notification_rules import api
from crm.notification_rules import personal_reminders as personal
from crm.notification_source import CRMNotifications


class TestPersonalReminders(CommonPushFixture):
	def test_optional_theme_absence_keeps_scheduler_safe(self):
		with patch("frappe.get_installed_apps", return_value=["frappe", "crm"]):
			self.assertEqual(personal.run()["published"], 0)

	def test_task_reassignment_does_not_change_the_person_who_requested_reminder(self):
		self.schedule()
		frappe.db.set_value("CRM Task", self.task_doc.name, "assigned_to", "Administrator")
		self.assertEqual(self.fire()["published"], 1)
		self.assertEqual(self.notice.to_user, self.user)

	def test_deleted_task_cancels_waiting_delivery(self):
		self.schedule()
		self.fire()
		frappe.db.delete("CRM Task", {"name": self.task_doc.name})
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_revoked_parent_access_cancels_and_hides_history(self):
		self.schedule()
		self.fire()
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "_assign", "[]")
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.clear_cache(user=self.user)
		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def setUp(self):
		super().setUp()
		self.save(
			{
				"id": uuid4().hex,
				"name": "Silent base",
				"enabled": False,
				"object": "CRM Lead",
				"event": "comment_added",
				"scope": "selected",
				"record_ids": [self.lead.name],
				"channels": {"crm_push": True, "one_message": False, "one_push": False},
			}
		)
		self.flags = patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 1})
		self.flags.start()
		self.addCleanup(self.flags.stop)
		self.now = event_time(now_datetime()).replace(microsecond=0)
		self.timer = patch.object(personal, "clock", return_value=self.now).start()
		self.addCleanup(patch.stopall)
		self.task_doc = self.task()
		self.channels = {"crm_push": True, "one_message": True, "one_push": True}
		self.at = self.now + timedelta(hours=2)

	save = baseline.TestCRMNotificationRules.save
	deliver_bot = baseline.TestCRMNotificationRules.deliver_bot

	def schedule(self, **values):
		args = {
			"task": str(self.task_doc.name),
			"at": self.at.isoformat(),
			"channels": self.channels,
			"mutation_id": uuid4().hex,
			"expected_viewer": self.user,
			**values,
		}
		self.args = args
		result = personal.schedule(**args)
		self.reminder = result["item"]
		return result

	def fire(self):
		self.timer.return_value = self.at + timedelta(seconds=1)
		result = personal.run()
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"last_event_id": "crm-personal-reminder:" + self.reminder["id"]},
			"*",
			as_dict=True,
		)
		return result

	def test_task_without_deadline_fires_at_independent_time(self):
		self.assertIsNone(self.task_doc.due_date)
		self.schedule()
		self.assertEqual(self.fire()["published"], 1)
		message = self.deliver_bot()
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(send.call_count, 2)
			self.assertEqual(
				{c.args[1]["url"] for c in send.call_args_list},
				{f"/crm/tasks?open={self.task_doc.name}", f"/one/dm-channel/{message.channel_id}"},
			)
			self.assertEqual(len({c.args[1]["tag"] for c in send.call_args_list}), 2)

	def test_scheduling_does_not_change_task_or_channel_settings(self):
		before = frappe.db.get_value("CRM Task", self.task_doc.name, "*", as_dict=True)
		settings = api.get_settings()
		self.schedule()
		self.assertEqual(before, frappe.db.get_value("CRM Task", self.task_doc.name, "*", as_dict=True))
		self.assertEqual(settings, api.get_settings())

	def test_changing_deadline_does_not_move_or_cancel_personal_reminder(self):
		self.schedule()
		frappe.db.set_value("CRM Task", self.task_doc.name, "due_date", now_datetime() + timedelta(days=5))
		self.assertEqual(self.fire()["published"], 1)
		frappe.db.set_value("CRM Task", self.task_doc.name, "due_date", None)
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Test Accepted"})

	def test_exact_request_replay_never_creates_second_reminder_even_after_time_passes(self):
		self.schedule()
		args = self.args.copy()
		self.fire()
		result = personal.schedule(**args)
		self.assertTrue(result["replayed"])
		self.assertEqual(result["item"]["id"], self.reminder["id"])
		self.assertEqual(personal.run()["published"], 0)

	def test_same_request_id_with_changed_payload_is_rejected(self):
		self.schedule()
		with self.assertRaises(frappe.ValidationError):
			personal.schedule(**{**self.args, "at": (self.at + timedelta(hours=1)).isoformat()})

	def test_cancel_before_time_is_idempotent_and_schedule_replay_cannot_revive(self):
		self.schedule()
		args = self.args.copy()
		for _ in range(2):
			personal.cancel(self.reminder["id"], 1, self.user)
		self.assertEqual(personal.schedule(**args)["item"]["state"], "Cancelled")
		self.assertEqual(self.fire()["published"], 0)

	def test_cancel_after_fire_stops_waiting_channels_but_preserves_history(self):
		self.schedule()
		self.fire()
		personal.cancel(self.reminder["id"], 2, self.user)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertTrue(frappe.db.exists("CRM Notification", self.notice.name))
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_stale_cancel_version_does_not_overwrite_fired_state(self):
		self.schedule()
		self.fire()
		with self.assertRaises(frappe.TimestampMismatchError):
			personal.cancel(self.reminder["id"], 1, self.user)

	def test_task_completion_cancels_scheduled_reminder(self):
		self.schedule()
		frappe.db.set_value("CRM Task", self.task_doc.name, "status", "Done")
		self.assertEqual(self.fire()["published"], 0)
		self.assertEqual(frappe.db.get_value(personal.DOCTYPE, self.reminder["id"], "state"), "Cancelled")

	def test_completion_between_message_and_its_push_cancels_both_pushes(self):
		self.schedule()
		self.fire()
		self.deliver_bot()
		frappe.db.set_value("CRM Task", self.task_doc.name, "status", "Done")
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_no_early_delivery_and_expired_time_is_not_backfilled(self):
		self.schedule()
		self.assertEqual(personal.run()["published"], 0)
		self.timer.return_value = self.at + timedelta(minutes=16)
		self.assertEqual(personal.run()["published"], 0)
		self.assertEqual(frappe.db.get_value(personal.DOCTYPE, self.reminder["id"], "state"), "Expired")

	def test_invalid_dates_timezone_and_channels_are_rejected(self):
		for values in [
			{"at": self.now.isoformat()},
			{"at": "2026-10-27T15:00"},
			{"at": "invalid"},
			{"at": (self.now + timedelta(days=367)).isoformat()},
			{"channels": {"crm_push": False, "one_message": False, "one_push": True}},
		]:
			with self.assertRaises(frappe.ValidationError):
				self.schedule(**values)

	def test_timezone_offset_is_normalized_to_same_instant(self):
		from datetime import timezone

		self.schedule(at=self.at.astimezone(timezone(timedelta(hours=3))).isoformat())
		self.assertEqual(event_time(self.reminder["at"]), self.at)

	def test_session_change_cannot_schedule_for_previous_user(self):
		with self.assertRaises(frappe.AuthenticationError):
			self.schedule(expected_viewer="Administrator")

	def test_another_user_cannot_list_or_cancel_my_reminder(self):
		self.schedule()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		self.assertEqual(personal.list_reminders(str(self.task_doc.name), "Administrator")["items"], [])
		with self.assertRaises(frappe.PermissionError):
			personal.cancel(self.reminder["id"], 1, "Administrator")

	def test_generic_crud_cannot_forge_or_edit_reminder(self):
		self.schedule()
		from frappe.client import set_value

		with self.assertRaises(frappe.PermissionError):
			set_value(personal.DOCTYPE, self.reminder["id"], "state", "Fired")

	def test_muted_record_and_current_access_still_win(self):
		self.schedule()
		api.set_record(
			"CRM Lead", self.lead.name, False, True, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.assertEqual(self.fire()["published"], 0)

	def test_main_channels_off_are_not_enabled_by_scheduling(self):
		self.primary(False)
		self.one(False)
		self.schedule()
		self.fire()
		self.assertIsNone(self.deliver_bot())
		self.assertEqual(self.rows(), [])

	def test_message_only_does_not_add_its_push(self):
		self.schedule(channels={"crm_push": False, "one_message": True, "one_push": False})
		self.fire()
		self.assertIsNotNone(self.deliver_bot())
		self.assertEqual(self.rows(), [])

	def test_feature_off_prevents_sweep_and_pending_delivery(self):
		self.schedule()
		self.fire()
		with patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 0}):
			self.assertEqual(personal.run()["published"], 0)
			self.assertIsNone(self.deliver_bot())
			self.drain()

	def test_unknown_push_is_terminal_after_job_replay(self):
		self.schedule()
		self.fire()
		frappe.db.set_value("EXP Push Delivery", self.rows()[0].name, "status", "Unknown")
		self.assertEqual(personal.run()["published"], 0)
		with patch.object(transport, "send") as send:
			self.drain()
			send.assert_not_called()

	def test_rollback_covers_reminder_fired_state_history_and_outboxes(self):
		self.schedule()
		frappe.db.savepoint("personal_fire")
		self.fire()
		frappe.db.rollback(save_point="personal_fire")
		self.assertEqual(frappe.db.get_value(personal.DOCTYPE, self.reminder["id"], "state"), "Scheduled")
		self.assertEqual(self.rows(), [])
