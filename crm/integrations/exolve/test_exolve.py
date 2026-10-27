from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import frappe
import requests

from crm.integrations.exolve import api
from crm.integrations.exolve.client import ExolveClient, ExolveError
from crm.integrations.exolve.utils import log_name, normalize_call, normalize_phone

APP = "11111111-1111-4111-8111-111111111111"
SIP = "883140000000001"
NUMBER = "79990000001"
PEER = "79990000002"


def fixture():
	start = datetime.now(timezone.utc) - timedelta(minutes=2)
	return {
		"application_uuid": APP,
		"call_id": "7285581555017551200",
		"service": "sip",
		"from": SIP,
		"to": PEER,
		"direction": "outbound",
		"status": "answered",
		"start_time": start.isoformat(),
		"end_time": (start + timedelta(seconds=30)).isoformat(),
		"duration": 30,
		"legs": [{"from": NUMBER, "to": PEER, "talk_time": 12}],
		"voice_record_exist": False,
	}


class TestExolveNormalization(unittest.TestCase):
	def normalize(self, row):
		return normalize_call(row, application_id=APP, sip_username=SIP, number=NUMBER)

	def test_talk_time_and_lossless_id(self):
		result = self.normalize(fixture())
		self.assertEqual(result["duration"], 12)
		self.assertEqual(result["exolve_call_id"], "7285581555017551200")
		self.assertEqual(result["from"], NUMBER)
		self.assertEqual(result["id"], log_name(APP, "7285581555017551200"))

	def test_rejects_other_application_and_sip(self):
		for key, value in (
			("application_uuid", "other"),
			("from", "another-sip"),
			("service", "voice_message"),
		):
			row = fixture()
			row[key] = value
			self.assertIsNone(self.normalize(row))

	def test_answered_and_terminal_are_required(self):
		for key, value in (
			("status", "unspecified"),
			("end_time", ""),
			("start_time", "2026-01-01T00:00:00"),
			("call_id", str(2**64)),
		):
			row = fixture()
			row[key] = value
			self.assertIsNone(self.normalize(row))

	def test_no_answer_is_never_completed_despite_duration_or_recording(self):
		row = fixture()
		row.update(status="NO_ANSWER", voice_record_exist=True)
		result = self.normalize(row)
		self.assertEqual(result["status"], "No Answer")
		self.assertEqual(result["duration"], 0)

	def test_incoming_requires_exact_sip_leg(self):
		row = fixture()
		row.update(service="sip_redirect", direction="inbound", **{"from": PEER, "to": NUMBER})
		self.assertIsNone(self.normalize(row))
		row["legs"] = [{"to": SIP, "talk_time": 10}]
		self.assertEqual(self.normalize(row)["type"], "Incoming")

	def test_parallel_legs_do_not_double_talk_duration(self):
		row = fixture()
		row["legs"].append({"talk_time": 12})
		self.assertEqual(self.normalize(row)["duration"], 12)

	def test_phone_normalization_and_sip_injection(self):
		self.assertEqual(normalize_phone("8 (999) 000-00-01"), NUMBER)
		for raw in ("sip:attacker@example.org", "79990000001;transport=tcp", "123", "*123#"):
			with self.assertRaises(ValueError):
				normalize_phone(raw)

	def test_http_errors_never_include_provider_body_or_token(self):
		response = MagicMock(status_code=401, text="private-token")
		with patch("crm.integrations.exolve.client.requests.post", return_value=response):
			with self.assertRaises(ExolveError) as caught:
				ExolveClient("private-token").read("sips", {})
			self.assertNotIn("private-token", str(caught.exception))
		with patch(
			"crm.integrations.exolve.client.requests.post",
			side_effect=requests.ConnectionError("private-token"),
		):
			with self.assertRaises(ExolveError) as caught:
				ExolveClient("private-token").read("sips", {})
			self.assertNotIn("private-token", str(caught.exception))

	def test_recording_redirect_drops_authorization(self):
		response = MagicMock(
			status_code=302, is_redirect=True, headers={"Location": "https://cdn.example.org/audio.mp3"}
		)
		upstream = MagicMock(status_code=206)
		with (
			patch("crm.integrations.exolve.client.requests.get", return_value=response) as get,
			patch("crm.integrations.api._fetch_recording", return_value=upstream) as fetch,
		):
			self.assertIs(ExolveClient("secret").recording("123", "bytes=0-10"), upstream)
			self.assertFalse(get.call_args.kwargs["allow_redirects"])
			fetch.assert_called_once_with("https://cdn.example.org/audio.mp3", None, {"Range": "bytes=0-10"})


