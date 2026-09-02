from unittest import TestCase
from unittest.mock import MagicMock

from crm.call_analysis.client import (
	CallAnalysisServiceError,
	parse_analysis,
	summarize_transcript,
	transcribe_recording,
)
from crm.call_analysis.config import CallAnalysisConfig


def _config(language="Auto"):
	return CallAnalysisConfig(
		api_base_url="https://ai.example.test/v1",
		api_key="secret",
		transcription_model="speech-model",
		summary_model="summary-model",
		language=language,
		max_recording_bytes=25 * 1024 * 1024,
	)


class TestCallAnalysisClient(TestCase):
	def test_transcription_uses_multipart_and_requested_language(self):
		response = MagicMock(ok=True)
		response.json.return_value = {"text": "Здравствуйте"}
		requester = MagicMock(return_value=response)

		result = transcribe_recording(
			b"audio",
			filename="call.mp3",
			content_type="audio/mpeg",
			config=_config("Russian"),
			requester=requester,
		)

		self.assertEqual(result, "Здравствуйте")
		kwargs = requester.call_args.kwargs
		self.assertEqual(kwargs["data"]["language"], "ru")
		self.assertEqual(kwargs["files"]["file"], ("call.mp3", b"audio", "audio/mpeg"))
		self.assertNotIn("secret", str(kwargs["data"]))

	def test_parse_analysis_accepts_json_code_fence(self):
		result = parse_analysis(
			'```json\n{"summary":"Итог","key_points":["Цена"],'
			'"next_steps":["Позвонить"],"sentiment":"positive"}\n```'
		)

		self.assertEqual(result.summary, "Итог")
		self.assertEqual(result.key_points, ["Цена"])
		self.assertEqual(result.next_steps, ["Позвонить"])
		self.assertEqual(result.sentiment, "positive")

	def test_parse_analysis_rejects_invalid_or_empty_summary(self):
		with self.assertRaises(CallAnalysisServiceError):
			parse_analysis("not json")
		with self.assertRaises(CallAnalysisServiceError):
			parse_analysis('{"summary":"","key_points":[]}')

	def test_summary_prompt_forbids_invented_facts(self):
		response = MagicMock(ok=True)
		response.json.return_value = {
			"choices": [
				{
					"message": {
						"content": '{"summary":"Done","key_points":[],"next_steps":[],"sentiment":"neutral"}'
					}
				}
			]
		}
		requester = MagicMock(return_value=response)

		result = summarize_transcript("Customer asked for a quote.", config=_config(), requester=requester)

		self.assertEqual(result.summary, "Done")
		payload = requester.call_args.kwargs["json"]
		self.assertIn("do not invent", payload["messages"][0]["content"])
		self.assertIn("untrusted conversation content", payload["messages"][0]["content"])
		self.assertEqual(payload["messages"][1]["content"], "Transcript:\nCustomer asked for a quote.")
		self.assertEqual(payload["response_format"], {"type": "json_object"})
