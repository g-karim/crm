"""Targets and actuals for authorized employee, team and site-wide CRM scopes."""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _

from crm.analytics.call_reporting import _summary as summarize_calls, call_facts
from crm.analytics.engine import amount, closing, number, timestamp
from crm.analytics.manager_work import CLOSED_TASKS, _has_scope, _incomplete_outcomes
from crm.analytics.sales_plans import (
	_assignees, can_manage_team, company_plan_editor, currency_and_precision, monthly_plans, plan_scope,
	save_plan, team_members,
)
from crm.analytics.service import (
	TASK_FIELDS, coherent_read, exact_json, normalize_filters, readable_rows, related_scope, snapshot_hash, source_snapshot,
)
from crm.permissions.org_hierarchy import hierarchy_enabled
from crm.utils import sales_user_only

GOAL = "CRM Analytics Goal"
METRICS = {
	"won_value": ("sales", "currency", "min", "Сумма побед", "По дате победы и текущему ответственному"),
	"won_count": ("sales", "count", "min", "Выигранные сделки", "По дате победы и текущему ответственному"),
	"calls_connected": ("calls", "count", "min", "Состоявшиеся соединения", "По дате начала звонка"),
	"calls_answer_incoming": ("calls", "percent", "min", "Дозвон входящих", "По дате начала. Учитываются звонки с известным исходом"),
	"calls_answer_outgoing": ("calls", "percent", "min", "Дозвон исходящих", "По дате начала. Учитываются звонки с известным исходом"),
	"calls_sla": ("calls", "percent", "min", "Перезвоны в срок", "По дате пропущенного звонка и действующим правилам SLA"),
	"calls_overdue": ("calls", "count", "max", "Просроченные перезвоны", "По дате пропущенного звонка, с учётом перезвонов на текущий момент"),
	"tasks_overdue": ("tasks", "count", "max", "Просроченные задачи", "Открытые сейчас задачи со сроком в выбранном периоде"),
}
FIELDS = ["name", "period", "period_start", "scope", "subject", "metric", "target", "goal_currency", "modified"]
OUTSIDE_SCOPE = object()
MONTHLY_METRICS = {"won_value": "target_amount", "won_count": "target_wins"}
CALL_METRIC_KEYS = {
	"calls_connected": "connected",
	"calls_answer_incoming": "answer_rate_incoming",
	"calls_answer_outgoing": "answer_rate_outgoing",
	"calls_sla": "sla_percent",
	"calls_overdue": "overdue",
}


