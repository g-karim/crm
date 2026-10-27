from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from crm.call_analysis.automation import (
	MIN_AUTO_ANALYSIS_SECONDS,
	get_analysis_user,
	maybe_enqueue_call_analysis,
	should_auto_analyze,
)


def _call(**values):
	defaults = {
		"name": "CALL-1",
		"owner": "Administrator",
		"type": "Incoming",
		"caller": None,
		"receiver": "agent@example.com",
		"status": "Completed",
		"duration": MIN_AUTO_ANALYSIS_SECONDS,
		"recording_url": "https://recordings.example.test/call.mp3",
		"ai_analysis_status": "",
	}
	defaults.update(values)
	return SimpleNamespace(**defaults)


class TestCallAnalysisAutomation(TestCase):
	def test_only_completed_unprocessed_recordings_are_eligible(self):
		self.assertTrue(should_auto_analyze(_call()))
		self.assertFalse(should_auto_analyze(_call(status="In Progress")))
		self.assertFalse(should_auto_analyze(_call(recording_url="")))
		self.assertFalse(should_auto_analyze(_call(ai_analysis_status="Queued")))
		self.assertFalse(should_auto_analyze(_call(ai_analysis_status="Completed")))
		self.assertFalse(should_auto_analyze(_call(ai_analysis_status="Failed")))

	def test_known_short_calls_are_skipped_but_unknown_duration_is_allowed(self):
		self.assertFalse(should_auto_analyze(_call(duration=MIN_AUTO_ANALYSIS_SECONDS - 1)))
		self.assertTrue(should_auto_analyze(_call(duration=0)))
		self.assertTrue(should_auto_analyze(_call(duration=None)))

	def test_responsible_agent_is_used_for_language_and_job_owner(self):
		self.assertEqual(get_analysis_user(_call(type="Incoming")), "agent@example.com")
		self.assertEqual(
			get_analysis_user(_call(type="Outgoing", caller="seller@example.com")),
			"seller@example.com",
		)

	@patch("crm.call_analysis.provider._request")
	def test_saving_a_call_never_schedules_paid_analysis(self, request):
		self.assertIsNone(maybe_enqueue_call_analysis(_call()))
		request.assert_not_called()
