"""Call facts shared by CRM analytics views. Private call content stays in the journal."""

from collections import Counter, defaultdict
import csv
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
import hashlib
import hmac
import io
from math import ceil
from statistics import median
from time import time as now_seconds

import frappe
from frappe import _

from crm.analytics.call_sla import callback_state, completed_callback_state
from crm.analytics.call_sla_settings import actual_schedule, can_manage
from crm.analytics.engine import number, timestamp
from crm.analytics.sales_plans import can_manage_team, plan_scope, team_members
from crm.analytics.service import (
	_csv_cell, _sign, _verify, coherent_read, exact_json, normalize_filters, readable_rows, related_scope, snapshot_hash,
)
from crm.integrations.exolve.coverage import recent_windows
from crm.utils import sales_user_only
from crm.permissions.org_hierarchy import hierarchy_enabled

CALL = "CRM Call Log"
OUTCOME = "CRM Call Outcome"
REFERENCES = {"CRM Lead", "CRM Deal", "Contact"}
MISSED = {"No Answer", "Busy", "Failed", "Canceled"}
CALL_FIELDS = [
	"name", "type", "status", "caller", "receiver", "start_time", "creation", "duration",
	"end_time", "analytics_connected_at",
	"from", "to", "reference_doctype", "reference_docname", "recording_url", "telephony_medium",
]
REQUIRED = {"name", "type", "status", "start_time", "creation", "caller", "receiver", "reference_doctype", "reference_docname"}
TERMINAL = MISSED | {"Completed"}
OUTCOMES = {"Agreed", "Callback", "Not interested", "Wrong number"}
CUTS = {"from_date", "to_date", "employee", "line", "direction", "outcome", "pipeline", "source"}
GROUPS = {"teams", "employees", "lines", "days", "weeks", "hours", "weekdays", "outcomes", "sla"}
COMPARISON_GROUPS = {"teams", "employees", "lines", "hours", "weekdays"}
METRICS = {"total", "incoming", "outgoing", "other_direction", "completed", "connected", "missed", "recorded",
	"on_time", "overdue", "pending", "late", "unavailable"}
RATE_METRICS = {
	"answer_rate_incoming": ("incoming", "duration"),
	"answer_rate_outgoing": ("outgoing", "duration"),
	"sla_percent": ("missed", "sla"),
}
SLA_DECIDED = {"on_time", "late", "overdue"}


def _batch(values):
	items = sorted(set(values) - {None, ""})
	for start in range(0, len(items), 400):
		yield items[start:start + 400]


def read_named(doctype, fields, names):
	for batch in _batch(names):
		rows, _fields = readable_rows(doctype, fields, {"name": ["in", batch]})
		yield from rows


def _context_scope(rows):
	pending = defaultdict(set)
	for row in rows:
		if row.get("reference_doctype") in REFERENCES and row.get("reference_docname"):
			pending[row["reference_doctype"]].add(row["reference_docname"])
	return {
		key: {row["name"] for row in read_named(key, ["name"], names)}
		for key, names in pending.items()
	}


def _has_context(row, allowed):
	kind, name = row.get("reference_doctype"), row.get("reference_docname")
	if not name:
		return kind in (None, "", "CRM Lead")
	return name in allowed.get(kind, ())


def _employee(row):
	return row.get({"Incoming": "receiver", "Outgoing": "caller"}.get(row.get("type"), ""))


def _interval(ctx):
	"""Include legacy rows missing start_time via their native creation timestamp."""
	start = datetime.combine(ctx.period.start, time.min)
	end = min(datetime.combine(ctx.period.end, time.max), ctx.as_of.replace(tzinfo=None))
	rows, fields = readable_rows(CALL, CALL_FIELDS, {"start_time": ["between", [start, end]]})
	legacy, legacy_fields = readable_rows(CALL, CALL_FIELDS,
		{"start_time": ["is", "not set"], "creation": ["between", [start, end]]})
	return rows + legacy, fields & legacy_fields


def _initial_rows(ctx, owners, related):
	rows, fields = _interval(ctx)
	if not REQUIRED <= fields:
		frappe.throw(_("Call analytics is unavailable with your current access."), frappe.PermissionError)
	allowed = _context_scope(rows)
	return [
		row for row in rows
		if _has_context(row, allowed)
		and (owners is None or _employee(row) in owners)
		and (not ctx.owner or _employee(row) == ctx.owner)
		and (related is None or row.get("reference_docname") in related.get(row.get("reference_doctype"), ()))
	], fields


