"""Saved CRM analyses using the sources and permissions of the current viewer."""

from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
import io
import re
from time import time

import frappe
from frappe import _
from frappe.model import get_permitted_fields

from crm.analytics.call_reporting import _make_report as call_report, read_named
from crm.analytics.engine import Period, money, number
from crm.analytics.goals import METRICS as GOAL_METRICS, bounds, goal_choices, goal_key, goal_report
from crm.analytics.metric_catalog import SALES_METRICS
from crm.analytics.sales_plans import can_manage_team, plan_scope, team_members
from crm.analytics.service import (
	_csv_cell, _sign, _verify, calculate, coherent_read, exact_json, normalize_filters, snapshot_hash,
)
from crm.permissions import org_hierarchy
from crm.utils import sales_user_only

BOARD = "CRM Analytics Board"
SCHEMA = 1
CALENDAR_PERIODS = {"week": "Week", "month": "Month", "quarter": "Quarter"}
GOAL_SCOPES = {"Company", "Team", "Employee"}
FIELDS = ["name", "title", "audience", "team_lead", "owner", "modified", "definition", "creation_hash"]
GROUPS = {
	"won_count": {"source": ("sources", "count"), "employee": ("owners", "count"), "closing_owner": ("closing_owners", "count")},
	"won_value": {"source": ("sources", "value"), "employee": ("owners", "value"), "closing_owner": ("closing_owners", "value")},
	"open_count": {"pipeline": ("open_pipelines", "count"), "stage": ("stages", "count"), "employee": ("open_owners", "count")},
	"open_value": {"pipeline": ("open_pipelines", "value"), "stage": ("stages", "value"), "employee": ("open_owners", "value")},
	"forecast": {"forecast_category": ("forecast_categories", "value")},
}
CALL_GROUPS = {"team": "teams", "employee": "employees", "line": "lines", "day": "days", "week": "weeks",
	"outcome": "outcomes", "sla": "sla"}
CORE_FILTERS = {"owner", "pipeline", "source"}
CALL_FILTERS = {"line", "direction", "outcome"}
CUSTOM_METRICS = {"new_leads", "new_deals", "won_count", "won_value", "lost_count"}
CALLS = {
	"calls_total": ("total", "count", "Все звонки"),
	"calls_missed": ("missed", "count", "Пропущенные звонки"),
	"calls_connected": ("connected", "count", "Состоявшиеся соединения"),
	"calls_answer_incoming": ("answer_rate_incoming", "percent", "Доля дозвона по входящим"),
	"calls_answer_outgoing": ("answer_rate_outgoing", "percent", "Доля дозвона по исходящим"),
	"calls_late_callback": ("overdue", "count", "Просроченные перезвоны"),
	"calls_sla": ("sla_percent", "percent", "Перезвоны в срок"),
}
TASKS = {"tasks_open": ("open", "Открытые задачи"), "tasks_overdue": ("overdue", "Просроченные задачи")}
DATE_BASES = {
	"created_on": "Дата создания", "won_on": "Дата победы", "lost_on": "Дата потери", "closed_on": "Дата закрытия",
	"now": "Текущее состояние", "expected_close_on": "Ожидаемая дата закрытия", "started_on": "Дата начала звонка",
}
LABELS = {
	"new_leads": "Новые лиды", "new_deals": "Новые сделки", "won_count": "Победы", "won_value": "Сумма побед",
	"lost_count": "Потери", "win_rate": "Доля побед", "median_cycle": "Медианный цикл", "open_count": "Открытые сделки",
	"open_value": "Сумма открытых сделок", "forecast": "Взвешенный прогноз", "risk_count": "Сделки с риском",
	"risk_value": "Сумма риска", "stalled_value": "Сумма зависших сделок", "average_won_value": "Средняя сумма победы",
	"median_won_value": "Медианная сумма победы", "average_cycle": "Средний цикл", "lead_cycle": "Цикл от лида до победы",
}


def _bad(message=None):
	frappe.throw(message or _("Invalid report settings."), frappe.ValidationError)


