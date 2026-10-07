from contextlib import contextmanager
from typing import ClassVar
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from twilio.request_validator import RequestValidator
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from crm.integrations.twilio import api


class TestTwilioWebhookSecurity(UnitTestCase):
	URL = "https://crm.example/api/method/crm.integrations.twilio.api.update_recording_info"
	TOKEN = "synthetic-test-token"
	PARAMS: ClassVar[dict[str, str]] = {
		"AccountSid": "AC-test",
		"CallSid": "CA-test",
		"RecordingUrl": "https://api.twilio.com/test",
	}

	@contextmanager
	def webhook(
		self, params=None, *, signature=None, request_url=None, public_url=None, method="POST", json_body=None
	):
		params = dict(self.PARAMS if params is None else params)
		url = request_url or self.URL
		builder = EnvironBuilder(
			path=url,
			method=method,
			data=params if method == "POST" and json_body is None else None,
			json=json_body,
			headers={"X-Twilio-Signature": signature} if signature else {},
		)
		request = Request(builder.get_environ())
		twilio = MagicMock(account_sid="AC-test", application_sid="AP-test")
		twilio.settings.get_password.return_value = self.TOKEN
		try:
			with (
				patch.object(frappe.local, "request", request, create=True),
				patch.object(api.Twilio, "connect", return_value=twilio),
				patch.object(api, "get_public_url", return_value=public_url or self.URL),
			):
				yield params, twilio
		finally:
			builder.close()

	def sign(self, params, url=None, token=None):
		return RequestValidator(token or self.TOKEN).compute_signature(url or self.URL, params)

	def test_accepts_signed_post(self):
		with self.webhook(signature=self.sign(self.PARAMS)) as (params, twilio):
			self.assertIs(api.validate_twilio_request(params), twilio)
			twilio.settings.get_password.assert_called_once_with("auth_token")

	def test_rejects_unsigned_request_even_with_the_correct_account(self):
		with self.webhook() as (params, _twilio), self.assertRaises(frappe.PermissionError):
			api.validate_twilio_request(params)

	def test_rejects_tampered_body(self):
		params = {**self.PARAMS, "RecordingUrl": "https://attacker.example/recording"}
		with (
			self.webhook(params, signature=self.sign(self.PARAMS)) as (args, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(args)

	def test_rejects_signature_for_another_url(self):
		signature = self.sign(self.PARAMS, url="https://other.example/callback")
		with (
			self.webhook(signature=signature) as (params, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(params)

	def test_rejects_signature_from_another_token(self):
		signature = self.sign(self.PARAMS, token="another-synthetic-token")
		with (
			self.webhook(signature=signature) as (params, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(params)

	def test_rejects_unsigned_json_body_even_with_a_valid_url_signature(self):
		with (
			self.webhook(signature=self.sign({}), json_body=self.PARAMS) as (params, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(params)

	def test_rejects_unsigned_get_body_even_with_a_valid_query_signature(self):
		url = self.URL + "?AccountSid=AC-test&CallSid=CA-test"
		with (
			self.webhook(
				signature=self.sign({}, url=url), request_url=url, method="GET", json_body=self.PARAMS
			) as (params, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(params)

	def test_rejects_methods_other_than_get_or_post(self):
		for method in ("PUT", "DELETE"):
			with (
				self.subTest(method=method),
				self.webhook(signature=self.sign({}), method=method, json_body=self.PARAMS) as (
					params,
					_twilio,
				),
				self.assertRaises(frappe.PermissionError),
			):
				api.validate_twilio_request(params)

	def test_accepts_public_https_url_behind_a_proxy(self):
		with self.webhook(
			signature=self.sign(self.PARAMS), request_url=self.URL.replace("https://", "http://")
		) as (params, twilio):
			self.assertIs(api.validate_twilio_request(params), twilio)

	def test_accepts_signed_get_with_query_parameters(self):
		url = self.URL + "?AccountSid=AC-test&CallSid=CA-test"
		with self.webhook(signature=self.sign({}, url=url), request_url=url, method="GET") as (
			params,
			twilio,
		):
			self.assertIs(api.validate_twilio_request(params), twilio)

	def test_includes_extra_form_parameters_in_signature_validation(self):
		params = {**self.PARAMS, "FutureTwilioParameter": "future-value"}
		with self.webhook(params, signature=self.sign(params)) as (_params, twilio):
			self.assertIs(api.validate_twilio_request(self.PARAMS), twilio)

	def test_rejects_signed_request_for_another_account(self):
		params = {**self.PARAMS, "AccountSid": "AC-other"}
		with (
			self.webhook(params, signature=self.sign(params)) as (args, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(args)

	def test_rejects_signed_voice_request_for_another_application(self):
		params = {**self.PARAMS, "ApplicationSid": "AP-other"}
		with (
			self.webhook(params, signature=self.sign(params)) as (args, _twilio),
			self.assertRaises(frappe.PermissionError),
		):
			api.validate_twilio_request(args, require_application_sid=True)

	def test_unsigned_webhooks_do_not_update_or_create_calls(self):
		for handler in (
			api.voice,
			api.twilio_incoming_call_handler,
			api.update_recording_info,
			api.update_call_status_info,
		):
			with (
				self.subTest(handler=handler.__name__),
				self.webhook() as (params, _twilio),
				patch.object(api, "create_call_log") as create_call,
				patch.object(api, "update_call_log") as update_call,
			):
				with self.assertRaises(frappe.PermissionError):
					handler(**params)
				create_call.assert_not_called()
				update_call.assert_not_called()