def _line(row, secret):
	number = row.get({"Incoming": "to", "Outgoing": "from"}.get(row.get("type"), "")) or ""
	if not number:
		return "", ""
	key = hmac.new(secret, str(number).encode(), hashlib.sha256).hexdigest()[:24]
	suffix = "".join(char for char in str(number) if char.isdigit())[-4:]
	return key, "•••• " + suffix if suffix else "••••"


def _load_followups(rows, observed_at, zone, owners):
	if not frappe.db.table_exists(OUTCOME) or not frappe.db.has_column(OUTCOME, "callback_linked_at"):
		return False, {}, {}
	if not rows:
		return True, {}, {}
	reviews = []
	for batch in _batch(row["name"] for row in rows):
		reviews.extend(frappe.get_all(OUTCOME, filters={"call_log": ["in", batch]},
			fields=["call_log", "outcome", "reference_doctype", "reference_docname",
				"processed_at", "callback_call", "callback_linked_at", "callback_task"]))
	allowed = _context_scope(reviews)
	valid = defaultdict(list)
	for review in reviews:
		processed = timestamp(review.get("processed_at"), zone)
		if (processed and processed <= observed_at and _has_context(review, allowed)
			and review.outcome in OUTCOMES):
			valid[review.call_log].append(review)
	canonical = {key: candidates[0] for key, candidates in valid.items() if len(candidates) == 1}
	callbacks = list(read_named(CALL, CALL_FIELDS, (review.callback_call for review in canonical.values())))
	callback_context = _context_scope(callbacks)
	return True, canonical, {
		row["name"]: row for row in callbacks if _has_context(row, callback_context)
		and (owners is None or _employee(row) in owners)
	}


def _connected(row):
	duration = number(row.get("duration"))
	# CRM uses provider duration as a transport signal. Outcome is independent.
	return row.get("status") == "Completed" and duration is not None and duration > 0


def _task_links(rows, reviews, zone):
	if not frappe.has_permission("CRM Task", "read"):
		return None, {}
	parents = defaultdict(set)
	for name, review in reviews.items():
		if review.callback_task:
			parents[name].add(str(review.callback_task))
	for batch in _batch(row["name"] for row in rows):
		for link in frappe.get_all("Dynamic Link", filters={"parent": ["in", batch],
			"parenttype": CALL, "parentfield": "links", "link_doctype": "CRM Task"},
			fields=["parent", "link_name"]):
			parents[link.parent].add(str(link.link_name))
	task_rows = list(read_named("CRM Task", ["name", "status", "due_date", "reference_doctype",
		"reference_docname"], (name for names in parents.values() for name in names)))
	allowed = _context_scope(task_rows)
	tasks = {}
	for row in task_rows:
		if "status" not in row or not _has_context(row, allowed):
			continue
		status = row["status"]
		due = timestamp(row.get("due_date"), zone)
		tasks[str(row["name"])] = status, due
	parents = {key: sorted(names & tasks.keys()) for key, names in parents.items()}
	return tasks, parents