def _denied():
	frappe.throw(_("This saved report is not available."), frappe.PermissionError)


def _json(value):
	try:
		return frappe.parse_json(value) if isinstance(value, str) else value
	except (TypeError, ValueError):
		_bad()


def _custom_fields(entity):
	doctype = {"lead": "CRM Lead", "deal": "CRM Deal"}.get(entity)
	if not doctype or not frappe.has_permission(doctype, "read"):
		return {}
	meta = frappe.get_meta(doctype)
	allowed = set(get_permitted_fields(doctype, permission_type="read"))
	allowed -= {field.fieldname for field in meta.get_masked_fields()}
	return {
		field.fieldname: {
			"label": field.label,
			"values": ["0", "1"] if field.fieldtype == "Check" else [value for value in (field.options or "").splitlines() if value],
		}
		for field in meta.fields
		if field.get("is_custom_field") and field.fieldtype in {"Select", "Check"} and field.fieldname in allowed
	}


def _catalog():
	catalog = {
		key: {"object": entity, "date": basis, "unit": unit, "label": LABELS[key],
			"formula": ru, "groups": list(GROUPS.get(key, {})), "custom": key in CUSTOM_METRICS}
		for key, (entity, basis, unit, _en, ru) in SALES_METRICS.items()
	}
	catalog.update({key: {"object": "call", "date": "started_on", "unit": unit, "label": label,
		"groups": list(CALL_GROUPS), "custom": False} for key, (_metric, unit, label) in CALLS.items()})
	catalog.update({key: {"object": "task", "date": "now", "unit": "count", "label": label,
		"groups": [], "custom": False} for key, (_metric, label) in TASKS.items()})
	catalog["goal_progress"] = {"object": "goal", "date": "goal_period", "unit": "", "label": "План и факт",
		"groups": [], "custom": False}
	return catalog


def _templates():
	return [
		{"title": "План и качество работы отдела", "period": {"mode": "month"}, "cards": [
			{"metric": "goal_progress"}, {"metric": "won_count"}, {"metric": "calls_sla"}, {"metric": "tasks_overdue"}]},
		{"title": "План отдела", "cards": [{"metric": "won_value"}, {"metric": "won_count"}, {"metric": "tasks_open"}]},
		{"title": "Пропущенные и SLA", "cards": [{"metric": "calls_missed", "group": "employee"}, {"metric": "calls_sla"}, {"metric": "calls_late_callback"}]},
		{"title": "Продажи по источникам", "cards": [{"metric": "won_value", "group": "source"}, {"metric": "won_count", "group": "source"}]},
		{"title": "Воронка по этапам", "cards": [{"metric": "open_count", "group": "stage"}, {"metric": "open_value", "group": "pipeline"}, {"metric": "forecast"}]},
	]


def _visible(row):
	viewer = frappe.session.user
	return row.owner == viewer or (row.audience == "Team" and viewer in team_members(row.team_lead))


def _period_definition(data):
	if "period" not in data:
		days = data.get("days", 30)
		if days not in (7, 30, 90):
			_bad()
		return {"days": days}
	period = data["period"]
	if "days" in data or not isinstance(period, dict) or not isinstance(period.get("mode"), str):
		_bad()
	mode = period["mode"]
	if mode in CALENDAR_PERIODS and set(period) == {"mode"}:
		return {"period": {"mode": mode}}
	if mode != "fixed" or set(period) != {"mode", "from_date", "to_date"}:
		_bad()
	try:
		start, end = (date.fromisoformat(period[key]) for key in ("from_date", "to_date"))
		if not (1901 <= start.year and end.year <= 2198
			and start.isoformat() == period["from_date"] and end.isoformat() == period["to_date"]):
			raise ValueError
		Period(start, end)
	except (TypeError, ValueError):
		_bad(_("Choose valid report dates in chronological order."))
	return {"period": {"mode": mode, "from_date": start.isoformat(), "to_date": end.isoformat()}}


