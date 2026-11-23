from datetime import datetime, time, timezone
import unittest

from crm.analytics.call_sla import WorkingHours, callback_state, completed_callback_state


class TestCallSla(unittest.TestCase):
	def setUp(self):
		self.hours = WorkingHours("Europe/Moscow", (0, 1, 2, 3, 4), time(9), time(18))

	def test_deadline_carries_work_across_weekend_and_month(self):
		missed = datetime.fromisoformat("2026-10-30T17:45:00+03:00")
		deadline = self.hours.deadline(missed, 60)
		self.assertEqual(deadline.isoformat(), "2026-11-02T09:45:00+03:00")
		self.assertEqual(callback_state(deadline, deadline), "pending")
		self.assertEqual(callback_state(deadline, deadline, deadline), "on_time")
		later = datetime.fromisoformat("2026-11-02T10:00:00+03:00")
		self.assertEqual(callback_state(deadline, later), "overdue")
		self.assertEqual(callback_state(deadline, later, later), "late")

	def test_after_hours_starts_with_next_shift(self):
		missed = datetime.fromisoformat("2026-11-02T18:01:00+03:00")
		self.assertEqual(self.hours.deadline(missed, 10).isoformat(), "2026-11-03T09:10:00+03:00")

	def test_clock_change_measures_real_working_minutes(self):
		hours = WorkingHours("Europe/Berlin", (6,), time(1), time(5))
		missed = datetime(2026, 10, 25, 0, 50, tzinfo=timezone.utc)
		self.assertEqual(hours.deadline(missed, 60).isoformat(), "2026-10-25T02:50:00+01:00")

	def test_unknown_deadline_stays_unknown(self):
		self.assertEqual(callback_state(None, datetime.now(timezone.utc)), "unavailable")

	def test_reply_crossing_deadline_requires_answer_time(self):
		start = datetime.fromisoformat("2026-11-02T09:14:30+03:00")
		deadline = datetime.fromisoformat("2026-11-02T09:15:00+03:00")
		answer = datetime.fromisoformat("2026-11-02T09:16:00+03:00")
		end = datetime.fromisoformat("2026-11-02T09:17:00+03:00")
		self.assertEqual(completed_callback_state(deadline, end, start, end, answer), "late")
		self.assertEqual(completed_callback_state(deadline, end, start, end), "unavailable")
		self.assertEqual(completed_callback_state(deadline, end, start, None), "unavailable")
		self.assertEqual(completed_callback_state(deadline, end, start, deadline), "on_time")
		self.assertEqual(completed_callback_state(deadline, end, answer, None), "late")