def call_facts(ctx, *, line=None, direction=None, outcome=None, related=None):
	"""Select permitted calls, then fold explicit callback and task evidence."""
	_, owners = plan_scope()
	rows, fields = _initial_rows(ctx, owners, related)
	hours, minutes, require_original_employee = actual_schedule()
	outcomes_available, reviews, callbacks = _load_followups(rows, ctx.as_of, ctx.zone, owners)
	tasks, linked = _task_links(rows, reviews, ctx.zone)
	if outcome and not outcomes_available:
		frappe.throw(_("Call outcomes are unavailable on this site."), frappe.ValidationError)
	secret = frappe.local.conf.get("encryption_key", "").encode()
	if not secret:
		frappe.throw(_("Analytics signing is not configured."))
	facts = []
	for row in rows:
		at = timestamp(row.get("start_time") or row.get("creation"), ctx.zone)
		if not at or at > ctx.as_of or not ctx.period.contains(at, ctx.zone):
			continue
		kind = row.get("type") if row.get("type") in ("Incoming", "Outgoing") else ""
		line_key, label = _line(row, secret) if {"from", "to"} <= fields else ("", "")
		review = reviews.get(row["name"])
		result = review.outcome if review else ""
		if (line and line_key != line) or (direction and direction != (kind or "unknown")) or (outcome and outcome != (result or "unprocessed")):
			continue
		missed = kind == "Incoming" and row.get("status") in MISSED
		reply = callbacks.get(review.callback_call) if missed and review else None
		link_at = timestamp(review.get("callback_linked_at"), ctx.zone) if review else None
		attempt = timestamp(reply.get("start_time") or reply.get("creation"), ctx.zone) if reply else None
		if not (attempt and link_at and at.astimezone(timezone.utc) < attempt.astimezone(timezone.utc)
			<= link_at.astimezone(timezone.utc) <= ctx.as_of.astimezone(timezone.utc) and reply.get("type") == "Outgoing"):
			attempt = reply = None
		callback_connected = bool(reply and _connected(reply))
		connected = timestamp(reply.get("analytics_connected_at"), ctx.zone) if callback_connected else None
		ended = timestamp(reply.get("end_time"), ctx.zone) if callback_connected else None
		if connected:
			answer = connected.astimezone(timezone.utc)
			last_possible = min(link_at.astimezone(timezone.utc), (ended or ctx.as_of).astimezone(timezone.utc))
			if not attempt.astimezone(timezone.utc) <= answer <= last_possible:
				connected = None
		deadline = hours.deadline(at, minutes) if missed and hours and outcomes_available and "duration" in fields else None
		callback_sla_exclusion = None
		if deadline is not None and callback_connected and require_original_employee:
			assigned, answered_by = _employee(row), _employee(reply)
			if not assigned or not answered_by:
				callback_sla_exclusion = "employee_unknown"
			elif assigned != answered_by:
				callback_sla_exclusion = "different_employee"
		sla = ""
		if missed:
			if callback_connected and not callback_sla_exclusion:
				sla = completed_callback_state(deadline, ctx.as_of, attempt, ended, connected)
			else:
				sla = callback_state(deadline, ctx.as_of)
		facts.append({
			"name": row["name"], "at": at, "direction": kind, "employee": _employee(row) or "",
			"line": line_key, "line_label": label, "status": row.get("status"),
			"duration": number(row.get("duration")), "connected": _connected(row) if "duration" in fields else None,
			"recorded": bool(row.get("recording_url")) if "recording_url" in fields else None,
			"missed": missed, "outcome": result, "tasks": linked.get(row["name"], []),
			"parent_type": row.get("reference_doctype"), "parent_name": row.get("reference_docname"),
			"callback": reply["name"] if reply else None, "attempt_at": attempt, "connected_at": connected,
			"callback_connected": callback_connected, "callback_sla_exclusion": callback_sla_exclusion,
			"attempt_seconds": (attempt.astimezone(timezone.utc) - at.astimezone(timezone.utc)).total_seconds() if attempt else None,
			"conversation_seconds": (connected.astimezone(timezone.utc) - at.astimezone(timezone.utc)).total_seconds() if connected else None,
			"deadline": deadline, "sla": sla,
			"date_basis": "start_time" if row.get("start_time") else "creation",
		})
	return sorted(facts, key=lambda row: (row["at"], row["name"]), reverse=True), tasks, {
		"outcomes": outcomes_available, "sla": bool(hours and outcomes_available and "duration" in fields),
		"require_original_employee": require_original_employee,
		"recordings": "recording_url" in fields, "duration": "duration" in fields,
	}


