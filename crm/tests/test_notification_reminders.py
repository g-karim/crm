"""Deadline lifecycle, current permissions, durable replay and independent Test channels."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications.access import event_time
from exp_theme.notifications.push import delivery, transport
from frappe.utils import now_datetime
from raven.tests.common_push_fixtures import CommonPushFixture

import crm.tests.test_notification_rules as baseline
from crm.notification_rules import api, preview, reminders, schema


class TestTaskReminders(CommonPushFixture):
	def setUp(self):
		super().setUp()
		self.flags = patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 1})
		self.flags.start()
		self.addCleanup(self.flags.stop)
		self.now = event_time(now_datetime())
		self.timer = patch.object(reminders, "clock", return_value=self.now).start()
		self.addCleanup(patch.stopall)
		patch.object(
			reminders, "now_datetime", side_effect=lambda: reminders.system_time(self.timer.return_value)
		).start()
		self.saved = self.rule()
		self.save(self.saved)

	save = baseline.TestCRMNotificationRules.save
	deliver_bot = baseline.TestCRMNotificationRules.deliver_bot

	def rule(self, **changes):
		return {
			"id": uuid4().hex,
			"name": "Deadline local rule",
			"enabled": True,
			"object": "CRM Lead",
			"event": "task_due_soon",
			"scope": "selected",
			"record_ids": [self.lead.name],
			"channels": {"crm_push": True, "one_message": True, "one_push": True},
			"include_self": False,
			"reminder_minutes": 60,
			**changes,
		}

	def task(self, due=None, **changes):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		doc = frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": "Deadline test task",
				"status": "Todo",
				"assigned_to": self.user,
				"due_date": reminders.system_time(due or self.now + timedelta(hours=2)),
				"reference_doctype": "CRM Lead",
				"reference_docname": self.lead.name,
				**changes,
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		return doc

	def fire(self, task, event="task_due_soon", minutes=60, late=1):
		self.timer.return_value = reminders.scheduled_at(task, event, minutes) + timedelta(seconds=late)
		result = reminders.run()
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"to_user": self.user, "type": "Reminder"},
			"*",
			as_dict=True,
			order_by="creation desc",
		)
		return result

	def change(self, task, **values):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		doc = frappe.get_doc("CRM Task", task.name)
		doc.update(values)
		doc.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		return doc

	def test_due_soon_one_history_one_bot_and_two_distinct_pushes(self):
		task = self.task()
		self.assertEqual(self.fire(task)["published"], 1)
		message = self.deliver_bot()
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(send.call_count, 2)
			self.assertEqual(
				{c.args[1]["url"] for c in send.call_args_list},
				{f"/crm/tasks?open={task.name}", f"/one/dm-channel/{message.channel_id}"},
			)
			self.assertEqual(len({c.args[1]["tag"] for c in send.call_args_list}), 2)
		self.assertEqual(reminders.run()["published"], 0)
		self.assertEqual(frappe.db.count("CRM Notification", {"to_user": self.user, "type": "Reminder"}), 1)
		self.assertEqual({row.status for row in self.rows()}, {"Test Accepted"})

	def test_overlapping_rules_do_not_add_intents(self):
		self.save(self.rule())
		self.fire(self.task())
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 2)

	def test_due_soon_and_overdue_are_independent_events(self):
		value = self.rule(event="task_overdue")
		value.pop("reminder_minutes")
		self.save(value)
		task = self.task()
		self.fire(task)
		self.deliver_bot()
		self.drain()
		self.fire(task, "task_overdue", 0)
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 4)
		self.assertEqual(frappe.db.count("CRM Notification", {"to_user": self.user, "type": "Reminder"}), 2)

	def test_two_offsets_are_distinct_selected_reminder_times(self):
		self.save(self.rule(reminder_minutes=15))
		task = self.task()
		self.fire(task)
		self.deliver_bot()
		self.drain()
		self.fire(task, minutes=15)
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 4)

	def test_no_notification_before_scheduled_time(self):
		task = self.task()
		self.assertEqual(self.fire(task, late=-1)["published"], 0)

	def test_expired_schedule_is_not_backfilled(self):
		task = self.task()
		self.assertEqual(self.fire(task, late=15 * 60)["published"], 0)

	def test_new_rule_does_not_backfill_recently_missed_time(self):
		self.task(due=self.now + timedelta(minutes=59))
		self.timer.return_value = self.now + timedelta(seconds=1)
		self.assertEqual(reminders.run()["published"], 0)

	def test_no_deadline_no_recipient_and_closed_tasks_do_not_fire(self):
		for changes in [
			{"due_date": None},
			{"assigned_to": None},
			{"status": "Done"},
			{"status": "Canceled"},
		]:
			self.task(**changes)
		self.timer.return_value = self.now + timedelta(hours=1, seconds=1)
		self.assertEqual(reminders.run()["published"], 0)

	def test_completed_task_cancels_both_queued_channels(self):
		task = self.task()
		self.fire(task)
		self.change(task, status="Done")
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_postponed_deadline_cancels_old_and_can_fire_at_new_time(self):
		task = self.task()
		self.fire(task)
		new = self.change(task, due_date=reminders.system_time(self.now + timedelta(hours=4)))
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual(self.fire(new)["published"], 1)
		self.deliver_bot()
		self.drain()
		self.assertEqual(
			sorted(r.status for r in self.rows()), ["Cancelled", "Test Accepted", "Test Accepted"]
		)

	def test_returning_to_old_due_date_does_not_revive_old_queue(self):
		task = self.task()
		self.fire(task)
		self.change(task, due_date=reminders.system_time(self.now + timedelta(hours=4)))
		self.change(task, due_date=task.due_date)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual(reminders.run()["published"], 0)

	def test_reopening_does_not_backfill_an_already_fired_reminder(self):
		task = self.task()
		self.fire(task)
		self.change(task, status="Done")
		self.change(task, status="Todo")
		self.assertEqual(reminders.run()["published"], 0)
		self.assertIsNone(self.deliver_bot())

	def test_ordinary_edit_does_not_change_schedule_identity(self):
		task = self.task()
		self.fire(task)
		new = self.change(task, title="Edited title", status="In Progress", exp_reminder_epoch=987654)
		self.assertEqual(new.exp_reminder_epoch, task.exp_reminder_epoch)
		self.assertEqual(reminders.run()["published"], 0)
		self.assertIsNotNone(self.deliver_bot())

	def test_one_push_rechecks_task_after_bot_message_was_created(self):
		task = self.task()
		self.fire(task)
		self.deliver_bot()
		self.change(task, status="Canceled")
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_parent_current_status_is_rechecked_before_delivery(self):
		self.save({**self.saved, "statuses": [self.lead.status]})
		task = self.task()
		self.fire(task)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		other = (
			frappe.get_doc(
				{
					"doctype": "CRM Lead Status",
					"lead_status": "Reminder ongoing " + uuid4().hex[:8],
					"type": "Ongoing",
				}
			)
			.insert()
			.name
		)
		lead = frappe.get_doc("CRM Lead", self.lead.name)
		lead.status = other
		lead.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def test_revoked_parent_access_cancels_delivery_and_hides_history(self):
		task = self.task()
		self.fire(task)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "_assign", "[]")
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.clear_cache(user=self.user)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		from crm.notification_source import CRMNotifications

		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def test_deleted_task_cancels_queue(self):
		task = self.task()
		self.fire(task)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		# A trusted source cleanup can remove a task while retaining its audit history.
		frappe.db.delete("CRM Task", {"name": task.name})
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def test_record_mute_and_policy_change_cancel_queued_reminders(self):
		task = self.task()
		self.fire(task)
		api.set_record(
			"CRM Lead", self.lead.name, False, True, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual(reminders.run()["published"], 0)

	def test_terminal_unknown_is_never_resent_after_rule_changes(self):
		task = self.task()
		self.fire(task)
		self.deliver_bot()
		row = next(r for r in self.rows() if r.channel == "source_push")
		delivery.claim_and_enqueue(row.name)
		token = frappe.db.get_value(delivery.DOCTYPE, row.name, "lease_token")
		with patch.object(transport, "send", side_effect=transport.PushOutcomeUnknown()):
			delivery.send_claimed(row.name, token)
		self.save({**self.saved, "enabled": False})
		self.save(self.saved)
		with patch.object(transport, "send", side_effect=AssertionError("Unknown replay")):
			delivery.claim_and_enqueue(row.name)
			delivery.send_claimed(row.name, token)
		self.assertEqual(frappe.db.get_value(delivery.DOCTYPE, row.name, "status"), "Unknown")

	def test_one_message_without_push_and_primary_opt_out(self):
		self.save({**self.saved, "channels": {"crm_push": False, "one_message": True, "one_push": False}})
		self.fire(self.task())
		message = self.deliver_bot()
		self.drain()
		self.assertIsNotNone(message)
		self.assertEqual(self.rows(), [])

	def test_reassignment_cancels_the_old_recipient_queue(self):
		task = self.task()
		self.fire(task)
		self.change(task, assigned_to="Administrator")
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_linked_deal_task_uses_its_parent_pipeline_and_stage(self):
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_owner": self.user}).insert()
		self.save(
			self.rule(
				object="CRM Deal", record_ids=[deal.name], pipelines=[deal.pipeline], statuses=[deal.status]
			)
		)
		task = self.task(reference_doctype="CRM Deal", reference_docname=deal.name)
		self.fire(task)
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 2)

	def test_masters_off_keeps_history_without_sending(self):
		self.primary(False)
		self.one(False)
		self.fire(self.task())
		self.assertIsNotNone(self.notice)
		self.assertIsNone(self.deliver_bot())
		self.assertEqual(self.rows(), [])

	def test_no_reminder_rule_does_not_enable_a_new_category(self):
		api.delete_rule(self.saved["id"], api.get_settings()["revision"], uuid4().hex, self.user)
		task = self.task()
		self.assertEqual(self.fire(task)["published"], 0)

	def test_feature_is_off_by_default_and_pause_cancels_pending(self):
		task = self.task()
		self.fire(task)
		with patch.dict(frappe.conf, {"exp_crm_reminders_enabled": 0}):
			self.assertEqual(reminders.run()["published"], 0)
			self.assertIsNone(self.deliver_bot())
			self.drain()

	def test_delivery_expires_if_processing_resumes_too_late(self):
		task = self.task()
		self.fire(task)
		self.timer.return_value += timedelta(minutes=16)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_a_task_created_by_its_own_assignee_still_gets_a_system_reminder(self):
		task = frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": "My own task",
				"status": "Todo",
				"assigned_to": self.user,
				"due_date": reminders.system_time(self.now + timedelta(hours=2)),
				"reference_doctype": "CRM Lead",
				"reference_docname": self.lead.name,
			}
		).insert()
		self.assertEqual(self.fire(task)["published"], 1)

	def test_standalone_task_reminder_has_exact_native_crm_route(self):
		task = self.task(reference_doctype=None, reference_docname=None)
		self.save(self.rule(object="CRM Task", record_ids=[str(task.name)]))
		self.fire(task)
		from crm.notification_source import CRMNotifications

		item = CRMNotifications().get(self.notice.name, self.user)
		self.assertEqual(item["route"], f"/crm/tasks?open={task.name}")
		self.assertEqual(item["push_route"], item["route"])

	def test_preview_shows_actual_assigned_tasks_and_future_localized_time(self):
		task = self.task()
		before = frappe.db.count("CRM Notification")
		value = preview.preview_rule(self.saved, self.user)
		self.assertEqual([r["id"] for r in value["items"]], [str(task.name)])
		self.assertEqual(value["items"][0]["label"], task.title)
		self.assertEqual(
			event_time(value["items"][0]["scheduled_at"]), reminders.scheduled_at(task, "task_due_soon", 60)
		)
		self.assertEqual(before, frappe.db.count("CRM Notification"))

	def test_validator_limits_offsets_and_keeps_manual_self_setting_out(self):
		for changes in [
			{"reminder_minutes": 0},
			{"reminder_minutes": True},
			{"reminder_minutes": 10080},
			{"include_self": True},
		]:
			with self.assertRaises(frappe.ValidationError):
				schema.validate(self.rule(**changes), self.user)

	def test_pagination_has_no_first_page_starvation(self):
		for _ in range(5):
			self.task()
		self.timer.return_value = self.now + timedelta(hours=1, seconds=1)
		with patch.object(reminders, "PAGE_SIZE", 2):
			self.assertEqual(reminders.run()["published"], 5)
			self.assertEqual(reminders.run()["published"], 0)

	def test_real_duration_uses_site_timezone_across_dst(self):
		with patch("exp_theme.notifications.access.get_system_timezone", return_value="Europe/Berlin"):
			value = reminders.scheduled_at(frappe._dict(due_date="2026-03-29 03:30:00"), "task_due_soon", 60)
			self.assertEqual(value.isoformat(), "2026-03-29T00:30:00+00:00")

	def test_scheduler_uses_bounded_whole_job_retry_and_preserves_inline_callers(self):
		previous = getattr(frappe.local, "job", None)
		try:
			frappe.local.job = frappe._dict(
				method="crm.notification_rules.reminders.run", job_name=uuid4().hex, kwargs={}
			)
			with patch.object(
				reminders, "_phases", side_effect=[frappe.QueryDeadlockError("artificial"), []]
			):
				with self.assertRaises(frappe.RetryBackgroundJobError):
					reminders.run()
				self.assertEqual(reminders.run()["published"], 0)
			frappe.local.job = None
			with (
				patch.object(reminders, "_phases", side_effect=frappe.QueryDeadlockError("artificial")),
				patch.object(frappe.db, "rollback") as rollback,
			):
				with self.assertRaises(frappe.QueryDeadlockError):
					reminders.run()
				rollback.assert_not_called()
		finally:
			frappe.local.job = previous