def bounds(period, value):
	try:
		day = date.fromisoformat(str(value))
	except ValueError:
		day = None
	if not day or not 1901 <= day.year <= 2198 or len(str(value)) != 10 or period not in ("Week", "Month", "Quarter"):
		frappe.throw(_("Choose a valid goal period."), frappe.ValidationError)
	if period == "Week":
		start = day - timedelta(days=day.weekday())
		return start, start + timedelta(days=6)
	start_month = day.month if period == "Month" else ((day.month - 1) // 3) * 3 + 1
	end_month = start_month if period == "Month" else start_month + 2
	return date(day.year, start_month, 1), date(day.year, end_month, monthrange(day.year, end_month)[1])


def _target(metric, value, precision):
	_kind, unit, direction, _label, _basis = METRICS[metric]
	target = number(value)
	places = precision if unit == "currency" else (2 if unit == "percent" else 0)
	maximum = {"currency": 999_999_999, "count": 1_000_000, "percent": 100}[unit]
	try:
		if target is not None and 0 <= target <= maximum and (target > 0 or direction == "max"):
			if target == target.quantize(Decimal(1).scaleb(-places)):
				return format(target.normalize(), "f")
	except InvalidOperation:
		pass
	frappe.throw(_("Choose a goal value within the metric's unit and precision."), frappe.ValidationError)


def _identity(period, start, scope, subject, metric):
	return "goal-" + snapshot_hash(period, start, scope, subject or "", metric)[:40]


def validate_document(doc):
	start, _end = bounds(doc.period, str(doc.period_start))
	if (str(start) != str(doc.period_start) or doc.scope not in ("Employee", "Team", "Company")
		or (doc.scope == "Company") == bool(doc.subject) or doc.metric not in METRICS
		or doc.name != _identity(doc.period, start, doc.scope, doc.subject, doc.metric)):
		frappe.throw(_("Invalid analytics goal."), frappe.ValidationError)
	if bool(doc.goal_currency) != (METRICS[doc.metric][1] == "currency"):
		frappe.throw(_("Choose a valid currency for the goal."), frappe.ValidationError)
	doc.target = _target(doc.metric, doc.target, currency_and_precision()[1])


def _selection(scope, subject):
	can_edit, owners = plan_scope()
	if scope == "Company" and not subject and company_plan_editor():
		return None
	if scope == "Team" and can_manage_team(subject):
		return team_members(subject)
	if scope == "Employee" and subject and (owners is None or subject in owners):
		return {subject}
	return OUTSIDE_SCOPE


def _version(row):
	return row.get("version") or str(row.modified)


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_goal(period: str, day: str, scope: str, metric: str, target: str, expected_viewer: str,
		subject: str | None = None, currency: str | None = None, version: str | None = None):
	if expected_viewer != frappe.session.user:
		frappe.throw(_("Reload analytics after switching users."), frappe.PermissionError)
	can_edit, owners = plan_scope()
	if not can_edit or _selection(scope, subject) is OUTSIDE_SCOPE or (
		scope == "Employee" and not _assignees(owners, subject)
	):
		frappe.throw(_("This analytics goal is outside your scope."), frappe.PermissionError)
	start, _end = bounds(period, day)
	current_currency, precision = currency_and_precision()
	if metric not in METRICS:
		frappe.throw(_("Choose a goal metric."), frappe.ValidationError)
	if (current_currency if METRICS[metric][1] == "currency" else None) != (currency or None):
		frappe.throw(_("Goal currency changed. Reload its settings."), frappe.TimestampMismatchError)
	value = _target(metric, target, precision)
	name = _identity(period, start, scope, subject, metric)
	if period == "Month" and scope == "Employee" and metric in MONTHLY_METRICS:
		current = monthly_plans(start, {subject}).get(subject, {})
		if metric == "won_count" and current.get("target_amount") and current["currency"] != current_currency:
			frappe.throw(_("Update the sales amount in the current currency first."), frappe.TimestampMismatchError)
		plan = save_plan(subject, start.isoformat()[:7],
			value if metric == "won_value" else current.get("target_amount"),
			value if metric == "won_count" else current.get("target_wins"),
			version, current_currency)
		return {"name": name, "version": plan["version"]}
	try:
		current = frappe.db.get_value(GOAL, name, ["target", "goal_currency", "modified"], as_dict=True, for_update=True)
		if current and (current.target, current.goal_currency or "") == (value, currency or ""):
			return exact_json({"name": name, "version": _version(current)})
		if (version or "") != (_version(current) if current else ""):
			frappe.throw(_("This goal changed. Reload the current version."), frappe.TimestampMismatchError)
		if current:
			doc = frappe.get_doc(GOAL, name, for_update=True)
			doc.update({"target": value, "goal_currency": currency})
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": GOAL, "period": period, "period_start": start,
				"scope": scope, "subject": subject, "metric": metric, "target": value, "goal_currency": currency})
			doc.insert(set_name=name, ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.QueryDeadlockError):
		frappe.throw(_("This goal changed. Reload the current version."), frappe.TimestampMismatchError)
	return exact_json({"name": name, "version": _version(doc)})


def _calculations(ctx, rows):
	kinds = {METRICS[row.metric][0] for row, _members in rows}
	sales = source_snapshot(ctx) if kinds & {"sales", "tasks"} else None
	calls, call_caps = None, None
	if "calls" in kinds:
		try:
			calls, _links, call_caps = call_facts(ctx)
		except frappe.PermissionError:
			pass
	if "tasks" in kinds:
		tasks, fields = readable_rows("CRM Task", TASK_FIELDS)
		if not {"assigned_to", "reference_doctype", "reference_docname", "status", "due_date"} <= fields:
			tasks = None
		else:
			allowed = related_scope(sales[0], sales[1], ctx)
			tasks = [row for row in tasks if _has_scope(row, allowed, restrict=False)
				and row.get("status") not in CLOSED_TASKS
				and (due := timestamp(row.get("due_date"), ctx.zone)) and due < ctx.as_of
				and ctx.period.contains(due, ctx.zone)]
	else:
		tasks = None

	facts = defaultdict(dict)
	call_scopes = {}
	for row, members in rows:
		key = row.scope, row.subject
		if row.metric in facts[key]:
			continue
		kind = METRICS[row.metric][0]
		actual, complete = None, False
		if kind == "calls" and calls is not None:
			if key not in call_scopes:
				call_scopes[key] = summarize_calls([call for call in calls if members is None or call["employee"] in members], call_caps)
			actual = call_scopes[key][CALL_METRIC_KEYS[row.metric]]
			complete = actual is not None
		elif kind == "sales":
			deals, _leads, _tasks, _events, caps, _statuses = sales
			if caps["status"] and (members is None or caps["owner"]):
				scoped = [deal for deal in deals if members is None or deal["owner"] in members]
				won = closing(scoped, "Won", ctx.period, ctx)
				gap, missing_won = _incomplete_outcomes(scoped, ctx)
				if row.metric == "won_count":
					actual, complete = len(won), not gap
				elif caps["money"]:
					result = amount(won, ctx, extra_missing=missing_won)
					actual, complete = result["value"], result["complete"] and row.goal_currency == ctx.currency
		elif kind == "tasks" and tasks is not None:
			actual = sum(members is None or task["assigned_to"] in members for task in tasks)
			complete = True
		facts[key][row.metric] = actual, complete
	return facts


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_goals(period: str, day: str):
	return exact_json(goal_report(period, day))