def _summary(rows, caps):
	counts = Counter()
	rate_counts = {}
	for metric, (_population, capability) in RATE_METRICS.items():
		if caps[capability]:
			rate_counts[metric] = Counter()
	for row in rows:
		for key, matches in _selections(row).items():
			if matches:
				counts[key] += 1
		for metric, outcomes in rate_counts.items():
			match = _rate_match(row, metric)
			if match is not None:
				outcomes[match] += 1
	bases = {}
	rates = {}
	for metric, (population, _capability) in RATE_METRICS.items():
		outcomes = rate_counts.get(metric)
		eligible = outcomes.total() if outcomes is not None else None
		bases[metric] = {
			"matched": outcomes[True], "eligible": eligible, "excluded": counts[population] - eligible,
		} if eligible is not None else None
		rates[metric] = 100 * outcomes[True] / eligible if eligible else None
	attempts = [row["attempt_seconds"] for row in rows if row["attempt_seconds"] is not None]
	conversations = [row["conversation_seconds"] for row in rows if row["conversation_seconds"] is not None]
	duration = [row["duration"] for row in rows if row["status"] == "Completed" and row["duration"] is not None and row["duration"] >= 0]
	return {
		**{key: counts[key] for key in sorted(METRICS)},
		"connected": counts["connected"] if caps["duration"] else None,
		"recorded": counts["recorded"] if caps["recordings"] else None,
		**rates,
		"rate_bases": bases,
		**{state: counts[state] if caps["sla"] else None for state in ("pending", "on_time", "late", "overdue")},
		"duration_seconds": sum(duration) if caps["duration"] else None,
		"average_seconds": sum(duration) / len(duration) if duration else None,
		"attempts_confirmed": len(attempts),
		"connections_timed": len(conversations),
		"median_attempt_seconds": median(attempts) if attempts else None,
		"p90_attempt_seconds": sorted(attempts)[ceil(len(attempts) * .9) - 1] if len(attempts) >= 10 else None,
		"median_conversation_seconds": median(conversations) if conversations else None,
		"p90_conversation_seconds": sorted(conversations)[ceil(len(conversations) * .9) - 1] if len(conversations) >= 10 else None,
		"sla_decided": bases["sla_percent"]["eligible"] if caps["sla"] else None,
		"outcome_known": sum(bool(row["outcome"]) for row in rows) if caps["outcomes"] else None,
	}


def _rate_match(row, metric):
	"""Return True or False only for calls included in this rate's denominator."""
	if metric == "sla_percent":
		return row["sla"] == "on_time" if row["sla"] in SLA_DECIDED else None
	population, _capability = RATE_METRICS[metric]
	return answer_outcome(row) if row["direction"].lower() == population else None


def answer_outcome(row):
	if row["connected"]:
		return True
	if row["status"] in MISSED:
		return False
	# A technical completion without confirmed conversation cannot decide this outcome.
	return None


def _selections(row):
	return {
		"total": True, "incoming": row["direction"] == "Incoming", "outgoing": row["direction"] == "Outgoing",
		"other_direction": not row["direction"], "completed": row["status"] == "Completed",
		"connected": row["connected"], "missed": row["missed"], "recorded": row["recorded"],
		**{state: row["sla"] == state for state in ("pending", "on_time", "overdue", "late", "unavailable")},
	}


def _group_values(row):
	day = row["at"].date()
	return {
		"employees": row["employee"], "lines": row["line"], "days": day.isoformat(),
		"weeks": (day - timedelta(days=day.weekday())).isoformat(),
		"hours": str(row["at"].hour).zfill(2), "weekdays": str(day.weekday()),
		"outcomes": row["outcome"], "sla": row["sla"],
	}


def _task_counts(rows, tasks, as_of):
	if tasks is None:
		return None
	visible_tasks = {name for row in rows for name in row["tasks"]}
	counts = dict(total=len(visible_tasks), done=0, canceled=0, open=0, overdue=0)
	for name in visible_tasks:
		status, due = tasks[name]
		category = "done" if status in ("Done", "Completed") else "canceled" if status in ("Canceled", "Cancelled") else "open"
		counts[category] += 1
		counts["overdue"] += int(category == "open" and bool(due and due < as_of))
	return counts


def _call_context(filters, *, observed_at=None):
	ctx = normalize_filters({"from_date": filters.get("from_date"), "to_date": filters.get("to_date"),
		"owner": filters.get("employee"), "pipeline": filters.get("pipeline"), "source": filters.get("source")},
		observed_at=observed_at)
	if ctx.period.start > ctx.as_of.date():
		frappe.throw(_("The call reporting period has not begun."), frappe.ValidationError)
	return ctx


