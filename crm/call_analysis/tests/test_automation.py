from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crm.call_analysis.automation import (
	MIN_AUTO_ANALYSIS_SECONDS,
	get_analysis_user,
	maybe_enqueue_call_analysis,
	should_auto_analyze,
)
from crm.call_analysis.config import CallAnalysisConfigurationError


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

	@patch("crm.call_analysis.automation.enqueue_call_analysis")
	@patch("crm.call_analysis.automation.get_config")
	@patch("crm.call_analysis.automation.get_user_analysis_language", return_value="Russian")
	def test_eligible_call_is_queued_in_agent_language(self, get_language, get_config, enqueue):
		call_log = _call()
		enqueue.return_value = {"queued": True}

		result = maybe_enqueue_call_analysis(call_log)

		self.assertEqual(result, {"queued": True})
		get_language.assert_called_once_with("agent@example.com")
		get_config.assert_called_once_with(language="Russian")
		enqueue.assert_called_once_with(call_log, "agent@example.com", language="Russian")

	@patch("crm.call_analysis.automation.enqueue_call_analysis")
	@patch(
		"crm.call_analysis.automation.get_config",
		side_effect=CallAnalysisConfigurationError("missing key"),
	)
	@patch("crm.call_analysis.automation.get_user_analysis_language", return_value="English")
	def test_missing_server_key_does_not_break_call_save(self, _get_language, _get_config, enqueue):
		self.assertIsNone(maybe_enqueue_call_analysis(_call()))
		enqueue.assert_not_called()

	@patch("crm.call_analysis.automation.frappe.log_error")
	@patch("crm.call_analysis.automation.enqueue_call_analysis", side_effect=RuntimeError("queue down"))
	@patch("crm.call_analysis.automation.get_config")
	@patch("crm.call_analysis.automation.get_user_analysis_language", return_value="English")
	def test_queue_failure_does_not_break_call_save(self, _get_language, _get_config, _enqueue, log_error):
		with patch("crm.call_analysis.automation.frappe.get_traceback", return_value="traceback"):
			self.assertIsNone(maybe_enqueue_call_analysis(_call()))
		log_error.assert_called_once()