def _period_context(config):
	filters = config["filters"]
	selection = config.get("period")
	if not selection:
		return normalize_filters(filters, default_days=config["days"]), None
	mode = selection["mode"]
	base = normalize_filters(filters)
	if mode == "fixed":
		start, end = selection["from_date"], selection["to_date"]
		if start > base.as_of.date().isoformat():
			_bad(_("The report start date must be today or earlier."))
	else:
		start, end = (value.isoformat() for value in bounds(CALENDAR_PERIODS[mode], base.as_of.date()))
	ctx = normalize_filters({**filters, "from_date": start, "to_date": end}, observed_at=base.as_of)
	return ctx, {"mode": mode, "from_date": start, "to_date": end}


def _board_filters(data):
	filters = data.get("filters") or {}
	if (not isinstance(filters, dict) or set(filters) - CORE_FILTERS
		or any(not isinstance(value, str) or not value or len(value) > 140 for value in filters.values())):
		_bad()
	return filters


def _goal_definition(value):
	if not isinstance(value, dict) or set(value) != {"scope", "subject", "metric"} or not all(isinstance(item, str) for item in value.values()):
		_bad(_("Select a goal for the report."))
	scope, subject, metric = goal_key(value)
	if scope not in GOAL_SCOPES or (scope == "Company") == bool(subject) or len(subject) > 140 or metric not in GOAL_METRICS:
		_bad(_("Select a goal for the report."))
	return {"scope": scope, "subject": subject, "metric": metric}


def _goal_period(selected):
	if not selected:
		return None
	start = selected["from_date"]
	if selected["mode"] in CALENDAR_PERIODS:
		return CALENDAR_PERIODS[selected["mode"]], start
	for mode in CALENDAR_PERIODS.values():
		period_start, period_end = bounds(mode, start)
		if (period_start.isoformat(), period_end.isoformat()) == (start, selected["to_date"]):
			return mode, start
	return None


def _goal_filter_matches(ctx, goal):
	return not (ctx.pipeline or ctx.source) and (not ctx.owner or (goal["scope"] == "Employee" and goal["subject"] == ctx.owner))


def _definition(value, *, check_fields=False):
	data = _json(value)
	if not isinstance(data, dict) or set(data) - {"schema", "cards", "days", "filters", "period"} or data.get("schema", SCHEMA) != SCHEMA:
		_bad()
	cards = data.get("cards")
	period = _period_definition(data)
	filters = _board_filters(data)
	if not isinstance(cards, list) or not 1 <= len(cards) <= 8:
		_bad()
	catalog = _catalog()
	normalized = []
	for item in cards:
		if not isinstance(item, dict) or set(item) - {"metric", "group", "display", "custom_field", "custom_value", "calculation", "operand", "call_filters", "goal"}:
			_bad()
		metric = item.get("metric")
		if not isinstance(metric, str) or metric not in catalog:
			_bad()
		if metric == "goal_progress":
			if any(item.get(key) for key in ("group", "calculation", "operand", "custom_field", "custom_value", "call_filters")) or item.get("display", "number") != "number":
				_bad(_("Goal cards use the settings of the selected goal."))
			normalized.append({"metric": metric, "goal": _goal_definition(item.get("goal")), "display": "number"})
			continue
		if "goal" in item:
			_bad()
		info = catalog[metric]
		group = item.get("group") or ""
		display = item.get("display", "number" if not group else "table")
		custom = item.get("custom_field") or ""
		custom_value = item.get("custom_value") or ""
		op, operand = item.get("calculation") or "", item.get("operand") or ""
		call_filters = item.get("call_filters") or {}
		if not all(isinstance(value, str) for value in (group, display, custom, custom_value, op, operand)):
			_bad()
		if display not in {"number", "table", "bar"} or bool(group) != (display != "number"):
			_bad()
		if group and group not in info["groups"] and group != "custom":
			_bad()
		if custom or group == "custom":
			if not info["custom"] or not re.fullmatch(r"[a-zA-Z0-9_]{1,140}", custom) or len(custom_value) > 180:
				_bad()
			if check_fields:
				field = _custom_fields(info["object"]).get(custom)
				if field is None or (custom_value and custom_value not in field["values"]):
					_bad(_("Choose an accessible custom field and an allowed option."))
		elif custom_value:
			_bad()
		if op or operand:
			if (op not in {"ratio", "difference"} or operand not in catalog or group or custom
				or any(catalog[operand][key] != info[key] for key in ("object", "date", "unit"))):
				_bad(_("Choose compatible metrics for this calculation."))
		if call_filters and (info["object"] != "call" or not isinstance(call_filters, dict) or set(call_filters) - CALL_FILTERS
			or any(not isinstance(value, str) or len(value) > 180 for value in call_filters.values())):
			_bad()
		from crm.analytics.call_reporting import _filters as validate_calls
		validate_calls(call_filters)
		normalized.append({"metric": metric, "group": group, "display": display, "custom_field": custom,
			"custom_value": custom_value, "calculation": op, "operand": operand, "call_filters": call_filters})
	return {"schema": SCHEMA, **period, "filters": filters, "cards": normalized}


