"""Native save/rollback acceptance on the fresh isolated synthetic site.

Run only with the analytics bench's config on PYTHONPATH. Existing demo rows are
never reset: every test rolls back its own transaction.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from crm.analytics.history import EVENT, _event_revision, _read_cache, backfill_baselines, capture, deal_history, load_events
from crm.analytics.service import get_details, get_report
from crm.analytics.testing import clock

ROOT = Path(__file__).resolve().parents[4]
FILTERS = {"from_date": "2026-10-01", "to_date": "2026-10-25", "forecast_from": "2026-10-26", "forecast_to": "2026-11-25"}


class TestAnalyticsNative(unittest.TestCase):
	def setUp(self):
		self.old_cwd = Path.cwd()
		import os
		os.chdir(ROOT / "sites")
		frappe.init(site="crm-analytics-acceptance.localhost", sites_path=str(ROOT / "sites"))
		frappe.connect()
		frappe.set_user("Administrator")
		assert frappe.local.site == "crm-analytics-acceptance.localhost"
		self.manifest = json.loads((ROOT / "evidence/fixture-acceptance.json").read_text())
		self.timer = clock("2026-10-26 12:00:00")
		self.timer.__enter__()

	def tearDown(self):
		import os
		frappe.db.rollback()
		self.timer.__exit__(None, None, None)
		frappe.destroy()
		os.chdir(self.old_cwd)

	def report(self):
		return get_report(FILTERS)

	def check(self, expected):
		metrics = self.report()["metrics"]
		for key, value in expected.items():
			self.assertEqual(str(metrics[key]["value"]), str(value), key)

	def deal(self, key):
		return frappe.get_doc("CRM Deal", self.manifest["deals"][key])

	def save(self, key, values, at="2026-10-26 12:00:00"):
		with clock(at):
			doc = self.deal(key)
			doc.update(values)
			doc.save()
		return doc

	def test_baseline_native_api_and_read_only_queries(self):
		before = {dt: frappe.db.count(dt) for dt in ["CRM Lead", "CRM Deal", "CRM Task", EVENT, "CRM Dashboard"]}
		self.check({"new_leads": 6, "new_deals": 5, "won_count": 2, "lost_count": 1, "won_value": "3000.00",
			"open_count": 4, "open_value": "25000.00", "forecast": "9000.00", "risk_count": 2, "risk_value": "20000.00", "median_cycle": "11.5"})
		r = self.report()
		self.assertEqual(get_details(r["snapshot_token"], "open_value", limit=2)["total"], 4)
		self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})

	def test_historical_as_of_request_does_not_return_current_facts(self):
		with self.assertRaises(frappe.ValidationError) as error:
			get_report({**FILTERS, "as_of": "2020-01-01"})
		self.assertIn("no complete history", str(error.exception))

	def test_future_only_results_period_does_not_report_factual_zero(self):
		with self.assertRaises(frappe.ValidationError) as error:
			get_report({**FILTERS, "from_date": "2026-10-27", "to_date": "2026-10-31"})
		self.assertIn("has not begun", str(error.exception))
		# A future forecast remains valid when the result period includes observed days.
		report = get_report({**FILTERS, "to_date": "2026-10-31"})
		self.assertEqual(report["context"]["to_date"], "2026-10-26")
		self.assertEqual(report["context"]["forecast_to"], "2026-11-25")

	def test_administrator_event_scan_keeps_only_selected_source_ids(self):
		selected = [self.manifest["deals"]["D1"]]
		expected = load_events("CRM Deal", selected)
		actual = load_events("CRM Deal", selected, administrator_scan=True)
		self.assertEqual(actual, expected)
		self.assertEqual(set(actual), set(selected))
		# Fast event transport must retain the driver's datetime types and
		# values so source revisions and stage timelines remain identical.
		native = frappe.db.sql("""SELECT `name`, `source_name`, `event_kind`, `occurred_at`,
			`history_complete`, `creation`, `sequence`
			FROM `tabCRM Analytics Event` WHERE `source_type` = %s AND `source_name` = %s
			ORDER BY `source_name` ASC, `sequence` ASC""", ("CRM Deal", selected[0]), as_dict=True)
		self.assertEqual(
			[{key: value for key, value in row.items() if key != "payload"} for row in expected[selected[0]]],
			native,
		)

	def test_revision_checked_history_cache_revalidates_native_change_and_rollback(self):
		"""A same-sequence replacement and direct source edit cannot preserve stale facts."""
		frappe.local.analytics_consistent_read = True
		frappe.db.savepoint("analytics_cache_check")
		try:
			original = self.report()
			base_revision, base_count = _event_revision("CRM Deal")
			self.save("D4", {"expected_deal_value": 8000})
			first_revision, first_count = _event_revision("CRM Deal")
			self.assertNotEqual(first_revision, base_revision)
			self.assertEqual(first_count, base_count + 1)
			self.assertEqual(self.report()["metrics"]["forecast"]["value"], "10000.00")
			frappe.db.rollback(save_point="analytics_cache_check")
			self.assertEqual(_event_revision("CRM Deal"), (base_revision, base_count))
			self.assertEqual(self.report()["snapshot"], original["snapshot"])

			self.save("D4", {"expected_deal_value": 9000})
			second_revision, second_count = _event_revision("CRM Deal")
			self.assertEqual(second_count, first_count)
			self.assertNotEqual(second_revision, first_revision)
			self.assertEqual(self.report()["metrics"]["forecast"]["value"], "10500.00")
			frappe.db.rollback(save_point="analytics_cache_check")

			# Direct SQL edits do not create history, but fresh source rows must
			# still invalidate the confirmed amount in the report.
			frappe.db.set_value("CRM Deal", self.manifest["deals"]["D4"], "deal_value", 12000)
			self.assertEqual(_event_revision("CRM Deal"), (base_revision, base_count))
			changed = self.report()
			self.assertFalse(changed["metrics"]["open_value"]["complete"])
			self.assertEqual(changed["metrics"]["open_value"]["value"], "15000.00")
			frappe.db.rollback(save_point="analytics_cache_check")

			# A warmed Administrator cache cannot supply another user's events.
			frappe.set_user(self.manifest["users"]["A"])
			restricted = self.report()
			self.assertEqual(restricted["metrics"]["won_value"]["value"], "1000.00")
			self.assertEqual(restricted["metrics"]["open_value"]["value"], "11000.00")
			self.assertEqual([row["name"] for row in get_details(
				restricted["snapshot_token"], "won_value")["rows"]], [self.manifest["deals"]["D1"]])
		finally:
			frappe.set_user("Administrator")
			frappe.db.rollback(save_point="analytics_cache_check")
			frappe.local.analytics_consistent_read = False
			_read_cache.clear()

	def test_streamed_history_matches_full_event_facts(self):
		from crm.analytics.history import _stream_deal_facts, _project_deal_events, internal_write
		names = list(self.manifest["deals"].values())
		self.assertEqual(_stream_deal_facts(names),
			_project_deal_events(load_events("CRM Deal", names, administrator_scan=True)))
		name = "analytics-projection-edge-chain"
		states = [("Deleted", {"status":"Old"}, None),
			("Baseline", None, {"status":"Open", "deal_value":"100"}),
			("Updated", {"status":"Open", "deal_value":"100"}, {"status":"Open", "deal_value":"200"})]
		with internal_write():
			for sequence, (kind, before, after) in enumerate(states, 1):
				frappe.get_doc({"doctype":EVENT,"source_type":"CRM Deal","source_name":name,
					"sequence":sequence,"event_kind":kind,"occurred_at":f"2026-10-26 10:00:0{sequence}",
					"history_complete":0,"actor":"Administrator","payload":json.dumps({"before":before,"after":after})}).insert(ignore_permissions=True,set_name=name+str(sequence))
		self.assertEqual(_stream_deal_facts([name]),
			_project_deal_events(load_events("CRM Deal", [name], administrator_scan=True)))

	def test_compact_history_cache_returns_detached_facts(self):
		from crm.analytics.history import load_deal_facts_for_report, _fact_read_cache
		frappe.local.analytics_consistent_read = True
		try:
			before = self.report()
			name = self.manifest["deals"]["D4"]
			facts = load_deal_facts_for_report([name], administrator_scan=True)
			facts[name]["latest_after"]["deal_value"] = "999999"
			facts[name]["first"]["history_complete"] = False
			facts[name]["fact"]["transitions"].clear()
			self.assertEqual(self.report()["snapshot"], before["snapshot"])
			self.assertEqual(self.report()["metrics"], before["metrics"])
		finally:
			frappe.local.analytics_consistent_read = False
			_fact_read_cache.clear()

	def test_dst_calendar_days_on_native_site(self):
		"""The site zone, source timestamps, API, and detail selection agree over DST."""
		original_zone = frappe.db.get_single_value("System Settings", "time_zone")
		try:
			frappe.db.set_single_value("System Settings", "time_zone", "America/New_York")
			for suffix, at in [("previous", "2026-03-06 23:59:59"),
				("inside", "2026-03-09 23:59:59"), ("outside", "2026-03-10 00:00:00")]:
				with clock(at):
					frappe.get_doc({"doctype": "CRM Lead", "first_name": "DST " + suffix,
						"status": "New"}).insert(set_name="analytics-dst-" + suffix)
			with clock("2026-10-26 12:00:00"):
				report = get_report({"from_date": "2026-03-07", "to_date": "2026-03-09",
					"forecast_from": "2026-03-07", "forecast_to": "2026-03-09"})
				details = get_details(report["snapshot_token"], "new_leads")
			self.assertEqual(report["context"]["timezone"], "America/New_York")
			self.assertEqual((report["context"]["previous_from"], report["context"]["previous_to"]),
				("2026-03-04", "2026-03-06"))
			self.assertEqual(report["metrics"]["new_leads"]["value"], 1)
			self.assertEqual(report["metrics"]["new_leads"]["previous"], 1)
			self.assertEqual(report["metrics"]["new_leads"]["delta"], "0")
			self.assertEqual(details["total"], 1)
			self.assertEqual(details["rows"][0]["name"], "analytics-dst-inside")
		finally:
			frappe.db.set_single_value("System Settings", "time_zone", original_zone)

	def test_native_period_edges_include_microseconds(self):
		"""A native row at the last microsecond belongs to the closing day."""
		for suffix, at in [("first", "2026-10-01 00:00:00"),
			("last", "2026-10-25 23:59:59.999999"),
			("next", "2026-10-26 00:00:00")]:
			with clock(at):
				frappe.get_doc({"doctype": "CRM Lead", "first_name": "Boundary " + suffix,
					"status": "New"}).insert(set_name="analytics-edge-" + suffix)
		report = self.report()
		self.assertEqual(report["metrics"]["new_leads"]["value"], 8)
		details = get_details(report["snapshot_token"], "new_leads", limit=50)
		self.assertEqual(details["total"], 8)
		names = {row["name"] for row in details["rows"]}
		self.assertTrue({"analytics-edge-first", "analytics-edge-last"} <= names)
		self.assertNotIn("analytics-edge-next", names)

	def test_native_money_probability_dates_and_outcome_mutations(self):
		s = self.manifest["stages"]
		cases = [
			("M01", "D2", {"deal_value": 2500}, {}, {"won_value": "3500.00", "forecast": "9000.00"}),
			("M02", "D4", {"expected_deal_value": 8000}, {}, {"forecast": "10000.00", "open_value": "25000.00"}),
			("M03", "D4", {"probability": 0}, {}, {"forecast": "6000.00", "won_value": "3000.00"}),
			("M04", "D4", {"probability": 100}, {}, {"forecast": "12000.00", "won_count": 2}),
			("M05", "D6", {"expected_closure_date": "2026-12-02"}, {}, {"forecast": "4000.00", "open_value": "25000.00"}),
			("M06", "D8", {"expected_closure_date": "2026-11-25"}, {}, {"forecast": "10000.00"}),
			("M07", "D5", {"status": s["Main:Won"]}, {"at": "2026-10-24 12:00:00"}, {"won_count": 3, "won_value": "7000.00", "open_value": "21000.00", "forecast": "8000.00", "median_cycle": "8"}),
			("M08", "D5", {"status": s["Main:Won"]}, {}, {"won_count": 2, "won_value": "3000.00", "open_value": "21000.00", "forecast": "8000.00"}),
			("M09", "D2", {"status": s["Main:Qualification"]}, {}, {"won_count": 1, "won_value": "1000.00", "open_value": "27000.00", "forecast": "9000.00"}),
			("M10", "D1", {"status": s["Main:Lost"], "lost_reason": "Analytics Price"}, {"at": "2026-10-05 12:00:00"}, {"won_count": 1, "won_value": "2000.00", "lost_count": 2}),
			("M11", "D5", {"status": s["Main:Lost"], "lost_reason": "Analytics Price"}, {}, {"lost_count": 1, "open_value": "21000.00", "forecast": "8000.00"}),
			("M12", "D1", {"closed_date": "2026-09-30"}, {}, {"won_count": 1, "won_value": "2000.00"}),
			("M13", "D6", {"deal_owner": self.manifest["users"]["A"]}, {}, {"open_value": "25000.00", "forecast": "9000.00"}),
			("M14", "D2", {"source": "Web"}, {}, {"won_value": "3000.00"}),
			("M15", "D6", {"pipeline": self.manifest["pipelines"]["Extra"], "status": s["Extra:Proposal"]}, {}, {"open_value": "25000.00", "forecast": "9000.00"}),
			("M16", "D6", {"exchange_rate": 110}, {}, {"open_value": "26000.00", "forecast": "9500.00", "risk_value": "21000.00"}),
			("M17", "D6", {"currency": "RUB"}, {}, {"open_value": "15100.00", "forecast": "4050.00", "risk_value": "10100.00"}),
		]
		for name, key, values, options, expected in cases:
			with self.subTest(scenario=name):
				frappe.db.savepoint("mutation")
				try:
					self.save(key, values, **options)
					self.check(expected)
				finally:
					frappe.db.rollback(save_point="mutation")

	def test_next_actions_and_independent_risk_reasons(self):
		frappe.get_doc({"doctype": "CRM Task", "title": "Следующее действие D4", "reference_doctype": "CRM Deal",
			"reference_docname": self.manifest["deals"]["D4"], "status": "Todo", "due_date": "2026-10-27 12:00:00",
			"assigned_to": self.manifest["users"]["A"]}).insert()
		self.check({"risk_count": 2, "risk_value": "20000.00"})
		self.save("D4", {"status": self.manifest["stages"]["Main:Qualification"]})
		self.check({"risk_count": 1, "risk_value": "10000.00"})

	def test_completed_overdue_task_still_requires_a_next_action(self):
		task = frappe.get_doc("CRM Task", self.manifest["tasks"]["TD6"])
		task.status = "Done"; task.save()
		self.check({"risk_count": 2, "risk_value": "20000.00"})
		attention = next(row for row in self.report()["attention"] if row["name"] == self.manifest["deals"]["D6"])
		self.assertIn("no_next_action", attention["reasons"])
		self.assertNotIn("overdue_action", attention["reasons"])

	def test_rescheduling_overdue_action_removes_its_risk(self):
		task = frappe.get_doc("CRM Task", self.manifest["tasks"]["TD6"])
		task.due_date = "2026-10-27 12:00:00"; task.save()
		self.check({"risk_count": 1, "risk_value": "10000.00"})

	def test_legacy_unknown_values_remain_partial(self):
		self.save("D5", {"expected_deal_value": None})
		r = self.report()
		self.assertEqual(r["metrics"]["forecast"]["value"], "8000.00")
		self.assertFalse(r["metrics"]["forecast"]["complete"])
		frappe.db.set_value("CRM Deal", self.manifest["deals"]["D6"], "exchange_rate", 0)
		r = self.report()
		self.assertEqual(r["metrics"]["open_value"]["value"], "15000.00")
		self.assertFalse(r["metrics"]["open_value"]["complete"])

	def test_unrecorded_numeric_change_is_partial_before_unrelated_save(self):
		frappe.db.savepoint("direct_probability")
		try:
			frappe.db.set_value("CRM Deal", self.manifest["deals"]["D4"], "probability", 0)
			r = self.report()
			self.assertEqual(r["metrics"]["forecast"]["value"], "6000.00")
			self.assertFalse(r["metrics"]["forecast"]["complete"])
		finally:
			frappe.db.rollback(save_point="direct_probability")
		frappe.db.savepoint("direct_rate")
		try:
			frappe.db.set_value("CRM Deal", self.manifest["deals"]["D6"], "exchange_rate", 0)
			r = self.report()
			self.assertEqual(r["metrics"]["open_value"]["value"], "15000.00")
			self.assertFalse(r["metrics"]["open_value"]["complete"])
		finally:
			frappe.db.rollback(save_point="direct_rate")

	def test_unknown_imported_currency_cannot_contribute_money_with_a_positive_rate(self):
		before = self.report()
		name = self.manifest["deals"]["D6"]
		frappe.db.set_value("CRM Deal", name, "currency", "ZZZ_INVALID")
		report = self.report()
		for key, value in (("open_value", "15000.00"), ("forecast", "4000.00"),
			("risk_value", "10000.00")):
			self.assertEqual(report["metrics"][key]["value"], value, key)
			self.assertFalse(report["metrics"][key]["complete"], key)
		rows = get_details(report["snapshot_token"], "open_value")["rows"]
		self.assertFalse(next(row for row in rows if row["name"] == name)["currency_valid"])
		quality = next(row for row in report["quality"] if row["code"] == "unknown_currency")
		self.assertEqual(quality["count"], 1)
		with self.assertRaises(frappe.TimestampMismatchError):
			get_details(before["snapshot_token"], "open_value")

	def test_created_on_correction_is_rejected_natively(self):
		before = self.report()["snapshot"]
		frappe.db.savepoint("creation_rejected")
		try:
			with self.assertRaises(frappe.CannotChangeConstantError):
				self.save("D5", {"creation": "2026-09-30 12:00:00"})
		finally:
			frappe.db.rollback(save_point="creation_rejected")
		self.assertEqual(before, self.report()["snapshot"])

	def test_linked_deal_deletion_rejected_and_rolled_back(self):
		before = self.report()["snapshot"]
		frappe.db.savepoint("delete_rejected")
		try:
			with self.assertRaises(frappe.LinkExistsError):
				frappe.delete_doc("CRM Deal", self.manifest["deals"]["D5"])
		finally:
			frappe.db.rollback(save_point="delete_rejected")
		self.assertEqual(before, self.report()["snapshot"])

	def test_unlinked_native_deletion_preserves_audit_fact_and_totals(self):
		before = self.report()
		with clock("2026-10-26 12:00:00"):
			deal = frappe.get_doc({"doctype": "CRM Deal", "deal_name": "Disposable deletion check",
				"pipeline": self.manifest["pipelines"]["Main"],
				"status": self.manifest["stages"]["Main:Qualification"],
				"deal_value": 100, "expected_deal_value": 100,
				"probability": 50, "currency": "RUB", "exchange_rate": 1,
				"expected_closure_date": "2026-11-10"}).insert()
		self.check({"open_count": 5, "open_value": "25100.00", "forecast": "9050.00"})
		frappe.delete_doc("CRM Deal", deal.name)
		self.assertEqual(self.report()["metrics"], before["metrics"])
		kinds = frappe.get_all(EVENT, filters={"source_type": "CRM Deal", "source_name": deal.name},
			pluck="event_kind", order_by="sequence asc", limit_page_length=0)
		self.assertEqual(kinds, ["Created", "Deleted"])

	def test_repeated_external_import_id_is_an_explicit_conflict(self):
		fields = {"doctype": "CRM Deal", "deal_name": "Repeated import check",
			"pipeline": self.manifest["pipelines"]["Main"],
			"status": self.manifest["stages"]["Main:Qualification"],
			"external_source": "analytics-local-acceptance", "external_record_id": "M26-repeat",
			"currency": "RUB", "exchange_rate": 1}
		first = frappe.get_doc(fields).insert()
		before = self.report()["snapshot"]
		before_count = frappe.db.count(EVENT)
		frappe.db.savepoint("duplicate_import")
		try:
			with self.assertRaises(frappe.DuplicateEntryError):
				frappe.get_doc(fields | {"deal_name": "Should not exist"}).insert()
		finally:
			frappe.db.rollback(save_point="duplicate_import")
		self.assertEqual(self.report()["snapshot"], before)
		self.assertEqual(frappe.db.count(EVENT), before_count)
		self.assertEqual(frappe.db.count("CRM Deal", {"external_source": fields["external_source"],
			"external_record_id": fields["external_record_id"]}), 1)
		self.assertTrue(first.name)

	def test_invalid_probability_closure_and_exchange_rate_are_rejected(self):
		for key, values in [("D4", {"probability": -1}), ("D4", {"probability": 101}),
			("D6", {"exchange_rate": -1}), ("D6", {"exchange_rate": 0}),
			("D2", {"closed_date": "2026-09-30"}), ("D2", {"closed_date": "2026-10-27"})]:
			with self.subTest(values=values):
				before = self.report()["snapshot"]
				frappe.db.savepoint("rejected")
				try:
					with self.assertRaises(frappe.ValidationError):
						self.save(key, values)
				finally:
					frappe.db.rollback(save_point="rejected")
				self.assertEqual(before, self.report()["snapshot"])

	def test_zero_numeric_string_is_retained(self):
		self.save("D4", {"probability": "0"})
		self.check({"forecast": "6000.00"})

	def test_partial_old_data_is_not_repaired_by_a_note(self):
		frappe.db.set_value("CRM Deal", self.manifest["deals"]["D6"], "exchange_rate", 0)
		frappe.db.set_value("CRM Deal", self.manifest["deals"]["D4"], "probability", 0)
		frappe.db.set_value("CRM Deal", self.manifest["deals"]["D2"], "closed_date", None)
		with patch("crm.fcrm.doctype.crm_deal.crm_deal.get_exchange_rate", side_effect=AssertionError("Unrelated change must not fetch rates")):
			for name in ["D6", "D4", "D2"]:
				self.save(name, {"next_step": "A note does not repair historical facts"})
		self.assertEqual(self.deal("D6").exchange_rate, 0)
		self.assertEqual(self.deal("D4").probability, 0)
		self.assertFalse(json.loads(self.deal("D4").analytics_value_presence)["probability"])
		self.assertIsNone(self.deal("D2").closed_date)

	def test_changed_report_rejects_stale_details(self):
		r = self.report()
		self.save("D2", {"deal_value": 2500})
		with self.assertRaises(frappe.TimestampMismatchError):
			get_details(r["snapshot_token"], "won_value")

	def test_user_scopes_and_forged_snapshot(self):
		for key, expected in [("manager", ("3000.00", "25000.00")), ("A", ("1000.00", "11000.00")), ("B", ("2000.00", "14000.00"))]:
			frappe.set_user(self.manifest["users"][key])
			r = self.report()
			self.assertEqual((r["metrics"]["won_value"]["value"], r["metrics"]["open_value"]["value"]), expected)
			with self.assertRaises(frappe.TimestampMismatchError):
				get_details(r["snapshot_token"] + "forged", "won_value")

	def test_token_cannot_be_reused_by_another_user(self):
		frappe.set_user(self.manifest["users"]["manager"])
		r = self.report()
		frappe.set_user(self.manifest["users"]["A"])
		with self.assertRaises(frappe.TimestampMismatchError):
			get_details(r["snapshot_token"], "won_value")

	def test_more_than_one_source_and_detail_page_has_no_gaps(self):
		frappe.db.savepoint("pagination")
		try:
			stage = self.manifest["stages"]["Main:Qualification"]
			pipeline = self.manifest["pipelines"]["Main"]
			for index in range(510):
				name = f"analytics-page-{index:04d}"
				frappe.db.sql("""INSERT INTO `tabCRM Deal`
					(name, owner, creation, modified, modified_by, docstatus, idx,
					 deal_name, status, pipeline, deal_owner, source, currency)
					 VALUES (%s, 'Administrator', '2026-10-20 12:00:00',
					 '2026-10-20 12:00:00', 'Administrator', 0, 0,
					 %s, %s, %s, %s, 'Web', 'RUB')""",
					(name, name, stage, pipeline, self.manifest["users"]["A"]))
			report = self.report()
			self.assertEqual(report["metrics"]["new_deals"]["value"], 515)
			pages = [get_details(report["snapshot_token"], "new_deals", start=start, limit=200)
				for start in (0, 200, 400)]
			self.assertTrue(all(page["total"] == 515 for page in pages))
			all_names = [row["name"] for page in pages for row in page["rows"]]
			self.assertEqual(len(all_names), 515)
			self.assertEqual(len(set(all_names)), 515)
			self.assertEqual(sum(name.startswith("analytics-page-") for name in all_names), 510)
		finally:
			frappe.db.rollback(save_point="pagination")

	def test_history_is_private_immutable_and_not_duplicated_by_replay(self):
		before = frappe.db.count(EVENT)
		doc = self.deal("D4")
		capture(doc, "on_update")
		self.assertEqual(before, frappe.db.count(EVENT))
		event = frappe.get_doc(EVENT, frappe.get_all(EVENT, fields=["name"], limit_page_length=1)[0].name)
		with self.assertRaises(frappe.PermissionError):
			event.payload = "{}"; event.save()
		frappe.set_user(self.manifest["users"]["A"])
		self.assertFalse(frappe.has_permission(EVENT, "read"))

	def test_comment_and_non_analytic_note_do_not_create_sales_or_contact_facts(self):
		before = self.report()
		event_count = frappe.db.count(EVENT)
		self.save("D4", {"next_step": "Synthetic internal note"})
		frappe.get_doc({"doctype": "Comment", "comment_type": "Comment",
			"reference_doctype": "CRM Deal", "reference_name": self.manifest["deals"]["D4"],
			"content": "Synthetic test comment, not a customer conversation"}).insert(ignore_permissions=True)
		after = self.report()
		self.assertEqual(before["snapshot"], after["snapshot"])
		self.assertEqual(before["metrics"], after["metrics"])
		self.assertEqual(event_count, frappe.db.count(EVENT))

	def test_revisited_stage_sequence_survives_equal_timestamps(self):
		s = self.manifest["stages"]
		before_report = self.report()
		before_funnel = before_report["funnel"]
		before_proposal = next(row for row in before_funnel["visited"] if row["stage"] == s["Main:Proposal"])
		for stage in [s["Main:Proposal"], s["Main:Qualification"], s["Main:Proposal"]]:
			self.save("D5", {"status": stage})
		rows = frappe.get_all(EVENT, filters={"source_name": self.manifest["deals"]["D5"]}, fields=["sequence"], order_by="sequence asc", limit_page_length=0)
		self.assertEqual([row.sequence for row in rows], list(range(1, len(rows) + 1)))
		funnel = self.report()["funnel"]
		proposal = next(row for row in funnel["visited"] if row["stage"] == s["Main:Proposal"])
		self.assertEqual(proposal["count"], before_proposal["count"] + 1)
		self.assertEqual(proposal["entry_events"], before_proposal["entry_events"] + 2)
		self.assertEqual(funnel["stage_changes"], before_funnel["stage_changes"] + 3)
		self.check({key: before_report["metrics"][key]["value"] for key in ("risk_count", "stalled_value")})

	def test_late_status_change_cannot_reorder_accepted_history(self):
		stages = self.manifest["stages"]
		self.save("D5", {"status": stages["Main:Proposal"]}, at="2026-10-26 11:00:02")
		accepted = self.report()
		count = frappe.db.count(EVENT)
		frappe.db.savepoint("late_status_change")
		try:
			with self.assertRaises(frappe.ValidationError) as error:
				self.save("D5", {"status": stages["Main:Qualification"]}, at="2026-10-26 11:00:01")
			self.assertIn("predates the latest accepted", str(error.exception))
		finally:
			frappe.db.rollback(save_point="late_status_change")
		self.assertEqual(self.deal("D5").status, stages["Main:Proposal"])
		self.assertEqual(frappe.db.count(EVENT), count)
		self.assertEqual(self.report()["snapshot"], accepted["snapshot"])
		self.assertEqual(get_details(accepted["snapshot_token"], "open_count")["total"], 4)
		# Redelivering the already accepted state does not create another interval.
		self.save("D5", {"status": stages["Main:Proposal"]}, at="2026-10-26 11:00:01")
		self.assertEqual(frappe.db.count(EVENT), count)

	def test_legacy_baseline_is_idempotent_without_invented_stage_history(self):
		name = "analytics-legacy-baseline-test"
		with patch("crm.analytics.history.capture", return_value=None), patch(
			"crm.fcrm.doctype.crm_deal.crm_deal.add_status_change_log", return_value=None
		):
			with clock("2026-10-02 09:00:00"):
				frappe.get_doc({"doctype": "CRM Deal", "deal_name": "Legacy baseline test",
					"pipeline": self.manifest["pipelines"]["Main"],
					"status": self.manifest["stages"]["Main:Proposal"],
					"deal_value": 300, "expected_deal_value": 300,
					"probability": 50, "currency": "RUB",
					"expected_closure_date": "2026-11-10"}).insert(set_name=name)
		before = self.report()
		self.assertEqual(load_events("CRM Deal", [name])[name], [])
		with clock("2026-10-26 11:00:00"):
			first = backfill_baselines(source_names={"CRM Deal": [name]})
			second = backfill_baselines(source_names={"CRM Deal": [name]})
		self.assertEqual(first, {"CRM Deal": 1, "CRM Lead": 0, "CRM Task": 0})
		self.assertEqual(second, {"CRM Deal": 0, "CRM Lead": 0, "CRM Task": 0})
		after = self.report()
		self.assertEqual(before["metrics"], after["metrics"])
		self.assertEqual(before["funnel"], after["funnel"])
		self.assertEqual(after["funnel"]["known_from_creation"], 5)
		self.assertEqual(after["funnel"]["cohort_count"], 6)
		events = load_events("CRM Deal", [name])[name]
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0]["event_kind"], "Baseline")
		self.assertEqual(events[0]["history_complete"], 0)
		self.assertFalse(deal_history(events)["stage_history_complete"])

	def test_used_stage_identifier_cannot_be_renamed_or_deleted(self):
		stage = self.manifest["stages"]["Main:Proposal"]
		deal_name = self.manifest["deals"]["D4"]
		before = self.report()
		events = load_events("CRM Deal", [deal_name])[deal_name]
		with self.assertRaises(frappe.ValidationError) as rename_error:
			frappe.rename_doc("CRM Deal Status", stage, stage + "-renamed")
		self.assertIn("without renaming its identifier", str(rename_error.exception))
		with self.assertRaises(frappe.ValidationError) as delete_error:
			frappe.delete_doc("CRM Deal Status", stage)
		self.assertIn("Archive a stage", str(delete_error.exception))
		self.assertEqual(self.deal("D4").status, stage)
		self.assertEqual(load_events("CRM Deal", [deal_name])[deal_name], events)
		self.assertEqual(self.report()["metrics"], before["metrics"])
		status = frappe.get_doc("CRM Deal Status", stage)
		old_label = status.deal_status
		status.deal_status = old_label + " (обновлено)"
		status.save()
		self.assertEqual(frappe.db.get_value("CRM Deal Status", stage, "deal_status"), status.deal_status)
		self.assertEqual(self.deal("D4").status, stage)
		self.assertEqual(load_events("CRM Deal", [deal_name])[deal_name], events)
		self.assertEqual(self.report()["metrics"], before["metrics"])

	def test_stage_referenced_only_by_retained_analytics_history_is_protected(self):
		stage = "analytics-retained-stage"
		deal = "analytics-retained-stage-deal"
		with clock("2026-10-10 09:00:00"):
			frappe.get_doc({"doctype": "CRM Deal Status", "deal_status": "Retained history",
				"pipeline": self.manifest["pipelines"]["Main"], "type": "Open"}).insert(set_name=stage)
			frappe.get_doc({"doctype": "CRM Deal", "deal_name": "Retained history deal",
				"pipeline": self.manifest["pipelines"]["Main"], "status": stage,
				"deal_value": 100, "expected_deal_value": 100, "probability": 50,
				"currency": "RUB", "expected_closure_date": "2026-11-10"}).insert(set_name=deal)
		with clock("2026-10-20 09:00:00"):
			frappe.delete_doc("CRM Deal", deal)
		self.assertFalse(frappe.db.exists("CRM Deal", {"status": stage}))
		self.assertFalse(frappe.db.exists("CRM Status Change Log", {"from": stage}))
		self.assertFalse(frappe.db.exists("CRM Status Change Log", {"to": stage}))
		self.assertTrue(load_events("CRM Deal", [deal])[deal])
		with self.assertRaises(frappe.ValidationError):
			frappe.rename_doc("CRM Deal Status", stage, stage + "-renamed")
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("CRM Deal Status", stage)
		self.assertTrue(frappe.db.exists("CRM Deal Status", stage))

	def test_historical_stage_label_remains_readable_after_return(self):
		stages = self.manifest["stages"]
		self.save("D8", {"status": stages["Extra:Proposal"]})
		self.save("D8", {"status": stages["Extra:Qualification"]})
		report = self.report()
		proposal = stages["Extra:Proposal"]
		self.assertIn(proposal, {row["stage"] for row in report["funnel"]["visited"]})
		self.assertIn("Proposal", report["labels"]["stages"][proposal])
		self.assertIn(self.manifest["pipelines"]["Extra"], report["labels"]["stages"][proposal])

	def test_backdated_creation_does_not_claim_complete_stage_path(self):
		before = self.report()
		name = self.manifest["deals"]["D5"]
		frappe.db.set_value("CRM Deal", name, "creation", "2026-10-21 12:00:00")
		after = self.report()
		self.assertEqual(before["funnel"]["cohort_count"], after["funnel"]["cohort_count"])
		self.assertEqual(after["funnel"]["known_from_creation"],
			before["funnel"]["known_from_creation"] - 1)

	def test_lost_reopened_then_won_keeps_one_current_outcome_and_full_history(self):
		name = self.manifest["deals"]["D5"]
		stages = self.manifest["stages"]
		self.save("D5", {"status": stages["Main:Lost"], "lost_reason": "Analytics Price"}, at="2026-10-26 12:00:01")
		self.check({"open_value": "21000.00", "forecast": "8000.00", "lost_count": 1})
		self.save("D5", {"status": stages["Main:Qualification"], "lost_reason": None}, at="2026-10-26 12:00:02")
		self.check({"open_value": "25000.00", "forecast": "9000.00", "lost_count": 1})
		self.save("D5", {"status": stages["Main:Won"]}, at="2026-10-26 12:00:03")
		self.check({"open_value": "21000.00", "forecast": "8000.00", "won_count": 2})
		current = get_report({**FILTERS, "to_date": "2026-10-26"})
		self.assertEqual(current["metrics"]["won_count"]["value"], 3)
		self.assertEqual(current["metrics"]["won_value"]["value"], "7000.00")
		events = load_events("CRM Deal", [name])[name]
		transitions = deal_history(events)["transitions"]
		self.assertEqual([row["to_stage"] for row in transitions[-3:]],
			[stages["Main:Lost"], stages["Main:Qualification"], stages["Main:Won"]])

	def test_used_stage_cannot_be_reclassified_or_deleted(self):
		stage = frappe.get_doc("CRM Deal Status", self.manifest["stages"]["Main:Proposal"])
		with self.assertRaises(frappe.ValidationError):
			stage.type = "Won"; stage.save()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("CRM Deal Status", stage.name)


if __name__ == "__main__":
	unittest.main()