class TestExolveDatabase(unittest.TestCase):
	"""Run only on the dedicated local pilot; all provider traffic is mocked."""

	def setUp(self):
		self.assertTrue(frappe.conf.allow_tests)
		frappe.set_user("Administrator")
		self.settings = frappe.get_single("CRM Exolve Settings")
		self.settings.application_id = APP
		self.settings.enabled = 1
		self.settings.api_key = "unit-test-placeholder"
		self.settings.set("agents", [{"user": "Administrator", "sip_resource_id": "123", "enabled": 1}])
		self.settings.save()
		self.row = fixture()
		self.read_patch = patch.object(ExolveClient, "read", side_effect=self.provider)
		self.read_patch.start()

	def test_history_settings_do_not_request_a_sip_reconnection(self):
		result = api.save_settings(self.settings.application_id, [{"user":"Administrator","sip_resource_id":"123","enabled":1}], enabled=True, history_enabled=True)
		self.assertFalse(result["connection_changed"])
		self.assertTrue(result["history_enabled"])

	def tearDown(self):
		self.read_patch.stop()
		frappe.db.rollback()
		frappe.set_user("Administrator")

	def provider(self, operation, values):
		if operation == "sip":
			return {
				"application_uuid": APP,
				"attributes": {"login": SIP, "cli": NUMBER, "password": "unit-test-sip-secret"},
			}
		if operation == "calls":
			return {"calls": [copy.deepcopy(self.row)]}
		return {}

	def test_secrets_are_not_returned_in_settings(self):
		settings = api.get_settings()
		self.assertTrue(settings["api_key_configured"])
		self.assertNotIn("api_key", settings)
		self.assertNotIn("password", str(settings))

	def test_readiness_is_local_and_contains_no_credentials_or_other_users(self):
		with patch.object(ExolveClient, "read") as read:
			self.assertEqual(api.get_connection_status(), {"available": True, "reason": None})
			read.assert_not_called()

	def test_readiness_never_falls_back_to_another_users_mapping(self):
		self.settings.set("agents", [])
		self.settings.save()
		with patch.object(ExolveClient, "read") as read:
			self.assertEqual(api.get_connection_status(), {"available": False, "reason": "unmapped"})
			with self.assertRaises(frappe.ValidationError):
				api.get_sip_credentials()
			read.assert_not_called()

	def test_readiness_checks_disabled_integration_and_guest(self):
		self.settings.enabled = 0
		self.settings.save()
		self.assertEqual(api.get_connection_status(), {"available": False, "reason": "disabled"})
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_connection_status()

	def test_snapshot_conflict_restarts_whole_reconciliation(self):
		from werkzeug.wrappers import Request

		previous_request = getattr(frappe.local, "request", None)
		previous_cmd = frappe.form_dict.get("cmd")
		frappe.local.request = Request.from_values(method="POST")
		frappe.form_dict.cmd = "crm.integrations.exolve.api.sync_calls"
		with (
			patch.object(
				api, "_sync_calls_once", side_effect=[frappe.QueryDeadlockError("snapshot"), {"logs": []}]
			) as sync,
			patch.object(frappe.db, "rollback") as rollback,
		):
			self.assertEqual(api.sync_calls(), {"logs": []})
			self.assertEqual(sync.call_count, 2)
			rollback.assert_called_once()
		frappe.local.request = previous_request
		frappe.form_dict.cmd = previous_cmd

	def test_embedded_call_leaves_transaction_recovery_to_caller(self):
		with (
			patch.object(api, "_sync_calls_once", side_effect=frappe.QueryDeadlockError("snapshot")),
			patch.object(frappe.db, "rollback") as rollback,
		):
			with self.assertRaises(frappe.QueryDeadlockError):
				api.sync_calls()
			rollback.assert_not_called()

	def test_settings_cas_and_empty_key_retention(self):
		settings = api.get_settings()
		api.save_settings(APP, settings["agents"], True, expected_modified=settings["modified"])
		self.assertEqual(
			frappe.get_single("CRM Exolve Settings").get_password("api_key"), "unit-test-placeholder"
		)
		with self.assertRaises(frappe.TimestampMismatchError):
			api.save_settings(APP, settings["agents"], True, expected_modified="stale")

	def test_sales_user_gets_only_their_mapped_sip_and_no_manager_settings(self):
		user = "exolve-unit@example.invalid"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Exolve Unit",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			api.get_settings()
		with self.assertRaises(frappe.ValidationError):
			api.get_sip_credentials()
		frappe.set_user("Administrator")
		self.settings.set("agents", [{"user": user, "sip_resource_id": "123", "enabled": 1}])
		self.settings.save()
		frappe.set_user(user)
		self.assertEqual(api.get_sip_credentials()["username"], SIP)
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.ValidationError):
			api.get_sip_credentials()

	def test_credentials_current_mapping_only_no_store(self):
		value = api.get_sip_credentials()
		self.assertEqual(value["username"], SIP)
		self.assertEqual(frappe.local.response_headers["Cache-Control"], "no-store")
		self.settings.set("agents", [])
		self.settings.save()
		with self.assertRaises(frappe.ValidationError):
			api.get_sip_credentials()

	def test_guest_and_unauthorized_user_cannot_read_settings_or_credentials(self):
		frappe.set_user("Guest")
		for method in (api.get_settings, api.get_sip_credentials, api.sync_calls):
			with self.assertRaises(frappe.PermissionError):
				method()

	def test_provider_application_checked_before_returning_password(self):
		with patch.object(
			ExolveClient,
			"read",
			return_value={
				"application_uuid": "other",
				"attributes": {"login": SIP, "cli": NUMBER, "password": "secret"},
			},
		):
			with self.assertRaises(frappe.ValidationError):
				api.get_sip_credentials()

	def test_duplicate_sync_and_late_recording(self):
		first = api.sync_calls()["logs"][0]
		second = api.sync_calls()["logs"][0]
		self.assertEqual(first["name"], second["name"])
		self.assertEqual(frappe.db.count("CRM Call Log", {"id": first["name"]}), 1)
		self.assertFalse(second["recording_ready"])
		self.row["voice_record_exist"] = True
		self.assertTrue(api.sync_calls()["logs"][0]["recording_ready"])
		self.row["voice_record_exist"] = False
		self.assertTrue(api.sync_calls()["logs"][0]["recording_ready"])
		doc = frappe.get_doc("CRM Call Log", first["name"])
		self.assertEqual(doc.duration, 12)
		self.assertFalse(doc.ai_analysis_status)
		self.assertTrue(frappe.local.exolve_locks)
		frappe.db.rollback()
		self.assertFalse(frappe.local.exolve_locks)

	def test_client_cannot_create_or_rewrite_provider_call(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "CRM Call Log", "telephony_medium": "Exolve", "to": PEER}).insert(
				ignore_permissions=True
			)
		name = api.sync_calls()["logs"][0]["name"]
		doc = frappe.get_doc("CRM Call Log", name)
		doc.duration = 999
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_recording_download_ignores_untrusted_recording_url(self):
		self.row["voice_record_exist"] = True
		name = api.sync_calls()["logs"][0]["name"]
		doc = frappe.get_doc("CRM Call Log", name)
		doc.recording_url = "https://attacker.example.org/recording"
		with patch.object(ExolveClient, "recording", return_value="response") as download:
			self.assertEqual(api.fetch_recording(doc), "response")
			download.assert_called_once_with(self.row["call_id"], None)
		doc.exolve_call_id = "123"
		with self.assertRaises(frappe.PermissionError):
			api.fetch_recording(doc)

	def test_mapping_rejects_duplicate_sip(self):
		self.settings.append("agents", {"user": "Administrator", "sip_resource_id": "123", "enabled": 1})
		with self.assertRaises(frappe.ValidationError):
			self.settings.save()

	def test_browser_recording_decodes_adpcm_serves_ranges_and_rechecks_cached_access(self):
		import shutil
		import subprocess
		import wave
		from pathlib import Path
		from tempfile import TemporaryDirectory

		from werkzeug.wrappers import Request

		from . import recording

		if not shutil.which("ffmpeg"):
			self.skipTest("ffmpeg is required for the Exolve browser preview")
		self.row["voice_record_exist"] = True
		name = api.sync_calls()["logs"][0]["name"]
		doc = frappe.get_doc("CRM Call Log", name)
		previous_request = getattr(frappe.local, "request", None)
		try:
			with TemporaryDirectory() as work:
				root = Path(work)
				source = root / "fixture.wav"
				subprocess.run(
					[
						shutil.which("ffmpeg"),
						"-nostdin",
						"-loglevel",
						"error",
						"-f",
						"lavfi",
						"-i",
						"sine=frequency=440:sample_rate=8000:duration=0.3",
						"-ac",
						"2",
						"-c:a",
						"adpcm_ms",
						str(source),
					],
					check=True,
					timeout=10,
				)
				upstream = MagicMock()
				upstream.iter_content.return_value = iter([source.read_bytes()])
				frappe.local.request = Request.from_values(headers={"Range": "bytes=0-31"})
				with (
					patch.object(recording, "_cache_directory", return_value=root / "cache"),
					patch.object(recording, "fetch_recording", return_value=upstream) as download,
				):
					response = recording.browser_recording(doc)
					response.direct_passthrough = False
					self.assertEqual(response.status_code, 206)
					self.assertTrue(response.headers["Content-Range"].startswith("bytes 0-31/"))
					self.assertEqual(len(response.get_data()), 32)
					response.close()
					preview = next((root / "cache").glob("*-pcm-v1.wav"))
					with wave.open(str(preview)) as audio:
						self.assertEqual(
							(audio.getnchannels(), audio.getframerate(), audio.getsampwidth()), (2, 8000, 2)
						)
					self.assertEqual(preview.stat().st_mode & 0o777, 0o600)
					response = recording.browser_recording(doc)
					response.close()
					download.assert_called_once()
					frappe.set_user("Guest")
					with self.assertRaises(frappe.PermissionError):
						recording.browser_recording(doc)
		finally:
			frappe.local.request = previous_request
			frappe.set_user("Administrator")
