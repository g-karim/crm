"""Confirmed deal transitions and the known stage distribution at two dates."""

from collections import Counter, defaultdict
import csv
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import io
from statistics import median
from time import time as now_seconds
from urllib.parse import quote
from zoneinfo import ZoneInfo

import frappe
from frappe import _

from crm.analytics.engine import distinct
from crm.analytics.service import (
	_csv_cell, _sign, _verify, coherent_read, exact_json, normalize_filters, snapshot_hash, source_snapshot,
)
from crm.utils import sales_user_only


def _instant(value, zone):
	try:
		observed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	except (TypeError, ValueError):
		return None
	if observed.tzinfo is None:
		observed = observed.replace(tzinfo=ZoneInfo(zone))
		if observed.replace(fold=0).utcoffset() != observed.replace(fold=1).utcoffset():
			return None  # A legacy local wall time can fall in either of two hours.
	return observed.astimezone(timezone.utc)


def summarize(deals, events, ctx, labels):
	zone = ZoneInfo(ctx.zone)
	first = datetime.combine(ctx.period.start, time.min, zone).astimezone(timezone.utc)
	next_day = datetime.combine(ctx.period.end + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
	as_of = ctx.as_of.astimezone(timezone.utc)
	if first > as_of:
		return {"available": False, "reason": "in_future"}, {}
	by_deal = defaultdict(list)
	unknown_time = set()
	scoped = {row["name"]: row for row in deals if ctx.includes(row)}
	for event in distinct(events):
		if event["deal"] not in scoped:
			continue
		occurred = _instant(event.get("occurred_at"), ctx.zone)
		if occurred is None:
			unknown_time.add(event["deal"])
		elif occurred <= as_of and event.get("to_stage"):
			by_deal[event["deal"]].append((occurred, event))
	movements, prior, later = defaultdict(list), Counter(), Counter()
	eligible = known = 0
	# Expired/missing history is represented in coverage, not extrapolated.
	for name, deal in scoped.items():
		created = _instant(deal.get("creation"), ctx.zone)
		if created and (created >= next_day or created > as_of):
			continue
		eligible += 1
		events = sorted(by_deal[name], key=lambda item: (item[0], item[1]["name"]))
		start_stage = end_stage = None
		stage = stage_at = None
		complete = bool(deal.get("path_history_complete") and events and events[0][1]["from_stage"] is None
			and name not in unknown_time)
		for at, event in events:
			before, after = event["from_stage"], event["to_stage"]
			compatible = stage == before
			# Durations belong to the stage being left, across date windows.
			if before and before != after and first <= at < next_day:
				seconds = Decimal(str((at - stage_at).total_seconds())) if compatible and stage_at and name not in unknown_time else None
				movements[before, after].append({
					"name": event["name"], "deal": name, "title": deal["title"], "at": at,
					"from_label": labels.get(before, before), "to_label": labels.get(after, after),
					"duration_seconds": seconds, "path": "/crm/deals/" + quote(name, safe=""),
				})
			if not compatible or (created is not None and at < created and (created - at).total_seconds() >= 1):
				complete = False
			stage, stage_at = after, at
			if at < first:
				start_stage = stage
			if at < next_day:
				end_stage = stage
		if complete and created and stage == deal.get("status") and end_stage:
			known += 1
			if start_stage:
				prior[start_stage] += 1
			later[end_stage] += 1
	rows, selections = [], {}
	for (before, after), items in movements.items():
		key = snapshot_hash(before, after)[:24]
		selections[key] = sorted(items, key=lambda item: (item["at"], item["name"]), reverse=True)
		durations = [item["duration_seconds"] for item in items if item["duration_seconds"] is not None]
		rows.append({"key": key, "from_label": labels.get(before, before), "to_label": labels.get(after, after),
			"moves": len(items), "deals": len({item["deal"] for item in items}), "duration_count": len(durations),
			"median_days": ((median(durations) / Decimal(86400)).quantize(Decimal("0.01")) if durations else None)})
	rows.sort(key=lambda row: (-row["moves"], row["from_label"], row["to_label"], row["key"]))
	stages = [{"key": stage, "label": labels.get(stage, stage), "start": prior[stage], "end": later[stage],
		"change": later[stage] - prior[stage]} for stage in sorted(prior.keys() | later.keys())]
	return {"available": True, "eligible": eligible, "known": known, "from_date": ctx.period.start,
		"to_date": ctx.period.end, "rows": rows, "stages": stages}, selections


def _calculate(filters):
	ctx = normalize_filters(filters)
	deals, _leads, _tasks, events, caps, statuses = source_snapshot(ctx)
	if not caps["history"]:
		return {"available": False, "reason": "history_unavailable"}, {}, ""
	labels = {key: f"{row.deal_status or key} · {row.pipeline}" if row.pipeline else row.deal_status or key
		for key, row in statuses.items()}
	report, rows = summarize(deals, events, ctx, labels)
	return report, rows, snapshot_hash(report, rows)


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_movement(filters: dict | str | None = None):
	report, _rows, revision = _calculate(filters)
	if report["available"]:
		report["token"] = _sign({"purpose": "movement", "site": frappe.local.site, "user": frappe.session.user,
			"filters": filters, "revision": revision, "expires": now_seconds() + 120})
	return exact_json(report)


def _selection(token, group):
	payload = _verify(token)
	if payload.get("purpose") != "movement":
		frappe.throw(_("Invalid movement selection."), frappe.ValidationError)
	report, rows, revision = _calculate(payload["filters"])
	if not report["available"] or revision != payload["revision"]:
		frappe.throw(_("The movement report changed. Refresh the figures."), frappe.TimestampMismatchError)
	return rows.get(group, []), revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(token: str, group: str, start: int = 0):
	rows, _revision = _selection(token, group)
	start = max(0, start)
	return exact_json({"rows": rows[start:start + 50], "total": len(rows)})


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export(token: str, group: str):
	rows, revision = _selection(token, group)
	output = io.StringIO(newline="")
	writer = csv.writer(output, lineterminator="\r\n")
	columns = ("deal", "title", "at", "from_label", "to_label", "duration_seconds", "path")
	writer.writerow(columns)
	for row in exact_json(rows):
		writer.writerow([_csv_cell(row[column]) for column in columns])
	return {"filename": f"crm-analytics-movement-{revision[:12]}.csv", "csv": output.getvalue(), "total": len(rows)}