def validate_document(doc):
	if not isinstance(doc.title, str) or not 1 <= len(doc.title.strip()) <= 100:
		_bad(_("Enter a report title of up to 100 characters."))
	_definition(doc.definition)
	if doc.audience not in {"Private", "Team"} or (doc.audience == "Team") != bool(doc.team_lead):
		_bad(_("Choose a valid report audience."))


def _serialize(row):
	can_edit = row.owner == frappe.session.user
	return {"name": row.name, "title": row.title, "audience": row.audience, "team_lead": row.team_lead if can_edit else None,
		"modified": str(row.modified), "can_edit": can_edit,
		"definition": _definition(row.definition) if can_edit else None}


def _visible_board(name, *, lock=False):
	if not isinstance(name, str) or not re.fullmatch(r"board-[0-9a-f]{32}", name):
		return None
	row = frappe.db.get_value(BOARD, name, FIELDS, as_dict=True, for_update=lock)
	return row if row and _visible(row) else None


def _get(name, *, lock=False, write=False):
	row = _visible_board(name, lock=lock)
	if not row or (write and row.owner != frappe.session.user):
		_denied()
	return row


def _call_scope(ctx):
	return {"from_date": str(ctx.period.start), "to_date": str(ctx.period.end),
		"employee": ctx.owner, "pipeline": ctx.pipeline, "source": ctx.source}


def _call_filter_options(ctx):
	try:
		call_data = call_report(_call_scope(ctx))[0]
	except frappe.PermissionError:
		return {}
	filters = {}
	for field, group in (("line", "lines"), ("outcome", "outcomes")):
		filters[field] = [{"value": row["key"], "label": row["label"]} for row in call_data["groups"][group] if row["key"]]
	if call_data["coverage"]["outcomes"]:
		filters["outcome"].append({"value": "unprocessed", "label": "Без итогов"})
	filters["direction"] = [{"value": "Incoming", "label": "Входящие"},
		{"value": "Outgoing", "label": "Исходящие"}, {"value": "unknown", "label": "Направление не распознано"}]
	return filters


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def call_filter_options(selection: dict | str):
	ctx, _selected = _selection_context(selection)
	return _call_filter_options(ctx)


def _selection_context(selection):
	data = _json(selection)
	if not isinstance(data, dict) or set(data) - {"period", "days", "filters"}:
		_bad()
	return _period_context({**_period_definition(data), "filters": _board_filters(data)})


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def goal_options(selection: dict | str):
	ctx, selected = _selection_context(selection)
	period = _goal_period(selected)
	if not period:
		return {"choices": [], "reason": "goal_period"}
	if ctx.pipeline or ctx.source:
		return {"choices": [], "reason": "goal_filters"}
	return {"choices": [row for row in goal_choices(*period) if _goal_filter_matches(ctx, row)]}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def options():
	return _workspace_options()


