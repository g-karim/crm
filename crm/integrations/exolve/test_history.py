"""Provider reads and bounded cursor recovery; no external requests or commits."""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from . import history
from .test_exolve import APP, NUMBER, SIP, fixture


class TestExolveHistory(TestCase):
	def setUp(self):
		self.now = datetime.now(timezone.utc)
		self.start = self.now - timedelta(days=3)
		self.doc = frappe._dict(state=None)
		self.settings = frappe._dict(application_id=APP)
		self.attrs = {"login": SIP, "cli": NUMBER}
		self.state = {
			"cursor": self.start.isoformat(),
			"recent": history._new_lane(self.now - timedelta(days=2), self.now),
		}

	def scan(self, client, pages=3):
		with (
			patch.object(history, "_write"),
			patch.object(frappe.db, "commit"),
			patch.object(history.api, "_save_call") as save,
		):
			history._scan(self.doc, self.state, "recent", client, self.settings, self.attrs, self.now, pages)
			return save

	def test_pages_resume_fixed_window_and_do_not_advance_on_truncation(self):
		client = MagicMock()
		client.read.return_value = {"calls": [fixture(), fixture()]}
		with patch.object(history, "PAGE_SIZE", 2):
			self.scan(client, pages=1)
			self.assertEqual(self.state["recent"]["offset"], 2)
			self.assertNotIn("recent_complete", self.state)
			client.read.return_value = {"calls": []}
			self.scan(client, pages=1)
			self.assertIsNone(self.state["recent"])
			self.assertEqual(client.read.call_args.args[1]["offset"], 2)

	def test_only_authenticated_application_sip_and_terminal_calls_reach_storage(self):
		valid = fixture()
		foreign = fixture()
		foreign["application_uuid"] = "foreign"
		running = fixture()
		running["end_time"] = ""
		client = MagicMock()
		client.read.return_value = {"calls": [valid, foreign, running]}
		save = self.scan(client)
		self.assertEqual(save.call_count, 1)

	def test_failure_does_not_advance_current_page(self):
		client = MagicMock()
		client.read.side_effect = RuntimeError("private provider body")
		with self.assertRaises(RuntimeError):
			self.scan(client)
		self.assertEqual(self.state["recent"]["offset"], 0)

	def test_empty_page_completes_history_and_preserves_cursor_boundary(self):
		self.state["history"] = history._new_lane(self.start, self.start + timedelta(days=1))
		client = MagicMock()
		client.read.return_value = {"calls": []}
		with patch.object(history, "_write"), patch.object(frappe.db, "commit"):
			history._scan(self.doc, self.state, "history", client, self.settings, self.attrs, self.now, 1)
		self.assertEqual(self.state["cursor"], (self.start + timedelta(days=1)).isoformat())
		self.assertIsNone(self.state["history"])

	def test_history_readiness_is_not_inferred_from_duration(self):
		from .utils import normalize_call

		for recording, ready, expected in [
			(False, False, "unavailable"),
			(True, False, "pending"),
			(True, True, "ready"),
		]:
			row = fixture()
			row.update(record_call=recording, voice_record_exist=ready)
			self.assertEqual(
				normalize_call(row, application_id=APP, sip_username=SIP, number=NUMBER)[
					"exolve_recording_state"
				],
				expected,
			)

	def test_disabled_server_sync_never_contacts_provider(self):
		with (
			patch.object(history.api, "is_enabled", return_value=False),
			patch.object(history.api, "_client") as client,
		):
			history.run()
			client.assert_not_called()

	def test_unexpected_success_body_does_not_mark_history_complete(self):
		client = MagicMock()
		client.read.return_value = {"error": "provider error"}
		with self.assertRaises(RuntimeError):
			self.scan(client)
		self.assertEqual(self.state["recent"]["offset"], 0)

	def test_proto_empty_object_completes_an_empty_history_page(self):
		client = MagicMock()
		client.read.return_value = {}
		self.scan(client)
		self.assertIsNone(self.state["recent"])

	def test_history_date_uses_site_timezone_and_default_is_thirty_days(self):
		with patch.object(frappe.utils, "get_system_timezone", return_value="Europe/Moscow"):
			start = history._start(frappe._dict(history_start="2026-10-20"), self.now)
			self.assertEqual(start.isoformat(), "2026-10-19T21:00:00+00:00")
		self.assertEqual(
			history._start(frappe._dict(history_start=None), self.now), self.now - timedelta(days=30)
		)