def goal_key(row):
	return row["scope"], row.get("subject") or "", row["metric"]


def _goal_entries(period, start, owners, selection=None):
	rows = []
	for row in frappe.get_all(GOAL, filters={"period": period, "period_start": start}, fields=FIELDS, order_by="scope, subject, metric"):
		if selection is not None and goal_key(row) not in selection:
			continue
		members = _selection(row.scope, row.subject)
		if members is not OUTSIDE_SCOPE:
			rows.append((row, members))
	if period == "Month":
		for employee, plan in monthly_plans(start, owners).items():
			for metric, field in MONTHLY_METRICS.items():
				if plan[field] is not None and (selection is None or ("Employee", employee, metric) in selection):
					rows.append((frappe._dict(
						name=_identity(period, start, "Employee", employee, metric), scope="Employee",
						subject=employee, metric=metric, target=plan[field], version=plan["version"],
						goal_currency=plan["currency"] if metric == "won_value" else None,
					), {employee}))
	return rows


def goal_choices(period, day):
	start, _end = bounds(period, day)
	_, owners = plan_scope()
	return [{"scope": row.scope, "subject": row.subject or "", "metric": row.metric,
		"label": METRICS[row.metric][3], "subject_label": _subject_label(row.subject)}
		for row, _members in _goal_entries(period, start, owners)]


def _subject_label(subject):
	return (frappe.get_cached_value("User", subject, "full_name") or subject) if subject else ""


def goal_report(period, day, *, observed_at=None, selection=None):
	start, end = bounds(period, day)
	ctx = normalize_filters({"from_date": str(start), "to_date": str(end)}, observed_at=observed_at)
	can_edit, owners = plan_scope()
	rows = _goal_entries(period, start, owners, selection)
	future = start > ctx.as_of.date()
	values = _calculations(ctx, rows) if rows and not future else {}
	results = []
	for row, _members in rows:
		_, unit, direction, label, basis = METRICS[row.metric]
		target = number(row.target)
		actual, complete = values.get((row.scope, row.subject), {}).get(row.metric, (None, False))
		mismatch = unit == "currency" and row.goal_currency != ctx.currency
		if mismatch:
			actual, complete = None, False
		known = number(actual) if complete else None
		status = None if known is None else (known >= target if direction == "min" else known <= target)
		results.append({"name": row.name, "scope": row.scope, "subject": row.subject, "metric": row.metric,
			"label": label, "basis": basis, "unit": unit, "direction": direction, "currency": row.goal_currency,
			"subject_label": _subject_label(row.subject),
			"target": row.target, "version": _version(row), "can_edit": can_edit, "actual": actual,
			"currency_mismatch": mismatch, "complete": complete, "met": status,
			"progress": ctx.round(100 * known / target) if direction == "min" and known is not None else None})
	if selection is not None:
		return {"start": start, "end": end, "rows": results}
	teams = frappe.get_all("CRM Sales Hierarchy", filters={"is_group": 1}, pluck="user") if can_edit and hierarchy_enabled() else []
	teams = [lead for lead in teams if can_manage_team(lead)]
	return {"viewer": frappe.session.user, "period": period, "start": start, "end": end,
		"future": future, "currency": ctx.currency, "rows": results, "can_edit": can_edit,
		"company": company_plan_editor(), "employees": _assignees(owners) if can_edit else [],
		"teams": [{"key": lead, "label": frappe.get_cached_value("User", lead, "full_name") or lead} for lead in teams],
		"metrics": {key: {"unit": entry[1], "direction": entry[2], "label": entry[3], "basis": entry[4]} for key, entry in METRICS.items()}}