def _workspace_options():
	teams = []
	if org_hierarchy.hierarchy_enabled() and plan_scope()[0]:
		leaders = frappe.get_all("CRM Sales Hierarchy", pluck="user")
		teams = [{"value": lead, "label": frappe.get_cached_value("User", lead, "full_name") or lead}
			for lead in leaders if can_manage_team(lead)]
	ctx = normalize_filters()
	report, _sources = calculate(ctx, include_source_revision=False)
	filters = {}
	for key, values in report["options"].items():
		filters[key] = [{
			"value": value,
			"label": (frappe.get_cached_value("User", value, "full_name") or value) if key == "owner" else value,
		} for value in values]
	return {"catalog": _catalog(), "templates": _templates(), "viewer": frappe.session.user, "filters": filters,
		"call_filters": _call_filter_options(ctx), "custom_fields": {entity: _custom_fields(entity) for entity in ("lead", "deal")}, "teams": teams,
		"default_period": {key: report["context"][key] for key in ("from_date", "to_date")}}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def list_boards():
	return [_serialize(row) for row in _board_rows()]


def _board_rows():
	if not frappe.db.table_exists(BOARD):
		return []
	actor = frappe.session.user
	owned = frappe.get_all(BOARD, filters={"owner": actor}, fields=FIELDS, limit_page_length=100, order_by="modified desc")
	team = frappe.get_all(BOARD, filters={"audience": "Team", "owner": ["!=", actor]}, fields=FIELDS, limit_page_length=0)
	return sorted((row for row in owned + team if _visible(row)), key=lambda row: row.modified, reverse=True)


def _history_board(name, modified):
	row = _get(name, write=True)
	if str(row.modified) != modified:
		frappe.throw(_("This board changed. Reload it before opening its history."), frappe.TimestampMismatchError)
	return row


def _previous_definition(value):
	def read_json(raw):
		try:
			return frappe.parse_json(raw) if isinstance(raw, str) else None
		except ValueError:
			return None

	data = read_json(value)
	if not isinstance(data, dict) or not isinstance(data.get("changed"), list):
		return None
	for change in data["changed"]:
		if not (isinstance(change, list) and len(change) == 3 and change[0] == "definition" and isinstance(change[1], str)):
			continue
		previous = read_json(change[1])
		if previous is None:
			# Frappe formats Long Text newlines as <br> in existing Version rows.
			previous = read_json(change[1].replace("<br>", "\n"))
		return previous if isinstance(previous, dict) and isinstance(previous.get("cards"), list) else None
	return None


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def list_revisions(name: str, modified: str, start: int = 0, limit: int = 20):
	row = _history_board(name, modified)
	start, limit = max(0, start), max(1, min(25, limit))
	versions = frappe.get_all("Version", filters={"ref_doctype": BOARD, "docname": row.name},
		fields=["name", "creation", "data"], order_by="creation desc, name desc", start=start, limit_page_length=limit + 1)
	catalog = _catalog()
	rows = []
	for version in versions[:limit]:
		previous = _previous_definition(version.data)
		if previous is None:
			continue
		formulas = []
		for card in previous["cards"]:
			if not isinstance(card, dict):
				continue
			metric, mode, operand = (card.get(key) for key in ("metric", "calculation", "operand"))
			if (all(isinstance(item, str) for item in (metric, mode, operand))
				and mode in {"ratio", "difference"} and metric in catalog and operand in catalog):
				formulas.append({"label": catalog[metric]["label"], "calculation": mode, "operand": catalog[operand]["label"]})
		rows.append({"name": version.name, "changed_at": str(version.creation)[:19], "formulas": formulas})
	return {"rows": rows, "next_start": start + limit if len(versions) > limit else None}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_revision(name: str, modified: str, revision: str):
	row = _history_board(name, modified)
	if not revision or len(revision) > 140:
		_denied()
	previous = _previous_definition(frappe.db.get_value(
		"Version", {"name": revision, "ref_doctype": BOARD, "docname": row.name}, "data"))
	if previous is None:
		_denied()
	return _definition(previous, check_fields=True)


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save(title: str, definition: dict | str, audience: str, expected_viewer: str, mutation: str,
	name: str | None = None, modified: str | None = None, team_lead: str | None = None):
	if expected_viewer != frappe.session.user:
		_denied()
	if not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", mutation or ""):
		_bad()
	if audience == "Team" and not can_manage_team(team_lead):
		_denied()
	if audience not in {"Private", "Team"} or (audience == "Private" and team_lead):
		_bad()
	config = _definition(definition, check_fields=True)
	has_goal = any(card["metric"] == "goal_progress" for card in config["cards"])
	if has_goal or config.get("period", {}).get("mode") == "fixed":
		_ctx, selected_period = _period_context(config)
		if has_goal and not _goal_period(selected_period):
			_bad(_("Goal cards require a full calendar week, month or quarter."))
	if not 1 <= len(title.strip()) <= 100:
		_bad(_("Enter a report title of up to 100 characters."))
	board_name = name or "board-" + sha256(f"{expected_viewer}\0{mutation}".encode()).hexdigest()[:32]
	frappe.db.get_value("User", expected_viewer, "name", for_update=True)
	fields = {"title": title.strip(), "definition": frappe.as_json(config), "audience": audience, "team_lead": team_lead}
	hash_value = snapshot_hash(fields)
	if name:
		current = _get(name, lock=True, write=True)
		if not modified or str(current.modified) != modified:
			frappe.throw(_("This board changed. Reload it before saving."), frappe.TimestampMismatchError)
		doc = frappe.get_doc(BOARD, name, for_update=True)
		doc.update(fields)
		doc.save(ignore_permissions=True)
	elif frappe.db.exists(BOARD, board_name):
		current = _get(board_name, lock=True, write=True)
		if current.creation_hash != hash_value:
			_bad(_("The request was already used for a different board."))
		return _serialize(current)
	else:
		doc = frappe.get_doc({"doctype": BOARD, **fields, "creation_hash": hash_value})
		doc.insert(set_name=board_name, ignore_permissions=True)
	return _serialize(doc)