def _make_report(filters, ctx=None):
	ctx = ctx or _call_context(filters)
	related = None
	if ctx.pipeline or ctx.source:
		from crm.analytics.service import source_snapshot

		deals, leads, *_ = source_snapshot(ctx)
		related = related_scope(deals, leads, replace(ctx, owner=None))
	rows, tasks, caps = call_facts(ctx, line=filters.get("line"), direction=filters.get("direction"),
		outcome=filters.get("outcome"), related=related)
	grouped = {key: defaultdict(list) for key in GROUPS}
	eligible_teams = []
	if hierarchy_enabled() and plan_scope()[0]:
		eligible_teams = frappe.get_all("CRM Sales Hierarchy", filters={"is_group": 1}, pluck="user")
	teams_by_employee = defaultdict(list)
	for lead in eligible_teams:
		if can_manage_team(lead):
			for member in team_members(lead):
				teams_by_employee[member].append(lead)
	for row in rows:
		for key, value in _group_values(row).items():
			grouped[key][value].append(row)
		for lead in teams_by_employee.get(row["employee"], ()):
			grouped["teams"][lead].append(row)
	groups = {}
	for key, buckets in grouped.items():
		if key == "outcomes" and not caps["outcomes"]:
			groups[key] = []
			continue
		groups[key] = []
		for name, items in sorted(buckets.items()):
			label = name
			if key in ("employees", "teams") and name:
				label = frappe.get_cached_value("User", name, "full_name") or name
			elif key == "lines":
				label = items[0]["line_label"]
			entry = {"key": name, "label": label, **_summary(items, caps)}
			if key in COMPARISON_GROUPS:
				task_counts = _task_counts(items, tasks, ctx.as_of)
				entry["linked_tasks"] = task_counts["total"] if task_counts is not None else None
				entry["overdue_tasks"] = task_counts["overdue"] if task_counts is not None else None
			groups[key].append(entry)
	counts = _task_counts(rows, tasks, ctx.as_of)
	context = ctx.metadata()
	report = {"period": context, "metrics": _summary(rows, caps), "groups": groups,
		"tasks": counts, "can_manage_sla": can_manage(), "coverage": {**caps,
			"creation_fallback": sum(row["date_basis"] == "creation" for row in rows),
			"first_call_at": rows[-1]["at"] if rows else None,
			"last_call_at": rows[0]["at"] if rows else None,
		}}
	team_calls = {lead: [row["name"] for row in items] for lead, items in grouped["teams"].items()}
	comparison_groups = {key: groups[key] for key in COMPARISON_GROUPS}
	revision = snapshot_hash(rows, report["metrics"], counts, caps, comparison_groups, team_calls,
		{key: value for key, value in context.items() if key != "as_of"})
	return report, rows, revision


