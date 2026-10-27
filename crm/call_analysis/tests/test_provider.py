import json
import math
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from crm.call_analysis import provider as p


class TestAnalysisProvider(TestCase):
	def test_raw_language_and_timestamps_are_not_rewritten(self):
		text = "Счёт отправим завтра. Да, согласен."
		response = {"text": text, "segments": [{"start": 0, "end": 1.5, "text": "Счёт отправим завтра."}]}
		self.assertEqual(p.transcript(response, 4), (text, response["segments"]))
		self.assertEqual(p.transcript({"text": text}, 4), (text, []))

	def test_bad_timestamps_never_become_clickable_audio_positions(self):
		for start, end in [(math.nan, 2), (-1, 2), (3, 2), (1, 200), (True, 1)]:
			with self.subTest(start=start), self.assertRaises(p.ProviderError):
				p.transcript(
					{"text": "hello", "segments": [{"start": start, "end": end, "text": "hello"}]}, 4
				)

	def test_unreported_and_nonfinite_cost_never_count_as_free(self):
		for cost in [None, -1, math.nan, math.inf, "0.1", True]:
			with self.subTest(cost=cost), self.assertRaises(p.UnknownCharge):
				p.cost({"usage": {"cost": cost}})
		self.assertEqual(p.cost({"usage": {"cost": 0}}), 0)

	@patch("crm.call_analysis.provider._request")
	def test_transcription_requests_russian_segment_timestamps(self, request):
		p.transcribe(SimpleNamespace(data=b"audio", content_type="audio/wav"))
		method, path, body = request.call_args.args
		self.assertEqual((method, path), ("POST", "/audio/transcriptions"))
		self.assertEqual(body["language"], "ru")
		self.assertEqual(body["response_format"], "verbose_json")
		self.assertEqual(body["timestamp_granularities"], ["segment"])
		self.assertNotIn("url", body["input_audio"])

	@patch("crm.call_analysis.provider._request")
	def test_summary_cannot_output_unbounded_tokens_or_ignore_price_caps(self, request):
		p.summarize("Договорились отправить счёт")
		body = request.call_args.args[2]
		self.assertEqual(body["max_tokens"], 1800)
		self.assertTrue(body["provider"]["require_parameters"])
		self.assertNotIn("transcript", body["messages"][0]["content"])

	def test_proposed_task_requires_a_real_source_quote(self):
		text = "Я отправлю счёт завтра."
		data = {
			"summary": "Обсудили счёт",
			"agreements": [],
			"tasks": [{"title": "Отправить счёт", "evidence": text}],
		}

		def response():
			return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(data)}}]}

		self.assertEqual(p.summary(response(), text), data)
		data["tasks"][0]["evidence"] = "Выдуманная фраза"
		with self.assertRaises(p.ProviderError):
			p.summary(response(), text)

	@patch("crm.call_analysis.provider._request")
	def test_dedicated_provider_daily_credit_cap_is_mandatory(self, request):
		good = {"limit": 1, "limit_remaining": 0.8, "limit_reset": "daily", "include_byok_in_limit": True}
		request.return_value = {"data": good}
		p.check_key_budget(1)
		for changes in [
			{"limit": None},
			{"limit": 2},
			{"limit_reset": "monthly"},
			{"include_byok_in_limit": False},
			{"limit_remaining": 0},
		]:
			request.return_value = {"data": {**good, **changes}}
			with self.subTest(changes=changes), self.assertRaises(p.ProviderError):
				p.check_key_budget(1)

	@patch("crm.call_analysis.provider._request")
	def test_price_changes_are_rejected_before_recording_upload(self, request):
		request.return_value = {
			"data": [{"id": p.STT_MODEL, "pricing": {"prompt": ".0001", "completion": "0"}}]
		}
		p.check_transcription_price()
		for pricing in [
			{"prompt": "1", "completion": "0"},
			{"prompt": ".0001", "completion": ".1"},
			{"prompt": "NaN", "completion": "0"},
			{"prompt": ".0001", "completion": "0", "request": "1"},
		]:
			request.return_value = {"data": [{"id": p.STT_MODEL, "pricing": pricing}]}
			with self.assertRaises(p.ProviderError):
				p.check_transcription_price()

	@patch("crm.call_analysis.provider._request")
	def test_shared_key_opt_in_checks_funds_without_mutating_provider_settings(self, request):
		def answer(method, path, payload=None):
			self.assertEqual(method, "GET")
			return (
				{"data": {"limit": None, "limit_remaining": None, "include_byok_in_limit": False}}
				if path == "/key"
				else {"data": {"total_credits": 2, "total_usage": 1}}
			)

		request.side_effect = answer
		p.check_key_budget(1, allow_shared=True, reserve=0.25)
		self.assertEqual([c.args[1] for c in request.call_args_list], ["/key", "/credits"])
		with self.assertRaises(p.ProviderError):
			p.check_key_budget(1)

	@patch("crm.call_analysis.provider._request")
	def test_shared_mode_stops_before_billing_if_key_or_account_cannot_cover_reserve(self, request):
		for key, credits in [
			({"limit": None, "limit_remaining": None}, {"total_credits": 1, "total_usage": 0.9}),
			({"limit": 1, "limit_remaining": 0.1}, {"total_credits": 2, "total_usage": 0}),
			({"limit": None, "limit_remaining": None}, {"total_credits": "NaN", "total_usage": 0}),
			(
				{"limit": None, "limit_remaining": None, "is_management_key": True},
				{"total_credits": 2, "total_usage": 0},
			),
		]:
			request.side_effect = lambda method, path, key=key, credits=credits: {
				"data": key if path == "/key" else credits
			}
			with self.subTest(key=key, credits=credits), self.assertRaises(p.ProviderError):
				p.check_key_budget(1, allow_shared=True, reserve=0.25)

	def test_entire_bounded_analysis_fits_minimum_reserve(self):
		# Worst permitted duration/rate + maximal UTF-8 input and completion cap.
		self.assertLess(0.0002 * p.MAX_AUDIO_SECONDS + p.summary_cost_bound(), 0.25)
		self.assertLess(p.summary_cost_bound("Короткая запись"), p.summary_cost_bound())
		with self.assertRaises(p.ProviderError):
			p.summary_cost_bound("x" * (p.MAX_TRANSCRIPT_BYTES + 1))
