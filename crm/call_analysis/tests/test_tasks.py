from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from crm.call_analysis.client import AnalysisResult
from crm.call_analysis.config import CallAnalysisConfig
from crm.call_analysis.tasks import run_call_analysis
from crm.fcrm.doctype.crm_call_log.test_crm_call_log import create_test_call_log


def _config():
	return CallAnalysisConfig(
		api_base_url="https://ai.example.test/v1",
		api_key="secret",
		proxy_url="",
		transcription_model="speech-model",
		summary_model="summary-model",
		language="Russian",
		max_recording_bytes=1024,
	)


class TestCallAnalysisTasks(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	@patch("crm.call_analysis.tasks._publish")
	@patch("crm.call_analysis.tasks.summarize_transcript")
	@patch("crm.call_analysis.tasks.transcribe_recording", return_value="Полная расшифровка")
	@patch("crm.call_analysis.tasks.download_recording")
	@patch("crm.call_analysis.tasks.get_config", return_value=_config())
	def test_worker_persists_transcript_and_summary(
		self,
		_get_config,
		download,
		_transcribe,
		summarize,
		_publish,
	):
		call_log = create_test_call_log(recording_url="https://cdn.example.test/call.mp3")
		download.return_value = SimpleNamespace(
			data=b"audio",
			filename="call.mp3",
			content_type="audio/mpeg",
		)
		summarize.return_value = AnalysisResult(
			transcript="Полная расшифровка на выбранном языке",
			summary="Краткий итог",
			key_points=["Обсудили цену"],
			next_steps=["Отправить предложение"],
			sentiment="positive",
		)

		result = run_call_analysis(call_log.name, user="Administrator", language="Russian")

		call_log.reload()
		self.assertEqual(result["status"], "Completed")
		self.assertEqual(call_log.ai_analysis_status, "Completed")
		self.assertEqual(call_log.ai_transcript, "Полная расшифровка на выбранном языке")
		self.assertEqual(call_log.ai_summary, "Краткий итог")
		self.assertEqual(frappe.parse_json(call_log.ai_key_points), ["Обсудили цену"])
		self.assertEqual(frappe.parse_json(call_log.ai_next_steps), ["Отправить предложение"])
		self.assertEqual(call_log.ai_sentiment, "positive")
		self.assertEqual(call_log.ai_analysis_language, "Russian")
		_get_config.assert_called_once_with(language="Russian")

	@patch("crm.call_analysis.tasks._publish")
	@patch("crm.call_analysis.tasks.download_recording", side_effect=RuntimeError("temporary failure"))
	@patch("crm.call_analysis.tasks.get_config", return_value=_config())
	@patch("crm.call_analysis.tasks.frappe.log_error")
	def test_worker_records_safe_failure(self, _log_error, _get_config, _download, _publish):
		call_log = create_test_call_log(recording_url="https://cdn.example.test/call.mp3")

		result = run_call_analysis(call_log.name, user="Administrator", language="English")

		call_log.reload()
		self.assertEqual(result["status"], "Failed")
		self.assertEqual(call_log.ai_analysis_status, "Failed")
		self.assertEqual(
			call_log.ai_analysis_error,
			"The AI service could not analyze this recording. Please try again.",
		)