def _sales(ctx, card, report, sources, metric):
	entry = report["metrics"][metric]
	group_key = card["group"]
	custom = card["custom_field"]
	if entry.get("redacted"):
		return None, False, [], "permission"
	if custom:
		return _custom_sales(ctx, card, report, sources, metric)
	rows = []
	if group_key:
		key, value_key = GROUPS[metric][group_key]
		group_permissions = {"source": "source", "employee": "owner", "closing_owner": "history", "stage": "status",
			"forecast_category": "forecast_category"}
		requires = group_permissions.get(group_key)
		if (requires and not report["permissions"][requires]) or (group_key == "closing_owner" and not report["permissions"]["owner"]):
			return entry.get("value"), bool(entry.get("complete", True)), [], "group_permission"
		label_maps = {"owners": "owners", "closing_owners": "owners", "open_owners": "owners",
			"open_pipelines": "pipelines", "stages": "stages"}
		labels = report["labels"].get(label_maps.get(key), {})
		rows = [{"key": row["key"], "label": labels.get(row["key"], row["key"]), "value": row.get(value_key)}
			for row in report[key]]
	return entry.get("value"), bool(entry.get("complete", True)), rows, None


def _custom_sales(ctx, card, report, sources, metric):
	entity = SALES_METRICS[metric][0]
	field = card["custom_field"]
	if field not in _custom_fields(entity):
		return None, False, [], "field_permission"
	doctype = "CRM Lead" if entity == "lead" else "CRM Deal"
	ids = report["selections"][metric]
	values = {row["name"]: str(row[field]) if row[field] is not None else ""
		for row in read_named(doctype, ["name", field], ids) if field in row}
	if set(ids) - values.keys():
		return None, False, [], "field_permission"
	source_rows = {row["name"]: row for row in sources[doctype]} if metric == "won_value" else {}
	buckets = defaultdict(list)
	for name in ids:
		key = values[name]
		if card["custom_value"] and key != card["custom_value"]:
			continue
		buckets[key].append(money(source_rows[name], ctx) if metric == "won_value" else 1)
	known = [value for values in buckets.values() for value in values if value is not None]
	partial = any(value is None for values in buckets.values() for value in values)
	value = sum(known) if known or not partial else None
	rows = []
	if card["group"] == "custom":
		for key, items in sorted(buckets.items()):
			amounts = [item for item in items if item is not None]
			rows.append({"key": key, "label": key, "value": sum(amounts) if amounts else None})
	return value, report["metrics"][metric].get("complete", True) and not partial, rows, None


