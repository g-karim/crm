"""Read-only contract checks against the isolated source-event import fixture."""

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import frappe

from crm.analytics.source_event_import import check_event_order, event_instant, parse_event


ROOT = Path(__file__).resolve().parents[4]
SITE = "crm-analytics-regression-h05event.localhost"


class TestSourceEventImport(unittest.TestCase):
	def setUp(self):
		self.old_cwd = Path.cwd()
		os.chdir(ROOT / "sites")
		frappe.init(site=SITE, sites_path=str(ROOT / "sites"))
		frappe.connect()
		frappe.set_user("Administrator")
		self.deal = json.loads((ROOT / "evidence/fixture-h05event.json").read_text())["deals"]["D4"]
		self.before = frappe.db.count("CRM Analytics Event")

	def tearDown(self):
		self.assertEqual(frappe.db.count("CRM Analytics Event"), self.before)
		frappe.db.rollback()
		frappe.destroy()
		os.chdir(self.old_cwd)

	def event(self, event_id, at):
		return parse_event("analytics-h05-feed", "D4-source", event_id, at)

	def test_utc_offset_normalization_preserves_source_instant(self):
		self.assertEqual(str(self.event("evt-023", "2026-10-26T16:00:00+03:00").occurred_at),
			"2026-10-26 13:00:00")
		self.assertEqual(self.event("evt-023", "2026-10-26T13:00:00Z").key(),
			self.event("evt-023", "2026-10-26T16:00:00+03:00").key())

	def test_missing_identity_bad_id_naive_or_future_time_are_rejected(self):
		for args in [
			("", "D4-source", "evt-023", "2026-10-26T13:00:00Z"),
			("analytics-h05-feed", "D4-source", "bad id", "2026-10-26T13:00:00Z"),
			("analytics-h05-feed", "D4-source", "evt-023", "2026-10-26T13:00:00"),
			("analytics-h05-feed", "D4-source", "evt-023", "2099-10-26T13:00:00Z"),
		]:
			with self.subTest(args=args), self.assertRaises(frappe.ValidationError):
				parse_event(*args)
		with patch.object(frappe.db, "get_single_value", return_value="Invalid/Zone"):
			with self.assertRaisesRegex(frappe.ValidationError, "site time zone is invalid"):
				self.event("evt-023", "2026-10-26T13:00:00Z")

	def test_exact_latest_replay_and_equal_time_larger_id(self):
		self.assertTrue(check_event_order(self.deal,
			self.event("evt-022", "2026-10-26T13:00:00Z"), allow_exact_replay=True))
		self.assertFalse(check_event_order(self.deal,
			self.event("evt-023", "2026-10-26T13:00:00Z"), allow_exact_replay=True))

	def test_reused_old_id_changed_time_and_out_of_order_are_rejected(self):
		for event in [
			self.event("evt-020", "2026-10-26T14:00:00Z"),
			self.event("evt-022", "2026-10-26T14:00:00Z"),
			self.event("evt-021", "2026-10-26T12:00:00Z"),
			self.event("evt-021", "2026-10-26T13:00:00Z"),
		]:
			with self.subTest(event=event), self.assertRaises(frappe.ValidationError):
				check_event_order(self.deal, event, allow_exact_replay=True)

	def test_fall_back_orders_absolute_instants_and_preserves_fold(self):
		with patch.object(frappe.db, "get_single_value", return_value="America/New_York"), \
			patch("crm.analytics.source_event_import.utc_now", return_value=datetime(2026, 11, 2, tzinfo=timezone.utc)):
			first = self.event("evt-dst-01", "2026-11-01T01:30:00-04:00")
			second = self.event("evt-dst-02", "2026-11-01T01:15:00-05:00")
		self.assertGreater(first.occurred_at, second.occurred_at)
		self.assertLess(first.occurred_at_utc, second.occurred_at_utc)
		row = frappe._dict(name="synthetic-dst", occurred_at=first.occurred_at,
			payload=json.dumps({"timezone": "America/New_York", "source_event": first.payload()}))
		self.assertEqual(event_instant(row), first.occurred_at_utc)
		with patch.object(frappe, "get_all", return_value=[row]), \
			patch.object(frappe.db, "get_value", return_value=None):
			self.assertFalse(check_event_order(self.deal, second))

	def test_ambiguous_legacy_wall_time_requires_review(self):
		row = frappe._dict(occurred_at="2026-11-01 01:30:00",
			payload=json.dumps({"timezone": "America/New_York"}))
		with self.assertRaisesRegex(frappe.ValidationError, "ambiguous local time"):
			event_instant(row)
