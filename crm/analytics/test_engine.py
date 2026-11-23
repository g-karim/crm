"""Numeric contract tests, independent of Frappe and a database."""

import random
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from crm.analytics.engine import (
	AnalyticsInputError, Context, Period, build_report, calendar_date,
	forecast_value, money, number, percent_change,
)
from crm.analytics.fixtures import acceptance_context, acceptance_data


class TestAnalyticsEngine(unittest.TestCase):
	def setUp(self):
		self.data = acceptance_data()
		self.context = acceptance_context()

	def row(self, name):
		return next(row for row in self.data["deals"] if row["name"] == name)

	def report(self, **kwargs):
		return build_report(**self.data, context=kwargs.pop("context", self.context), **kwargs)

	def check(self, expected, report=None):
		metrics = (report or self.report())["metrics"]
		for key, expected_value in expected.items():
			with self.subTest(metric=key):
				self.assertEqual(metrics[key]["value"], Decimal(str(expected_value)))

	def test_baseline_from_documented_dataset(self):
		self.check({"new_leads": 6, "new_deals": 5, "won_count": 2, "lost_count": 1,
			"won_value": 3000, "open_count": 4, "open_value": 25000, "forecast": 9000,
			"risk_count": 2, "risk_value": 20000, "stalled_value": 10000, "median_cycle": "11.5"})
		r = self.report()
		self.assertEqual(r["quality"], [])
		self.assertEqual(r["metrics"]["win_rate"]["value"], Decimal(200) / 3)
		self.assertEqual(r["metrics"]["won_value"]["delta"], 0)
		self.assertEqual(r["metrics"]["new_leads"]["delta"], 500)
		self.assertEqual(r["funnel"]["converted_leads"], 5)
		self.assertEqual(r["funnel"]["won_leads"], 1)
		self.assertEqual(r["funnel"]["won"], 1)
		self.assertEqual(r["funnel"]["lost"], 1)
		self.assertEqual({v["key"]: v["value"] for v in r["open_owners"]}, {"A": 11000, "B": 14000})

	def test_long_stage_threshold_uses_elapsed_time_across_clock_change(self):
		deal = self.row("D4")
		deal.update(creation="2026-03-28 10:00:00", expected_date="2026-04-15",
			stage_entered_at="2026-03-29T01:30:00+01:00", stale_days=1)
		self.data["deals"] = [deal]
		self.data["leads"] = []
		self.data["tasks"] = []
		zone = ZoneInfo("Europe/Berlin")
		before = replace(self.context, zone=zone.key, as_of=datetime(2026, 3, 30, 1, 45, tzinfo=zone),
			period=Period(date(2026, 3, 1), date(2026, 3, 30)), horizon=Period(date(2026, 3, 30), date(2026, 4, 30)))
		self.assertNotIn("long_stage", self.report(context=before)["attention"][0]["reasons"])
		after = replace(before, as_of=datetime(2026, 3, 30, 2, 45, tzinfo=zone))
		self.assertIn("long_stage", self.report(context=after)["attention"][0]["reasons"])

	def test_numeric_mutations_m01_to_m18(self):
		cases = [
			("M01", "D2", {"value": 2500}, {"won_value": 3500, "open_value": 25000, "forecast": 9000}),
			("M02", "D4", {"expected_value": 8000}, {"forecast": 10000, "open_value": 25000}),
			("M03", "D4", {"probability": 0}, {"forecast": 6000, "open_count": 4}),
			("M04", "D4", {"probability": 100}, {"forecast": 12000, "won_count": 2}),
			("M05", "D6", {"expected_date": "2026-12-02"}, {"forecast": 4000, "open_value": 25000}),
			("M06", "D8", {"expected_date": "2026-11-25"}, {"forecast": 10000}),
			("M07", "D5", {"status_type": "Won", "closed_date": "2026-10-24"}, {"won_count": 3, "won_value": 7000, "open_value": 21000, "forecast": 8000, "median_cycle": 8}),
			("M08", "D5", {"status_type": "Won", "closed_date": "2026-10-26"}, {"won_count": 2, "won_value": 3000, "open_value": 21000, "forecast": 8000}),
			("M09", "D2", {"status_type": "Ongoing"}, {"won_count": 1, "won_value": 1000, "open_value": 27000, "forecast": 9000}),
			("M10", "D1", {"status_type": "Lost", "lost_date": "2026-10-05"}, {"won_count": 1, "won_value": 2000, "lost_count": 2}),
			("M11", "D5", {"status_type": "Lost", "lost_date": "2026-10-26"}, {"lost_count": 1, "open_value": 21000, "forecast": 8000}),
			("M12", "D1", {"closed_date": "2026-09-30"}, {"won_count": 1, "won_value": 2000}),
			("M13", "D6", {"owner": "A"}, {"open_value": 25000, "forecast": 9000}),
			("M14", "D2", {"source": "Web"}, {"won_value": 3000}),
			("M15", "D6", {"pipeline": "Extra"}, {"open_value": 25000, "forecast": 9000}),
			("M16", "D6", {"exchange_rate": 110}, {"open_value": 26000, "forecast": 9500, "risk_value": 21000}),
			("M17", "D6", {"currency": "RUB", "exchange_rate": 1}, {"open_value": 15100, "forecast": 4050, "risk_value": 10100}),
			("M18", "D5", {"creation": "2026-09-30 12:00:00"}, {"new_deals": 4, "open_count": 4, "forecast": 9000}),
		]
		for name, row_name, changes, expected in cases:
			with self.subTest(scenario=name):
				self.data = acceptance_data()
				self.row(row_name).update(changes)
				self.check(expected)

	def test_task_mutations_m19_to_m23(self):
		self.data["tasks"].append({"name": "TD4", "reference_name": "D4", "status": "Todo", "due_date": "2026-10-27"})
		self.check({"risk_count": 2, "risk_value": 20000})  # M19: long-stage remains.
		self.row("D4")["stage_entered_at"] = "2026-10-26 12:00:00"
		self.check({"risk_count": 1, "risk_value": 10000})  # M21: both reasons gone.
		self.data = acceptance_data()
		self.row("D4")["stage_entered_at"] = "2026-10-26 12:00:00"
		self.check({"risk_count": 2})  # M20: no-next-action remains.
		self.data = acceptance_data()
		next(t for t in self.data["tasks"] if t["reference_name"] == "D6")["status"] = "Done"
		self.check({"risk_count": 2, "risk_value": 20000})  # M22: no-next-action replaces overdue.
		self.data = acceptance_data()
		next(t for t in self.data["tasks"] if t["reference_name"] == "D6")["due_date"] = "2026-10-27"
		self.check({"risk_count": 1, "risk_value": 10000})  # M23.

	def test_missing_values_m24_m25(self):
		self.row("D5")["expected_value"] = None
		r = self.report()
		self.check({"forecast": 8000}, r)
		self.assertFalse(r["metrics"]["forecast"]["complete"])
		self.assertEqual(r["metrics"]["forecast"]["missing_count"], 1)
		self.data = acceptance_data()
		self.row("D6")["exchange_rate"] = None
		r = self.report()
		self.check({"open_value": 15000, "forecast": 4000}, r)
		self.assertFalse(r["metrics"]["open_value"]["complete"])

	def test_deletion_duplicate_input_and_repeat_m26_to_m28(self):
		initial = self.report()
		self.data["deals"].append(deepcopy(self.row("D5")))
		self.assertEqual(initial, self.report())
		self.data["deals"] = [r for r in self.data["deals"] if r["name"] != "D4"]
		self.check({"open_value": 15000, "forecast": 6000, "new_deals": 5, "risk_value": 10000})
		self.assertEqual(self.report(), self.report())

	def test_period_boundaries_equal_length_and_timezone(self):
		p = self.context.period
		self.assertEqual(p.days, 25)
		self.assertEqual(p.previous, Period(date(2026, 9, 6), date(2026, 9, 30)))
		self.assertTrue(p.contains("2026-09-30T21:00:00Z", self.context.zone))
		self.assertFalse(p.contains("2026-09-30T20:59:59.999999Z", self.context.zone))
		self.assertTrue(p.contains("2026-10-25T23:59:59.999999+03:00", self.context.zone))
		self.assertFalse(p.contains("2026-10-26T00:00:00+03:00", self.context.zone))
		self.assertEqual(calendar_date(date(2026, 10, 1), "America/New_York"), date(2026, 10, 1))
		for start, end in [(date(2024, 2, 1), date(2024, 2, 29)), (date(2026, 1, 1), date(2026, 1, 1)), (date(2026, 12, 31), date(2027, 1, 1))]:
			period = Period(start, end)
			self.assertEqual(period.days, period.previous.days)
		dst = Period(date(2026, 3, 7), date(2026, 3, 9))
		self.assertEqual(dst.days, 3)
		self.assertTrue(dst.contains("2026-03-10T03:59:59Z", "America/New_York"))
		self.assertFalse(dst.contains("2026-03-10T04:00:00Z", "America/New_York"))

	def test_empty_zero_and_invalid_values(self):
		r = build_report([], [], [], self.context)
		self.assertEqual(r["metrics"]["won_value"]["value"], 0)
		self.assertIsNone(r["metrics"]["win_rate"]["value"])
		self.assertIsNone(r["metrics"]["new_leads"]["delta"])
		for value in [None, "", "NaN", "Infinity", "-Infinity", True, "not a number"]:
			self.assertIsNone(number(value))
		self.assertEqual(number(0), 0)
		for probability in [-1, 101, None, "NaN"]:
			self.row("D4")["probability"] = probability
			self.assertIsNone(forecast_value(self.row("D4"), self.context))
		for value in [-1, None, "NaN"]:
			self.row("D4")["value"] = value
			self.assertIsNone(money(self.row("D4"), self.context))
		with self.assertRaises(AnalyticsInputError):
			Period(date(2026, 10, 2), date(2026, 10, 1))
		with self.assertRaises(AnalyticsInputError):
			replace(self.context, as_of=datetime(2026, 10, 26))

	def test_row_rounding_and_forecast_round_only_once(self):
		r = self.row("D6")
		r.update(value="0.005", expected_value="0.005", currency="RUB", probability=50)
		self.assertEqual(money(r, self.context), Decimal("0.01"))
		self.assertEqual(forecast_value(r, self.context), Decimal("0.00"))
		r.update(value="1000000000000000000.01")
		self.assertEqual(money(r, self.context), Decimal("1000000000000000000.01"))
		r.update(currency="EUR", exchange_rate=0)
		self.assertIsNone(money(r, self.context))

	def test_unknown_currency_never_becomes_known_money_from_a_positive_rate(self):
		row = self.row("D6")
		row.update(currency="ZZZ_INVALID", currency_valid=False, exchange_rate=100)
		report = self.report()
		self.check({"open_value": 15000, "forecast": 4000, "risk_value": 10000}, report)
		self.assertFalse(report["metrics"]["open_value"]["complete"])
		self.assertFalse(report["metrics"]["forecast"]["complete"])
		self.assertIn("unknown_currency", {item["code"] for item in report["quality"]})

	def test_group_totals_dimensions_and_no_inference_from_probability(self):
		for field in ["owner", "pipeline", "source"]:
			r = self.report()
			for value in {d.get(field) for d in self.data["deals"]}:
				context = replace(self.context, **{field: value})
				partial = self.report(context=context)
				expected = sum(d["value"] * d["exchange_rate"] for d in self.data["deals"] if d[field] == value and d["status_type"] not in {"Won", "Lost"})
				self.assertEqual(partial["metrics"]["open_value"]["value"], expected)
		self.row("D4")["probability"] = 100
		self.assertEqual(self.report()["metrics"]["won_count"]["value"], 2)

	def test_real_outcome_date_and_unknown_lost_date(self):
		self.row("D3")["lost_date"] = None
		self.row("D3")["closed_date"] = "2026-10-12"
		r = self.report()
		self.assertEqual(r["metrics"]["lost_count"]["value"], 0)
		self.assertFalse(r["metrics"]["win_rate"]["complete"])
		self.assertIn("missing_outcome_date", {v["code"] for v in r["quality"]})

	def test_revisited_stages_count_unique_deals_including_losses(self):
		events = [{"name": str(i), "deal": "D3", "from_stage": a, "to_stage": b,
			"occurred_at": "2026-10-04 12:00:00"} for i, (a, b) in enumerate([("A", "B"), ("B", "A"), ("A", "B"), ("B", "Lost")])]
		events.append({"name": "outside", "deal": "D1", "from_stage": "A", "to_stage": "B", "occurred_at": "2026-10-04"})
		r = self.report(events=events)
		self.assertEqual({v["stage"]: v["count"] for v in r["funnel"]["visited"]}, {"A": 1, "B": 1, "Lost": 1})
		self.assertEqual({v["stage"]: v["entry_events"] for v in r["funnel"]["visited"]}, {"A": 1, "B": 2, "Lost": 1})
		self.assertEqual(r["funnel"]["stage_changes"], 4)

	def test_skipped_stage_is_not_counted_as_visited(self):
		events = [{"name": "skip", "deal": "D5", "from_stage": "Qualification",
			"to_stage": "Won", "occurred_at": "2026-10-24 12:00:00"}]
		visited = {row["stage"]: row["count"] for row in self.report(events=events)["funnel"]["visited"]}
		self.assertEqual(visited, {"Qualification": 1, "Won": 1})
		self.assertNotIn("Proposal", visited)

	def test_late_creation_records_only_its_actual_first_stage(self):
		self.row("D5")["path_history_complete"] = True
		events = [{"name": "created-late", "deal": "D5", "from_stage": None,
			"to_stage": "Proposal", "occurred_at": "2026-10-23 12:00:00"}]
		funnel = self.report(events=events)["funnel"]
		self.assertEqual({row["stage"]: row["count"] for row in funnel["visited"]}, {"Proposal": 1})
		self.assertEqual(funnel["known_from_creation"], 1)
		self.assertEqual(funnel["stage_changes"], 0)

	def test_two_deals_for_one_lead_and_direct_deal_do_not_duplicate_lead_cohort(self):
		original = self.row("D5")
		self.data["deals"].append({**original, "name": "D9", "creation": "2026-10-22 12:00:00"})
		self.data["deals"].append({**original, "name": "D10", "creation": "2026-10-23 12:00:00", "lead": None})
		funnel = self.report()["funnel"]
		self.assertEqual(funnel["cohort_count"], 7)
		self.assertEqual(funnel["lead_count"], 6)
		self.assertEqual(funnel["converted_leads"], 5)

	def test_missing_history_does_not_invent_a_stale_stage(self):
		self.row("D4")["stage_history_complete"] = False
		r = self.report()
		self.assertEqual(r["metrics"]["stalled_value"]["value"], 0)
		self.assertIn("incomplete_stage_history", {v["code"] for v in r["quality"]})
		self.assertEqual(r["metrics"]["risk_count"]["value"], 2)  # Missing action is still factual.

	def test_stale_threshold_is_strict_and_irrelevant_changes_do_not_change_metrics(self):
		self.row("D4")["stage_entered_at"] = "2026-10-12 12:00:00"
		self.check({"stalled_value": 0})
		before = self.report()["metrics"]
		self.row("D4")["description"] = "A comment is not a new customer contact"
		self.assertEqual(before, self.report()["metrics"])

	def test_future_days_not_rendered_as_observed_zeros(self):
		ctx = replace(self.context, period=Period(date(2026, 10, 1), date(2026, 10, 31)))
		self.assertEqual(len(self.report(context=ctx)["trend"]), 26)

	def test_conflicting_revisions_fail_instead_of_blending(self):
		self.data["deals"].append(self.row("D5") | {"value": 99})
		with self.assertRaises(AnalyticsInputError):
			self.report()

	def test_seeded_mutation_sequences_against_independent_reference(self):
		# This oracle does not call money(), forecast_value(), amount(), or closing().
		rng = random.Random(261026)
		for step in range(200):
			row = rng.choice(self.data["deals"])
			row[rng.choice(["value", "expected_value"])] = rng.randint(0, 100000)
			row["probability"] = rng.randint(0, 100)
			row["status_type"] = rng.choice(["Won", "Lost", "Ongoing"])
			# The native controller rejects an outcome before creation. Generate
			# only accepted transitions for this independent mutation oracle.
			outcome = max(date(2026, 10, 15), calendar_date(row["creation"], self.context.zone))
			row["closed_date"] = str(outcome)
			row["lost_date"] = str(outcome)
			row["owner"] = rng.choice(["A", "B"])
			opened = [d for d in self.data["deals"] if d["status_type"] == "Ongoing"]
			won = [d for d in self.data["deals"] if d["status_type"] == "Won" and "2026-10-01" <= d["closed_date"] <= "2026-10-25"]
			eligible = [d for d in opened if "2026-10-26" <= d["expected_date"] <= "2026-11-25"]
			reference_open = sum(Decimal(d["value"]) * Decimal(d["exchange_rate"]) for d in opened)
			reference_won = sum(Decimal(d["value"]) * Decimal(d["exchange_rate"]) for d in won)
			reference_forecast = sum((Decimal(d["expected_value"]) * Decimal(d["exchange_rate"]) * Decimal(d["probability"]) / 100).quantize(Decimal(".01")) for d in eligible)
			with self.subTest(seed=261026, step=step):
				r = self.report()
				self.check({"open_value": reference_open, "won_value": reference_won, "forecast": reference_forecast}, r)
				self.assertEqual(sum(g["value"] for g in r["open_owners"]), reference_open)
				self.assertEqual(sum(day["won_value"] for day in r["trend"]), reference_won)
				shuffled = deepcopy(self.data)
				rng.shuffle(shuffled["deals"])
				self.assertEqual(build_report(**shuffled, context=self.context), r)


if __name__ == "__main__":
	unittest.main()