def _board_goals(ctx, selected_period, cards):
	period = _goal_period(selected_period)
	keys = {goal_key(card["goal"]) for card in cards if card["metric"] == "goal_progress" and _goal_filter_matches(ctx, card["goal"])}
	if not period or not keys:
		return {}
	try:
		goals = goal_report(*period, observed_at=ctx.as_of, selection=keys)
	except frappe.PermissionError:
		return {}
	return {goal_key(row): row for row in goals["rows"]}


def _goal_result(info, item, ctx, selected_period, goals):
	result = {**info, "rows": [], "display": "number", "value": None, "complete": False}
	if not _goal_period(selected_period):
		return {**result, "reason": "goal_period"}
	if not _goal_filter_matches(ctx, item["goal"]):
		return {**result, "reason": "goal_filters"}
	row = goals.get(goal_key(item["goal"]))
	if not row:
		return {**result, "reason": "goal_unavailable"}
	goal = {key: row[key] for key in ("target", "progress", "met", "direction", "currency", "scope", "subject_label", "basis")}
	goal.update(from_date=selected_period["from_date"], to_date=selected_period["to_date"])
	return {**result, "label": row["label"], "value": row["actual"], "unit": row["unit"], "complete": row["complete"],
		"reason": "goal_currency" if row["currency_mismatch"] else None, "goal": goal}


def _render(config):
	ctx, selected_period = _period_context(config)
	catalog = _catalog()
	results, call_cache = [], {}
	sales = None
	goals = _board_goals(ctx, selected_period, config["cards"])
	for item in config["cards"]:
		metric = item["metric"]
		info = catalog[metric]
		rate_base = None
		if info["object"] == "goal":
			results.append(_goal_result(info, item, ctx, selected_period, goals))
			continue
		if info["object"] == "call":
			filters = {**_call_scope(ctx), **item["call_filters"]}
			cache_key = frappe.as_json(filters)
			try:
				if cache_key not in call_cache:
					call_cache[cache_key] = call_report(filters)[0]
				report = call_cache[cache_key]
			except frappe.PermissionError:
				results.append({"value": None, "complete": False, "rows": [], "reason": "permission", "display": item["display"], **info})
				continue
			metric_key = CALLS[metric][0]
			value = report["metrics"][metric_key]
			if not item["calculation"]:
				rate_base = report["metrics"]["rate_bases"].get(metric_key)
			rows = []
			for row in report["groups"].get(CALL_GROUPS.get(item["group"]), ()):
				entry = {"key": row["key"], "label": row["label"], "value": row.get(metric_key)}
				if rate_base is not None:
					entry["rate_base"] = row["rate_bases"][metric_key]
				rows.append(entry)
			other = report["metrics"][CALLS[item["operand"]][0]] if item["operand"] else None
			complete, reason = value is not None, None
		else:
			try:
				if sales is None:
					sales = calculate(ctx, include_source_revision=False)
			except frappe.PermissionError:
				results.append({"value": None, "complete": False, "rows": [], "reason": "permission", "display": item["display"], **info})
				continue
			sales_report, sources = sales
			if info["object"] == "task":
				tasks = sales_report["activity"]["tasks"]
				value = tasks[TASKS[metric][0]]
				other = tasks[TASKS[item["operand"]][0]] if item["operand"] else None
				complete, rows, reason = value is not None, [], None
			else:
				value, complete, rows, reason = _sales(ctx, item, sales_report, sources, metric)
				other = None
				if item["operand"]:
					other_entry = sales_report["metrics"][item["operand"]]
					other = other_entry.get("value") if not other_entry.get("redacted") else None
					complete = complete and bool(other_entry.get("complete", True))
		result = {**info, "value": value, "complete": complete, "rows": rows, "reason": reason,
			"display": item["display"], "group": item["group"]}
		if rate_base is not None:
			result["rate_base"] = rate_base
		if item["calculation"]:
			left, right = number(value), number(other)
			if not complete or left is None or right is None or (item["calculation"] == "ratio" and not right):
				result.update(value=None, complete=False, reason=reason or "operand_unavailable")
			elif item["calculation"] == "ratio":
				result.update(value=(100 * left / right).quantize(Decimal("0.01")), unit="percent")
			else:
				result["value"] = left - right
			result["calculation"] = item["calculation"]
			result["operand_label"] = catalog[item["operand"]]["label"]
		results.append(result)
	return {"context": ctx.metadata(), "selected_period": selected_period, "cards": results}


