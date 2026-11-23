"""Manager analytics over authorized CRM documents and the selected period."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
import re

import frappe

from crm.analytics.call_reporting import TERMINAL as CALL_TERMINAL, answer_outcome, call_facts
from crm.analytics.engine import CLOSED, OPEN, amount, calendar_date, closing, number, outcome_date, timestamp
from crm.analytics.service import (
	TASK_FIELDS,
	coherent_read,
	exact_json,
	normalize_filters,
	readable_rows,
	related_scope,
	source_snapshot,
)
from crm.analytics.sales_plans import month_bounds, monthly_plans, plan_scope
from crm.utils import sales_user_only

CLOSED_TASKS = {"Done", "Completed", "Canceled", "Cancelled"}
PAGE_SIZE = 25


def summarize_calls(rows, ctx, *, can_match):
	"""Match a later connected outgoing call to the same number and manager.

	Only records inside the selected period are used. Unmatchable identities
	remain unknown, and phone numbers are never returned by the report.
	"""
	records = []
	for row in rows:
		observed = timestamp(row.get("start_time"), ctx.zone)
		direction = row.get("type")
		manager = row.get({"Incoming": "receiver", "Outgoing": "caller"}.get(direction, ""))
		if not observed or observed > ctx.as_of or not ctx.period.contains(observed, ctx.zone) or not manager:
			continue
		peer = row.get("from" if direction == "Incoming" else "to")
		raw = re.sub(r"[^\d+]", "", str(peer or ""))
		peer = raw if can_match and re.fullmatch(r"\+?\d{7,15}", raw) else None
		records.append((observed, row, manager, peer, direction))

	outbound_by_peer = defaultdict(list)
	logs = defaultdict(list)
	for observed, row, manager, peer, direction in sorted(records, key=lambda item: item[0]):
		duration = number(row.get("duration"))
		if direction == "Outgoing" and row.get("status") == "Completed" and duration is not None and duration > 0 and peer:
			outbound_by_peer[(manager, peer)].append(observed)

	for observed, row, manager, peer, direction in sorted(records, key=lambda item: item[0], reverse=True):
		state = row.get("status")
		duration = number(row.get("duration"))
		connected = state == "Completed" and duration is not None and duration > 0
		callback = None
		if direction == "Incoming" and state == "No Answer" and peer:
			followups = outbound_by_peer[(manager, peer)]
			index = bisect_right(followups, observed)
			if index < len(followups):
				callback = int((followups[index] - observed).total_seconds())
		logs[manager].append({
			"name": row["name"], "at": observed, "direction": direction, "status": state,
			"duration": duration, "medium": row.get("telephony_medium"),
			"callback_seconds": callback,
			"callback_unconfirmed": direction == "Incoming" and state == "No Answer" and bool(peer) and callback is None,
			"callback_unknown": direction == "Incoming" and state == "No Answer" and not peer,
			"outbound_connected": direction == "Outgoing" and connected,
		})
	return logs


def _has_scope(row, allowed, *, restrict):
	doctype, name = row.get("reference_doctype"), row.get("reference_docname")
	if doctype in allowed and name:
		return name in allowed[doctype]
	# Calls may have no CRM reference, or be associated only with a contact.
	# They belong to their explicit agent but cannot inherit a deal dimension.
	return not restrict


def _task_logs(ctx, allowed, team, viewer):
	rows, fields = readable_rows("CRM Task", TASK_FIELDS)
	required = {"assigned_to", "reference_doctype", "reference_docname", "status", "due_date"}
	if not required <= fields:
		return None
	logs = defaultdict(list)
	for row in rows:
		manager = row.get("assigned_to")
		if not manager or (not team and manager != viewer) or (ctx.owner and manager != ctx.owner):
			continue
		if not _has_scope(row, allowed, restrict=bool(ctx.pipeline or ctx.source)):
			continue
		if row.get("status") in CLOSED_TASKS:
			continue
		due = timestamp(row.get("due_date"), ctx.zone)
		logs[manager].append({
			"name": str(row["name"]), "title": row.get("title"), "status": row.get("status"),
			"due": due, "overdue": bool(due and due < ctx.as_of),
		})
	for items in logs.values():
		items.sort(key=lambda row: (row["due"] is None, row["due"] or ctx.as_of, row["name"]))
	return logs


def _call_logs(ctx, allowed):
	try:
		facts, _tasks, caps = call_facts(ctx, related=allowed if ctx.pipeline or ctx.source else None)
	except frappe.PermissionError:
		return None
	logs = defaultdict(list)
	for fact in facts:
		if not fact["employee"]:
			continue
		logs[fact["employee"]].append({
			"name": fact["name"], "at": fact["at"], "direction": fact["direction"],
			"status": fact["status"], "duration": fact["duration"], "missed": fact["missed"],
			"callback_seconds": fact["conversation_seconds"],
			"callback_unconfirmed": bool(fact["missed"] and not fact["callback_connected"] and caps["outcomes"] and caps["duration"]),
			"callback_unknown": bool(fact["missed"] and not (caps["outcomes"] and caps["duration"])),
			"outbound_connected": bool(fact["direction"] == "Outgoing" and fact["connected"]),
			"answer_outcome": answer_outcome(fact) if caps["duration"] else None,
			"can_check_calls": caps["outcomes"] and caps["duration"],
		})
	return logs


def _plans(ctx, full_access):
	"""Explicit period totals in the reporting currency, configured by the site."""
	if not full_access or ctx.pipeline or ctx.source:
		return {}
	plans = frappe.conf.get("crm_analytics_sales_plans") or []
	if not isinstance(plans, list):
		return {}
	key = (str(ctx.period.start), str(ctx.period.end), ctx.currency)
	grouped = defaultdict(list)
	for entry in plans:
		if not isinstance(entry, dict) or (entry.get("from_date"), entry.get("to_date"), entry.get("currency")) != key:
			continue
		if isinstance(entry.get("manager"), str):
			grouped[entry["manager"]].append(number(entry.get("amount")))
	return {owner: values[0] for owner, values in grouped.items()
		if len(values) == 1 and values[0] is not None and values[0] > 0}


def _call_metrics(rows):
	if not rows:
		return None
	outgoing = [row for row in rows if row["direction"] == "Outgoing"]
	callbacks = [row["callback_seconds"] for row in rows if row["callback_seconds"] is not None]
	return {
		"incoming": sum(row["direction"] == "Incoming" for row in rows),
		"outgoing": len(outgoing),
		"outgoing_connected": sum(row["outbound_connected"] for row in outgoing),
		"outgoing_attempts": sum(row["status"] in CALL_TERMINAL for row in outgoing),
		"outgoing_known_outcomes": sum(row["answer_outcome"] is not None for row in outgoing),
		"missed": sum(row["missed"] for row in rows),
		"callback_unconfirmed": sum(row["callback_unconfirmed"] for row in rows) if rows[0]["can_check_calls"] else None,
		"callback_unknown": sum(row["callback_unknown"] for row in rows),
		"average_callback_seconds": round(sum(callbacks) / len(callbacks)) if callbacks else None,
	}


def _incomplete_outcomes(deals, ctx):
	won_missing = 0
	has_gap = False
	for row in deals:
		status = row.get("status_type")
		if status in OPEN:
			continue
		if status not in CLOSED:
			has_gap = True
			won_missing += 1
			continue
		closed = calendar_date(outcome_date(row), ctx.zone)
		created = calendar_date(row.get("creation"), ctx.zone)
		if not closed or not created or not created <= closed <= ctx.as_of.date():
			has_gap = True
			won_missing += status == "Won"
	return has_gap, won_missing


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_manager_work(filters: dict | str | None = None, manager: str | None = None,
		view: str = "tasks", start: int = 0, month: str | None = None) -> dict:
	month_start = None
	if month:
		month_start, month_end = month_bounds(month)
		params = frappe.parse_json(filters) if isinstance(filters, str) else filters or {}
		if not isinstance(params, dict):
			frappe.throw(frappe._("Invalid manager report filters."), frappe.ValidationError)
		filters = {**params, "from_date": str(month_start), "to_date": str(month_end)}
	ctx = normalize_filters(filters)
	future = ctx.period.start > ctx.as_of.date()
	if (future and not month) or view not in {"tasks", "calls"} or start < 0:
		frappe.throw(frappe._("Invalid manager report filters."), frappe.ValidationError)

	viewer = frappe.session.user
	can_edit, plan_owners = plan_scope()
	team = can_edit
	deals, leads, _tasks, _events, caps, _statuses = source_snapshot(ctx)
	allowed = related_scope(deals, leads, replace(ctx, owner=None))
	task_logs = _task_logs(ctx, allowed, team, viewer)
	call_logs = None if future else _call_logs(ctx, allowed)
	legacy_plans = _plans(ctx, viewer == "Administrator")
	if not month_start and ctx.period.start.day == 1:
		first, last = month_bounds(ctx.period.start.isoformat()[:7])
		if ctx.period.end == min(last, ctx.as_of.date()):
			month_start = first
	plans = {}
	if month_start and not (ctx.pipeline or ctx.source):
		plan_filter = {ctx.owner} if ctx.owner else None
		if plan_filter is not None and plan_owners is not None:
			plan_filter &= plan_owners
		plans = monthly_plans(month_start, plan_filter if ctx.owner else plan_owners)

	by_manager = defaultdict(list)
	if caps["owner"]:
		for row in deals:
			owner = row.get("owner")
			if owner and (team or owner == viewer) and ctx.includes(row):
				by_manager[owner].append(row)

	owners = sorted(set(by_manager) | set(task_logs or {}) | set(call_logs or {}) | set(plans))
	result = []
	for owner in owners:
		deals_for_owner = by_manager[owner]
		sales_visible = not future and caps["status"] and caps["owner"]
		won = closing(deals_for_owner, "Won", ctx.period, ctx) if sales_visible else None
		lost = closing(deals_for_owner, "Lost", ctx.period, ctx) if sales_visible else None
		outcome_gap, missing_won = _incomplete_outcomes(deals_for_owner, ctx)
		outcomes_complete = won is not None and not outcome_gap
		measured = amount(won, ctx, extra_missing=missing_won) if won is not None and caps["money"] else None
		plan_record = plans.get(owner)
		plan_currency_ok = not plan_record or plan_record["currency"] == ctx.currency
		sale_plan = number(plan_record["target_amount"]) if plan_record else legacy_plans.get(owner)
		wins_plan = plan_record["target_wins"] if plan_record else None
		tasks = task_logs.get(owner, []) if task_logs is not None else None
		result.append({
			"key": owner, "label": frappe.get_cached_value("User", owner, "full_name") or owner,
			"won": len(won) if won is not None else None,
			"lost": len(lost) if lost is not None else None,
			"won_value": measured["value"] if measured else None,
			"won_value_complete": measured["complete"] if measured else False,
			"outcomes_complete": outcomes_complete,
			"win_rate": ctx.round(Decimal(len(won) * 100) / (len(won) + len(lost)))
				if outcomes_complete and (won or lost) else None,
			"plan": sale_plan if plan_currency_ok else None,
			"plan_currency_mismatch": not plan_currency_ok,
			"plan_percent": ctx.round(100 * measured["value"] / sale_plan)
				if sale_plan and plan_currency_ok and measured and measured["complete"] else None,
			"wins_plan": wins_plan,
			"wins_plan_percent": ctx.round(Decimal(100 * len(won)) / wins_plan)
				if wins_plan and outcomes_complete else None,
			"open_tasks": len(tasks) if tasks is not None else None,
			"overdue_tasks": sum(row["overdue"] for row in tasks) if tasks is not None else None,
			"calls": _call_metrics(call_logs.get(owner, [])) if call_logs is not None else None,
		})

	response = {
		"rows": result, "period": ctx.metadata(), "team": team, "can_edit_plans": can_edit,
		"future": future, "plans_filtered": bool(ctx.pipeline or ctx.source),
	}
	if manager:
		if manager not in owners:
			frappe.throw(frappe._("This manager report is unavailable."), frappe.PermissionError)
		logs = call_logs if view == "calls" else task_logs
		items = logs.get(manager, []) if logs is not None else []
		response["detail"] = {
			"manager": manager, "view": view, "available": logs is not None,
			"rows": items[start:start + PAGE_SIZE], "start": start,
			"total": len(items), "has_more": start + PAGE_SIZE < len(items),
		}
	return exact_json(response)