def _filters(filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else filters or {}
	if (not isinstance(filters, dict) or set(filters) - CUTS
		or any(value is not None and (not isinstance(value, str) or len(value) > 180) for value in filters.values())
		or filters.get("direction") not in (None, "", "Incoming", "Outgoing", "unknown")
		or filters.get("outcome") not in (None, "", "unprocessed", *OUTCOMES)):
		frappe.throw(_("Invalid call analytics filters."), frappe.ValidationError)
	return filters


@frappe.whitelist(methods=["POST"])
@sales_user_only
@coherent_read
def telephony_scope(period: str = "30", employee: str = "", line: str = "", outcome: str = "", view: str = "all"):
	"""Convert enabled journal filters to an analytics link without a phone number in the URL."""
	from crm.api.telephony import filtered_query, get_filter_options
	from frappe.query_builder.functions import Coalesce

	direction = {"incoming": "Incoming", "outgoing": "Outgoing"}.get(view, "")
	_filters({"employee": employee, "line": line, "outcome": outcome, "direction": direction})
	today = normalize_filters().as_of.date()
	days = {"today": 1, "7": 7, "30": 30, "all": 3660}.get(period)
	if days is None:
		frappe.throw(_("Choose a valid call period."), frappe.ValidationError)
	start = today - timedelta(days=days - 1)
	if period == "all":
		table = frappe.qb.DocType(CALL)
		at = Coalesce(table.start_time, table.creation)
		rows = filtered_query("", view, period, 0, employee, line, outcome).orderby(at).limit(1).run(as_dict=True)
		if rows:
			value = rows[0].get("start_time") or rows[0].get("creation")
			if value:
				start = max(start, min(frappe.utils.getdate(value), today))
	result = {"from_date": str(start), "to_date": str(today), "owner": employee,
		"call_direction": direction, "call_outcome": outcome}
	if line and line in get_filter_options()["lines"]:
		secret = frappe.local.conf.get("encryption_key", "").encode()
		if secret:
			result["call_line"] = _line({"type": "Incoming", "to": line}, secret)[0]
	return result


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_report(filters: dict | str | None = None, include_comparison: bool = False):
	filters = _filters(filters)
	ctx = _call_context(filters)
	report, _rows, revision = _make_report(filters, ctx)
	report["coverage"]["exolve_windows"] = recent_windows(plan_scope()[1], ctx.owner)
	report["snapshot"] = revision
	report["snapshot_token"] = _report_token(filters, revision)
	if include_comparison:
		previous = ctx.period.previous
		previous_filters = filters | {"from_date": str(previous.start), "to_date": str(previous.end)}
		baseline, _rows, version = _make_report(previous_filters, replace(ctx, period=previous))
		report["comparison"] = {"period": baseline["period"], "metrics": baseline["metrics"],
			"coverage": baseline["coverage"], "snapshot_token": _report_token(previous_filters, version),
			"employees": [{"key": row["key"], "label": row["label"]} for row in baseline["groups"]["employees"]],
		}
	return exact_json(report)


def _report_token(filters, revision):
	return _sign({"user": frappe.session.user, "site": frappe.local.site,
		"purpose": "calls", "filters": filters, "snapshot": revision, "expires": now_seconds() + 120})


def _select(token, metric, group, group_key):
	payload = _verify(token)
	is_rate = metric in RATE_METRICS
	if payload.get("purpose") != "calls" or (not is_rate and metric not in METRICS) or group not in (None, "", *GROUPS):
		frappe.throw(_("Invalid call analytics selection."), frappe.ValidationError)
	report, rows, revision = _make_report(_filters(payload["filters"]))
	if revision != payload["snapshot"]:
		frappe.throw(_("The report changed. Refresh the call figures."), frappe.TimestampMismatchError)
	value = report["metrics"]["rate_bases"][metric] if is_rate else report["metrics"][metric]
	if value is None:
		frappe.throw(_("This metric is unavailable with your current access."), frappe.PermissionError)
	if group == "teams":
		valid = any(team["key"] == group_key for team in report["groups"]["teams"])
		members = team_members(group_key) if valid else set()
		rows = [row for row in rows if row["employee"] in members]
	elif group:
		rows = [row for row in rows if _group_values(row)[group] == group_key]
	if is_rate:
		return [dict(row, rate_match=match) for row in rows if (match := _rate_match(row, metric)) is not None], revision
	return [row for row in rows if _selections(row)[metric]], revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(snapshot_token: str, metric: str = "total", group: str | None = None,
	group_key: str | None = None, start: int = 0, limit: int = 50):
	rows, revision = _select(snapshot_token, metric, group, group_key)
	start, limit = max(0, start), min(200, max(1, limit))
	result = {"rows": rows[start:start + limit], "total": len(rows), "snapshot": revision}
	if metric in RATE_METRICS:
		result["matched"] = sum(row["rate_match"] for row in rows)
	return exact_json(result)


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export_details(snapshot_token: str, metric: str = "total", group: str | None = None, group_key: str | None = None):
	rows, revision = _select(snapshot_token, metric, group, group_key)
	output = io.StringIO(newline="")
	writer = csv.writer(output, lineterminator="\r\n")
	columns = ("name", "at", "direction", "employee", "line_label", "status", "outcome",
		"recorded", "duration", "callback", "attempt_at", "connected_at", "deadline", "sla", "callback_connected",
		"callback_sla_exclusion")
	if metric in RATE_METRICS:
		columns += ("rate_match",)
	writer.writerow(columns)
	for row in exact_json(rows):
		writer.writerow([_csv_cell(int(row[key]) if key == "rate_match" else row[key]) for key in columns])
	result = {"filename": "crm-call-analytics.csv", "csv": output.getvalue(), "total": len(rows), "snapshot": revision}
	if metric in RATE_METRICS:
		result["matched"] = sum(row["rate_match"] for row in rows)
	return result
