"""Deterministic analytics over an already authorized, consistent source snapshot.

This module has no Frappe, database, network, clock, or persistence dependency.
Amounts remain Decimal; callers serialize them as decimal strings.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from statistics import median
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

VERSION = "crm-analytics/1"
CLOSED = {"Won", "Lost"}
OPEN = {"Open", "Ongoing", "On Hold"}
DONE_TASKS = {"Done", "Canceled", "Cancelled", "Completed"}
RISK_REASONS = ("overdue_action", "overdue_close", "no_next_action", "long_stage", "pushed_close")


class AnalyticsInputError(ValueError):
	pass


def number(value: Any) -> Decimal | None:
	if value is None or value == "" or isinstance(value, bool):
		return None
	try:
		result = Decimal(str(value))
	except (InvalidOperation, ValueError, TypeError):
		return None
	return result if result.is_finite() else None


def timestamp(value: Any, zone: str) -> datetime | None:
	if value is None or value == "":
		return None
	try:
		if isinstance(value, datetime):
			result = value
		elif isinstance(value, date):
			result = datetime.combine(value, time.min)
		else:
			result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
		return result.replace(tzinfo=ZoneInfo(zone)) if result.tzinfo is None else result.astimezone(ZoneInfo(zone))
	except (ValueError, TypeError, OverflowError):
		return None


def calendar_date(value: Any, zone: str) -> date | None:
	if isinstance(value, date) and not isinstance(value, datetime):
		return value
	parsed = timestamp(value, zone)
	return parsed.date() if parsed else None


@dataclass(frozen=True)
class Period:
	start: date
	end: date

	def __post_init__(self):
		if self.start > self.end:
			raise AnalyticsInputError("Period start must not follow its end")
		if self.days > 3660:
			raise AnalyticsInputError("Period exceeds ten calendar years")

	@property
	def days(self) -> int:
		return (self.end - self.start).days + 1

	@property
	def previous(self) -> Period:
		return Period(self.start - timedelta(days=self.days), self.start - timedelta(days=1))

	def contains(self, value: Any, zone: str) -> bool:
		parsed = calendar_date(value, zone)
		return bool(parsed and self.start <= parsed <= self.end)


@dataclass(frozen=True)
class Context:
	period: Period
	horizon: Period
	as_of: datetime
	zone: str = "Europe/Moscow"
	currency: str = "RUB"
	precision: int = 2
	stale_days: int = 14
	owner: str | None = None
	pipeline: str | None = None
	source: str | None = None

	def __post_init__(self):
		if self.as_of.tzinfo is None:
			raise AnalyticsInputError("An explicit timezone is required for the snapshot")
		ZoneInfo(self.zone)
		if not 0 <= self.precision <= 6 or not 0 <= self.stale_days <= 3650:
			raise AnalyticsInputError("Invalid precision or stage threshold")
		if not self.currency or len(self.currency) > 12:
			raise AnalyticsInputError("A reporting currency is required")

	@cached_property
	def quantum(self) -> Decimal:
		return Decimal(1).scaleb(-self.precision)

	def round(self, value: Decimal) -> Decimal:
		return value.quantize(self.quantum, rounding=ROUND_HALF_UP)

	def includes(self, row: dict) -> bool:
		return ((not self.owner or row.get("owner") == self.owner)
			and (not self.pipeline or row.get("pipeline") == self.pipeline)
			and (not self.source or row.get("source") == self.source))

	def metadata(self) -> dict:
		return {
			"contract": VERSION,
			"from_date": str(self.period.start), "to_date": str(self.period.end),
			"previous_from": str(self.period.previous.start), "previous_to": str(self.period.previous.end),
			"forecast_from": str(self.horizon.start), "forecast_to": str(self.horizon.end),
			"as_of": self.as_of.isoformat(), "timezone": self.zone,
			"currency": self.currency, "precision": self.precision,
			"owner": self.owner, "pipeline": self.pipeline, "source": self.source,
			"dimension_basis": "current", "open_pipeline_basis": "current",
		}


def distinct(rows: list[dict]) -> list[dict]:
	result = {}
	for row in rows:
		name = row.get("name")
		if not isinstance(name, str) or not name:
			raise AnalyticsInputError("Every source row requires an identity")
		if name in result and result[name] != row:
			raise AnalyticsInputError("Conflicting revisions in the source snapshot")
		result[name] = row
	return [result[name] for name in sorted(result)]


def money(row: dict, context: Context, field: str = "value") -> Decimal | None:
	value = number(row.get(field))
	if value is None or value < 0 or not row.get("currency") or row.get("currency_valid") is False:
		return None
	rate = Decimal(1) if row["currency"] == context.currency else number(row.get("exchange_rate"))
	if rate is None or rate <= 0:
		return None
	return context.round(value * rate)


def forecast_value(row: dict, context: Context) -> Decimal | None:
	# Preserve precision until the weighted currency line is rounded.
	value, probability = number(row.get("expected_value")), number(row.get("probability"))
	if value is None or value < 0 or probability is None or not 0 <= probability <= 100 or row.get("currency_valid") is False:
		return None
	rate = Decimal(1) if row.get("currency") == context.currency else number(row.get("exchange_rate"))
	if not row.get("currency") or rate is None or rate <= 0:
		return None
	return context.round(value * probability / 100 * rate)


def percent_change(current: Decimal | int, previous: Decimal | int) -> Decimal | None:
	return (Decimal(current) - Decimal(previous)) * 100 / Decimal(previous) if previous else None


def amount(rows: list[dict], context: Context, *, forecast: bool = False, extra_missing: int = 0, values_by_name: dict | None = None) -> dict:
	values = [values_by_name[row["name"]] if values_by_name is not None else
		(forecast_value(row, context) if forecast else money(row, context)) for row in rows]
	missing = sum(value is None for value in values) + extra_missing
	return {
		"value": sum((value for value in values if value is not None), Decimal(0)),
		"complete": missing == 0, "missing_count": missing,
		"known_count": sum(value is not None for value in values),
		"currency": context.currency,
	}


def outcome_date(row: dict) -> Any:
	# A Won date never stands in for the date of a Lost outcome.
	return row.get("closed_date") if row.get("status_type") == "Won" else row.get("lost_date")


def closing(rows: list[dict], kind: str, period: Period, context: Context) -> list[dict]:
	observed = context.as_of.astimezone(ZoneInfo(context.zone)).date()
	return [row for row in rows if row.get("status_type") == kind and period.contains(outcome_date(row), context.zone)
		and (when := calendar_date(outcome_date(row), context.zone)) is not None and when <= observed
		and (created := calendar_date(row.get("creation"), context.zone)) is not None and created <= when]


def aggregate_groups(rows: list[dict], key: str, context: Context, values_by_name=None) -> list[dict]:
	groups = defaultdict(list)
	for row in rows:
		groups[row.get(key) or ""].append(row)
	return [{"key": group, "count": len(items), **amount(items, context, values_by_name=values_by_name),
		"record_ids": [row["name"] for row in items]}
		for group, items in sorted(groups.items())]


def build_report(
	deals: list[dict], leads: list[dict], tasks: list[dict], context: Context,
	*, events: list[dict] | None = None, tasks_available: bool = True, include_snapshot: bool = True,
) -> dict:
	"""Return metrics plus the exact authorized selections used for drill-downs."""
	all_deals = distinct(deals)
	deals = [row for row in all_deals if context.includes(row)]
	all_leads = distinct(leads)
	leads = [row for row in all_leads if context.includes(row)]
	tasks = distinct(tasks)
	# Request-local values; no result survives this source snapshot.
	money_values = {row["name"]: money(row, context) for row in deals}
	forecast_values = {row["name"]: forecast_value(row, context) for row in deals}
	previous = context.period.previous
	observed = context.as_of.astimezone(ZoneInfo(context.zone)).date()
	observed_utc = context.as_of.astimezone(timezone.utc)
	won = closing(deals, "Won", context.period, context)
	lost = closing(deals, "Lost", context.period, context)
	old_won = closing(deals, "Won", previous, context)
	old_lost = closing(deals, "Lost", previous, context)
	new_leads = [row for row in leads if context.period.contains(row.get("creation"), context.zone) and calendar_date(row.get("creation"), context.zone) <= observed]
	old_leads = [row for row in leads if previous.contains(row.get("creation"), context.zone) and calendar_date(row.get("creation"), context.zone) <= observed]
	new_deals = [row for row in deals if context.period.contains(row.get("creation"), context.zone) and calendar_date(row.get("creation"), context.zone) <= observed]
	opened = [row for row in deals if row.get("status_type") in OPEN]
	unclassified = [row for row in deals if row.get("status_type") not in OPEN | CLOSED]
	forecast = [row for row in opened if context.horizon.contains(row.get("expected_date"), context.zone)]
	missing_forecast_date = [row for row in opened if calendar_date(row.get("expected_date"), context.zone) is None]
	missing_outcome_date = [row for row in deals if row.get("status_type") in CLOSED
		and calendar_date(outcome_date(row), context.zone) is None]
	by_deal = defaultdict(list)
	for task in tasks:
		if task.get("status") not in DONE_TASKS and task.get("reference_name"):
			by_deal[task["reference_name"]].append(task)
	attention = []
	stalled = []
	quality = defaultdict(list)
	for row in deals:
		if not row.get("source"):
			quality["missing_source"].append(row["name"])
		if row.get("currency_valid") is False:
			quality["unknown_currency"].append(row["name"])
		if money_values[row["name"]] is None:
			quality["unknown_or_invalid_amount"].append(row["name"])
	for row in missing_outcome_date:
		quality["missing_outcome_date"].append(row["name"])
	for row in unclassified:
		quality["unknown_stage_type"].append(row["name"])
	for row in deals:
		if row.get("status_type") in CLOSED and (closed := calendar_date(outcome_date(row), context.zone)) is not None:
			created = calendar_date(row.get("creation"), context.zone)
			if not created or closed < created or closed > observed:
				quality["invalid_outcome_date"].append(row["name"])
	for row in opened:
		facts = {}
		disabled = row.get("disabled_risk_rules", ())
		active_tasks = by_deal[row["name"]]
		if tasks_available and not active_tasks and "no_next_action" not in disabled:
			facts["no_next_action"] = {"count": 0}
		if tasks_available and "overdue_action" not in disabled:
			overdue = [due for task in active_tasks if (due := timestamp(task.get("due_date"), context.zone)) and due < context.as_of]
			if overdue:
				facts["overdue_action"] = {"at": min(overdue), "count": len(overdue)}
		if any(not timestamp(task.get("due_date"), context.zone) for task in active_tasks):
			quality["unscheduled_action"].append(row["name"])
		entered = timestamp(row.get("stage_entered_at"), context.zone)
		entered_utc = entered.astimezone(timezone.utc) if entered else None
		threshold = number(row.get("stale_days", context.stale_days))
		if entered_utc is None or entered_utc > observed_utc or not row.get("stage_history_complete", True):
			quality["incomplete_stage_history"].append(row["name"])
		elif threshold is not None and Decimal(str((observed_utc - entered_utc).total_seconds())) > threshold * 86400:
			stalled.append(row)
			if "long_stage" not in disabled:
				facts["long_stage"] = {"at": entered, "threshold_days": threshold}
		expected = calendar_date(row.get("expected_date"), context.zone)
		if expected is None:
			quality["missing_expected_date"].append(row["name"])
		elif expected < observed and "overdue_close" not in disabled:
			facts["overdue_close"] = {"at": expected}
		if row.get("close_date_pushed") and "pushed_close" not in disabled:
			facts["pushed_close"] = row.get("close_date_push") or {}
		if forecast_values[row["name"]] is None:
			quality["incomplete_forecast"].append(row["name"])
		if facts:
			attention.append({**row, "reasons": list(facts), "reason_facts": facts})
	cycles = []
	for row in won:
		created = calendar_date(row.get("creation"), context.zone)
		closed = calendar_date(row.get("closed_date"), context.zone)
		if not created or not closed or closed < created:
			quality["invalid_cycle"].append(row["name"])
		else:
			cycles.append(Decimal((closed - created).days))
	unknown_won_dates = sum(row.get("status_type") == "Won" for row in missing_outcome_date) + sum(
		row.get("status_type") == "Won" and row["name"] in quality["invalid_outcome_date"] for row in deals)
	won_amount = amount(won, context, values_by_name=money_values, extra_missing=unknown_won_dates)
	old_amount = amount(old_won, context, values_by_name=money_values, extra_missing=unknown_won_dates)
	rate = Decimal(len(won)) * 100 / (len(won) + len(lost)) if won or lost else None
	old_rate = Decimal(len(old_won)) * 100 / (len(old_won) + len(old_lost)) if old_won or old_lost else None
	metrics = {
		"new_leads": {"value": len(new_leads), "previous": len(old_leads), "delta": percent_change(len(new_leads), len(old_leads))},
		"new_deals": {"value": len(new_deals)},
		"won_count": {"value": len(won), "previous": len(old_won), "delta": percent_change(len(won), len(old_won)), "complete": not missing_outcome_date and not quality["invalid_outcome_date"] and not unclassified},
		"lost_count": {"value": len(lost), "complete": not missing_outcome_date and not quality["invalid_outcome_date"] and not unclassified},
		"won_value": {**won_amount, "previous": old_amount["value"],
			"delta": percent_change(won_amount["value"], old_amount["value"]) if won_amount["complete"] and old_amount["complete"] else None},
		"win_rate": {"value": rate, "previous": old_rate,
			"delta_pp": rate - old_rate if rate is not None and old_rate is not None else None,
			"complete": not missing_outcome_date and not quality["invalid_outcome_date"] and not unclassified},
		"median_cycle": {"value": median(cycles) if cycles else None, "unit": "days", "complete": len(cycles) == len(won) and not unknown_won_dates},
		"open_count": {"value": len(opened), "complete": not unclassified, "basis": "current"},
		"open_value": {**amount(opened, context, values_by_name=money_values, extra_missing=len(unclassified)), "basis": "current"},
		"forecast": {**amount(forecast, context, values_by_name=forecast_values, forecast=True, extra_missing=len(missing_forecast_date) + len(unclassified)), "basis": "horizon"},
		"risk_count": {"value": len(attention), "basis": "current"},
		"risk_value": {**amount(attention, context, values_by_name=money_values), "basis": "current"},
		"stalled_value": {**amount(stalled, context, values_by_name=money_values), "basis": "current"},
	}
	known_won = [value for row in won if (value := money_values[row["name"]]) is not None]
	metrics["average_won_value"] = {"value": context.round(sum(known_won) / len(known_won)) if known_won else None,
		"complete": won_amount["complete"], "known_count": len(known_won), "basis": "period"}
	metrics["median_won_value"] = {"value": median(known_won) if known_won else None,
		"complete": won_amount["complete"], "known_count": len(known_won), "basis": "period"}
	metrics["average_cycle"] = {"value": sum(cycles) / len(cycles) if cycles else None,
		"complete": metrics["median_cycle"]["complete"], "unit": "days", "basis": "period"}
	lead_by_id = {row["name"]: row for row in all_leads}
	lead_cycles = []
	linked_won = [row for row in won if row.get("lead")]
	for row in linked_won:
		lead = lead_by_id.get(row["lead"])
		start = calendar_date(lead.get("creation"), context.zone) if lead else None
		end = calendar_date(row.get("closed_date"), context.zone)
		if start and end and end >= start:
			lead_cycles.append(Decimal((end - start).days))
	metrics["lead_cycle"] = {"value": median(lead_cycles) if lead_cycles else None, "unit": "days", "basis": "period",
		"complete": len(lead_cycles) == len(linked_won), "direct_deals": len(won) - len(linked_won), "known_count": len(lead_cycles)}
	for key in ("new_leads", "new_deals", "won_count", "lost_count", "won_value", "win_rate", "median_cycle"):
		metrics[key]["basis"] = "period"
		metrics[key].setdefault("complete", True)
	selections = {key: [row["name"] for row in rows] for key, rows in {
		"new_leads": new_leads, "new_deals": new_deals, "won_count": won, "won_value": won,
		"lost_count": lost, "win_rate": won + lost, "median_cycle": won,
		"open_count": opened, "open_value": opened, "forecast": forecast,
		"risk_count": attention, "risk_value": attention, "stalled_value": stalled,
		"average_won_value": won, "median_won_value": won, "average_cycle": won, "lead_cycle": linked_won,
	}.items()}
	daily = defaultdict(lambda: {"new_leads": 0, "new_deals": 0, "won_count": 0, "won_value": Decimal(0)})
	for row in new_leads:
		daily[str(calendar_date(row["creation"], context.zone))]["new_leads"] += 1
	for row in new_deals:
		daily[str(calendar_date(row["creation"], context.zone))]["new_deals"] += 1
	for row in won:
		day = daily[str(calendar_date(row["closed_date"], context.zone))]
		day["won_count"] += 1
		if (value := money_values[row["name"]]) is not None:
			day["won_value"] += value
	# Missing days are generated only through the snapshot's local day.
	days = []
	day = context.period.start
	while day <= min(context.period.end, context.as_of.astimezone(ZoneInfo(context.zone)).date()):
		days.append({"date": str(day), **daily[str(day)]})
		day += timedelta(days=1)
	cohort_ids = {row["name"] for row in new_deals}
	visited = defaultdict(set)
	stage_entries = defaultdict(int)
	stage_changes = 0
	for event in distinct(events or []):
		occurred = timestamp(event.get("occurred_at"), context.zone)
		if event.get("deal") not in cohort_ids or occurred is None or occurred > context.as_of:
			continue
		before_stage, after_stage = event.get("from_stage"), event.get("to_stage")
		if after_stage and before_stage != after_stage:
			stage_entries[after_stage] += 1
			if before_stage:
				stage_changes += 1
		for stage in (before_stage, after_stage):
			if stage:
				visited[stage].add(event["deal"])
	cohort_leads = {row["name"] for row in new_leads}
	# A lead cohort is selected by the lead's dimensions. Related deals must not
	# be filtered again by a different owner/source after a handoff or correction.
	linked = [row for row in all_deals if row.get("lead") in cohort_leads]
	converted = {row["name"] for row in new_leads if row.get("converted") in (True, 1, "1")}
	converted.update(row["lead"] for row in linked)
	cohort_won_leads = {row["lead"] for row in linked if row.get("status_type") == "Won"
		and (closed := calendar_date(row.get("closed_date"), context.zone)) is not None
		and closed <= context.as_of.astimezone(ZoneInfo(context.zone)).date()}
	unresolved_conversions = converted - {row["lead"] for row in linked}
	report = {
		"context": context.metadata(), "metrics": metrics, "selections": selections,
		"trend": days, "attention": attention,
		"quality": [{"code": code, "count": len(set(names)), "record_ids": sorted(set(names))} for code, names in sorted(quality.items()) if names],
		"sources": aggregate_groups(won, "source", context, money_values),
		"owners": aggregate_groups(won, "owner", context, money_values),
		"closing_owners": aggregate_groups(won, "outcome_owner", context, money_values),
		"open_owners": aggregate_groups(opened, "owner", context, money_values),
		"open_pipelines": aggregate_groups(opened, "pipeline", context, money_values),
		"stages": aggregate_groups(opened, "status", context, money_values),
		"funnel": {
			"basis": "creation_cohort", "cohort_count": len(new_deals),
			"won": sum(row.get("status_type") == "Won" for row in new_deals),
			"lost": sum(row.get("status_type") == "Lost" for row in new_deals),
			"visited": [{"stage": stage, "count": len(names), "entry_events": stage_entries[stage],
				"record_ids": sorted(names)} for stage, names in sorted(visited.items())],
			"stage_changes": stage_changes,
			"known_from_creation": sum(row.get("path_history_complete") is True for row in new_deals),
			"lead_count": len(cohort_leads), "converted_leads": len(converted), "won_leads": len(cohort_won_leads),
			"outcome_complete": not unresolved_conversions, "unresolved_conversions": len(unresolved_conversions),
		},
	}
	report["source_cohorts"] = [{"key": source or "", "leads": len(items),
		"converted": sum(row["name"] in converted for row in items),
		"won": sum(row["name"] in cohort_won_leads for row in items),
		"outcome_complete": not bool({row["name"] for row in items} & unresolved_conversions),
		"record_ids": [row["name"] for row in items]}
		for source in sorted({row.get("source") or "" for row in new_leads})
		if (items := [row for row in new_leads if (row.get("source") or "") == source])]
	if include_snapshot:
		encoded = json.dumps(report, default=str, sort_keys=True, ensure_ascii=False).encode()
		report["snapshot"] = hashlib.sha256(encoded).hexdigest()
	return report