def _preview(config):
	result = _render(config)
	revision = snapshot_hash(result["cards"], {key: value for key, value in result["context"].items() if key != "as_of"})
	result["snapshot"] = revision
	return result


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_board(name: str):
	return exact_json(_board_result(_get(name)))


def _board_result(row, *, include_report=True):
	if not include_report:
		return {"board": _serialize(row), "preview": None}
	config = _definition(row.definition)
	result = _preview(config)
	result["token"] = _sign({"user": frappe.session.user, "site": frappe.local.site, "purpose": "board",
		"name": row.name, "modified": str(row.modified), "revision": result["snapshot"], "expires": time() + 120})
	return {"board": _serialize(row), "preview": result}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_workspace(name: str | None = None, include_options: bool = False, include_report: bool = True):
	"""Read the library and requested board under one current viewer and snapshot."""
	rows = _board_rows()
	selected = _visible_board(name) if name and frappe.db.table_exists(BOARD) else None
	result = {"viewer": frappe.session.user,
		"boards": [{"name": row.name, "title": row.title, "audience": row.audience} for row in rows],
		"selected": _board_result(selected, include_report=include_report) if selected else None}
	if include_options:
		result["options"] = _workspace_options()
	return exact_json(result)


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def preview(definition: dict | str):
	return exact_json(_preview(_definition(definition, check_fields=True)))


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export(token: str, index: int):
	payload = _verify(token)
	if payload.get("purpose") != "board":
		_denied()
	row = _get(payload["name"])
	result = _preview(_definition(row.definition))
	if payload["modified"] != str(row.modified) or payload["revision"] != result["snapshot"]:
		frappe.throw(_("This report changed. Refresh before exporting."), frappe.TimestampMismatchError)
	if not 0 <= index < len(result["cards"]):
		_bad()
	card = result["cards"][index]
	output = io.StringIO(newline="")
	writer = csv.writer(output, lineterminator="\r\n")
	writer.writerow(["Группа", "Значение", "Единица", "Начало", "Конец", "Основание расчёта"])
	context = result["context"]
	if card["object"] == "goal":
		goal = card.get("goal")
		if not goal:
			_denied()
		start, end = goal["from_date"], goal["to_date"]
		unit = goal["currency"] or card["unit"]
		items = [("План" if goal["direction"] == "min" else "Лимит", goal["target"], unit),
			("Факт", card["value"], unit)]
		if goal["progress"] is not None:
			items.append(("Выполнение", goal["progress"], "%"))
		for label, value, unit in items:
			writer.writerow([_csv_cell(item) for item in (label, value, unit, start, end, goal["basis"])])
		return {"filename": "crm-report.csv", "csv": output.getvalue(), "snapshot": result["snapshot"]}
	if card["date"] == "now":
		start = end = context["as_of"][:10]
	elif card["date"] == "expected_close_on":
		start, end = context["forecast_from"], context["forecast_to"]
	else:
		start, end = context["from_date"], context["to_date"]
	for item in [{"label": "Итого", "value": card["value"]}, *card["rows"]]:
		writer.writerow([_csv_cell(value) for value in (item["label"], item["value"], card["unit"], start, end, DATE_BASES[card["date"]])])
	return {"filename": "crm-report.csv", "csv": output.getvalue(), "snapshot": result["snapshot"]}
