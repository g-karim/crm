"""Native source permissions, normalized facts, and signed read-only drill-downs."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import time
from collections import Counter, defaultdict
from functools import wraps
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import now_datetime

from crm.analytics.engine import AnalyticsInputError, Context, Period, amount, build_report, calendar_date, closing, forecast_value, money, timestamp
from crm.analytics.history import _same_value, deal_history, load_deal_facts_for_report
from crm.analytics.metric_catalog import FORECAST_CATEGORIES, sales_catalog
from crm.utils import sales_user_only

FILTERS = {"from_date", "to_date", "forecast_from", "forecast_to", "owner", "pipeline", "source"}
DEAL_FIELDS = ["name", "deal_name", "creation", "status", "pipeline", "deal_owner", "source", "territory", "lead", "deal_value",
	"currency", "exchange_rate", "expected_deal_value", "probability", "expected_closure_date", "closed_date", "lost_reason", "analytics_value_presence"]
LEAD_FIELDS = ["name", "lead_name", "creation", "status", "lead_owner", "source", "planned_deal_pipeline", "converted"]
TASK_FIELDS = ["name", "title", "status", "due_date", "assigned_to", "reference_doctype", "reference_docname"]
MAX_ROWS = 100000


def coherent_read(fn):
	"""HTTP GETs use a separate native, read-only repeatable-read transaction.

	The request's transaction is never committed or replaced permanently. Internal
	callers (including native save/rollback tests) retain their existing transaction.
	"""
	@wraps(fn)
	def wrapped(*args, **kwargs):
		request = getattr(frappe.local, "request", None)
		if not request:
			return fn(*args, **kwargs)
		from frappe.database import get_db
		conf = frappe.local.conf
		old = frappe.local.db
		old_consistent_read = getattr(frappe.local, "analytics_consistent_read", False)
		db = get_db(socket=conf.db_socket, host=conf.db_host, port=conf.db_port,
			user=conf.db_user or conf.db_name, password=conf.db_password, cur_db_name=conf.db_name)
		try:
			db.connect()
			db.sql("ROLLBACK")
			db.sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
			db.sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
			frappe.local.db = db
			frappe.local.analytics_consistent_read = True
			return fn(*args, **kwargs)
		finally:
			frappe.local.analytics_consistent_read = old_consistent_read
			db.rollback()
			db.close()
			frappe.local.db = old
	return wrapped


def exact_json(value):
	if isinstance(value, Decimal):
		return format(value, "f")
	if isinstance(value, (date, datetime)):
		return value.isoformat()
	if isinstance(value, dict):
		return {key: exact_json(item) for key, item in value.items()}
	if isinstance(value, (list, tuple)):
		return [exact_json(item) for item in value]
	return value


def snapshot_hash(*parts):
	"""Hash canonical facts without copying the entire nested report first."""
	def atom(value):
		if isinstance(value, Decimal):
			return format(value, "f")
		if isinstance(value, (date, datetime)):
			return value.isoformat()
		return str(value)
	return hashlib.sha256(json.dumps(parts, sort_keys=True, default=atom).encode()).hexdigest()


def normalize_filters(filters=None, *, observed_at=None, default_days=30):
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters or {}
	if isinstance(parsed, dict) and "as_of" in parsed:
		frappe.throw(_("Historical as-of reports are unavailable because the source has no complete history. Open a saved snapshot for a recorded past result."), frappe.ValidationError)
	if not isinstance(parsed, dict) or set(parsed) - FILTERS:
		frappe.throw(_("Unsupported analytics filter."), frappe.ValidationError)
	for field, value in parsed.items():
		if value is not None and (not isinstance(value, str) or len(value) > 180):
			frappe.throw(_("Invalid analytics filter."), frappe.ValidationError)
	zone = frappe.db.get_single_value("System Settings", "time_zone") or "UTC"
	now = timestamp(observed_at or now_datetime(), zone)
	today = now.date()
	def day(key, fallback):
		value = parsed.get(key)
		if value and (len(value) != 10 or calendar_date(value, zone) is None):
			frappe.throw(_("Select valid calendar dates."), frappe.ValidationError)
		return calendar_date(value, zone) if value else fallback
	start, end = day("from_date", today - timedelta(days=default_days - 1)), day("to_date", today)
	# A current unfinished month compares equal observed calendar spans.
	if start <= today < end:
		end = today
	forecast_start = day("forecast_from", today)
	forecast_end = day("forecast_to", today + timedelta(days=30))
	try:
		ctx = Context(Period(start, end), Period(forecast_start, forecast_end), now, zone=zone,
			currency=frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
			precision=int(frappe.db.get_single_value("System Settings", "currency_precision") or 2),
			owner=parsed.get("owner") or None, pipeline=parsed.get("pipeline") or None, source=parsed.get("source") or None)
	except (AnalyticsInputError, ValueError, TypeError) as exc:
		frappe.throw(_("Invalid analytics period or settings: {0}").format(str(exc)), frappe.ValidationError)
	return ctx


def readable_rows(doctype: str, fields: list[str], filters=None):
	"""Native query ACL, document ACL, then native field-level read/masking.

	Full rows are loaded only for already permitted identities to evaluate native
	controller permissions without an N+1 get_doc query. They never leave this scope.
	"""
	if not frappe.has_permission(doctype, "read"):
		return [], set()
	rows, cursor = [], ""
	available = set(get_permitted_fields(doctype, permission_type="read"))
	meta = frappe.get_meta(doctype)
	levels = meta.get_permlevel_access("read")
	available.update(field.fieldname for field in meta.get_table_fields() if field.permlevel in levels)
	available -= {field.fieldname for field in meta.get_masked_fields()}
	if frappe.session.user == "Administrator":
		# Frappe grants Administrator every document and skips field masking.
		# Fetch only the requested columns without hydrating each document.
		selected = [field for field in fields if field in available]
		raw_rows = frappe.get_all(doctype, filters=filters or {}, fields=selected,
			order_by="name asc", limit_page_length=MAX_ROWS + 1)
		if len(raw_rows) > MAX_ROWS:
			frappe.throw(_("This analytics selection is too large. Apply a narrower filter."), frappe.ValidationError)
		rows = [{**row, "_available": sorted(row)} for row in raw_rows]
		if rows:
			available &= set(selected) | {field.fieldname for field in meta.get_table_fields() if field.fieldname in available}
		return rows, available
	while True:
		query_filters = {**(filters or {})}
		if cursor:
			query_filters["name"] = [">", cursor]
		names = frappe.get_list(doctype, filters=query_filters, fields=["name"], order_by="name asc", limit_page_length=500)
		if not names:
			break
		raw_rows = frappe.get_all(doctype, filters={"name": ["in", [row.name for row in names]]}, fields=["*"], order_by="name asc", limit_page_length=0)
		for raw in raw_rows:
			doc = frappe.get_doc({"doctype": doctype, **raw})
			if not frappe.has_permission(doctype, "read", doc=doc):
				continue
			doc.apply_fieldlevel_read_permissions()
			masked = set(doc.flags.get("masked_fieldnames") or [])
			row = {field: doc.get(field) for field in fields if field in available and field not in masked and field in doc.__dict__}
			row["_available"] = sorted(set(row))
			rows.append(row)
		if len(rows) > MAX_ROWS:
			frappe.throw(_("This analytics selection is too large. Apply a narrower filter."), frappe.ValidationError)
		cursor = names[-1].name
		if len(names) < 500:
			break
	if rows:
		available &= set.intersection(*(set(row["_available"]) for row in rows)) | {f.fieldname for f in meta.get_table_fields() if f.fieldname in available}
	return rows, available


def _validate_dimension_filters(ctx):
	meta = frappe.get_meta("CRM Deal")
	allowed = set(get_permitted_fields("CRM Deal", permission_type="read"))
	allowed -= {field.fieldname for field in meta.get_masked_fields()}
	for field, value in [("deal_owner", ctx.owner), ("pipeline", ctx.pipeline), ("source", ctx.source)]:
		if value and field not in allowed:
			frappe.throw(_("This analytics filter is not available to your account."), frappe.PermissionError)


def related_scope(deals, leads, ctx):
	return {
		"CRM Deal": {row["name"] for row in deals if ctx.includes(row)},
		"CRM Lead": {row["name"] for row in leads if ctx.includes(row)},
	}


def source_snapshot(ctx):
	_validate_dimension_filters(ctx)
	# Keep source permissions authoritative. A requested owner narrows visible rows;
	# it cannot expand the native assignment/share/hierarchy boundary.
	deals, deal_fields = readable_rows("CRM Deal", DEAL_FIELDS)
	leads, lead_fields = readable_rows("CRM Lead", LEAD_FIELDS)
	tasks, task_fields = readable_rows("CRM Task", TASK_FIELDS)
	for chosen, fields in ((ctx.owner, ("deal_owner", "lead_owner")),
		(ctx.source, ("source", "source")), (ctx.pipeline, ("pipeline", "planned_deal_pipeline"))):
		if chosen and (fields[0] not in deal_fields or fields[1] not in lead_fields):
			frappe.throw(_("This analytics filter is not available to your account."), frappe.PermissionError)
	category_field = "analytics_forecast_category"
	disabled_risks_field = "analytics_disabled_risks"
	stage_fields = ["name", "deal_status", "type", "pipeline", "position", "analytics_stale_days"]
	if frappe.db.has_column("CRM Deal Status", disabled_risks_field):
		stage_fields.append(disabled_risks_field)
	can_read_category = (category_field in get_permitted_fields("CRM Deal Status", permission_type="read")
		and category_field not in {field.fieldname for field in frappe.get_meta("CRM Deal Status").get_masked_fields()})
	if can_read_category:
		stage_fields.append(category_field)
	statuses = {row.name: row for row in frappe.get_all("CRM Deal Status", fields=stage_fields, limit_page_length=0)}
	valid_currencies = set(frappe.get_all("Currency", pluck="name", limit_page_length=0))
	permitted_names = [row["name"] for row in deals]
	permitted_set = set(permitted_names)
	child_fields = set(get_permitted_fields("CRM Status Change Log", parenttype="CRM Deal", permission_type="read"))
	child_fields -= {field.fieldname for field in frappe.get_meta("CRM Status Change Log").get_masked_fields(parenttype="CRM Deal")}
	can_history = {"status", "status_change_log"} <= deal_fields and {"from", "to", "from_date", "to_date", "from_type", "to_type"} <= child_fields
	history = load_deal_facts_for_report(permitted_names,
		administrator_scan=frappe.session.user == "Administrator") if can_history else {}
	legacy = {}
	if permitted_names and can_history:
		fields = ["name", "parent", "from", "to", "from_date", "to_date", "from_type", "to_type"]
		if frappe.session.user == "Administrator":
			# Administrator's source query already includes every current deal. Read
			# the small legacy log table once instead of one query per 500 deals.
			legacy_events = frappe.get_all("CRM Status Change Log", filters={"parenttype": "CRM Deal"},
				fields=fields, order_by="from_date asc, name asc", limit_page_length=0)
			for event in legacy_events:
				if event.parent in permitted_set:
					legacy.setdefault(event.parent, []).append(event)
		else:
			for offset in range(0, len(permitted_names), 500):
				for event in frappe.get_all("CRM Status Change Log", filters={"parenttype": "CRM Deal", "parent": ["in", permitted_names[offset:offset + 500]]},
					fields=fields, order_by="from_date asc, name asc", limit_page_length=0):
					legacy.setdefault(event.parent, []).append(event)
	normalized, transitions = [], []
	for row in deals:
		available = set(row.pop("_available"))
		presence = frappe.parse_json(row.pop("analytics_value_presence", None) or "{}")
		# A direct db_set/import can bypass hooks while leaving a previous
		# "known" marker behind. Until a native save records the new fact,
		# these numeric values are unknown rather than confirmed zero or money.
		last_after = (history.get(row["name"]) or {}).get("latest_after")
		if last_after:
			for field in ("deal_value", "expected_deal_value", "probability", "exchange_rate"):
				if not _same_value(field, last_after.get(field), row.get(field)):
					presence[field] = False
		for field in ("deal_value", "expected_deal_value", "probability", "exchange_rate"):
			if presence.get(field, bool(row.get(field))) is not True:
				row[field] = None
		status = statuses.get(row.get("status"))
		fact = dict((history.get(row["name"]) or {}).get("fact") or deal_history([]))
		if "expected_closure_date" not in available:
			fact["close_date_pushed"] = False
			fact.pop("close_date_push", None)
		first_event = (history.get(row["name"]) or {}).get("first")
		created_at = timestamp(row.get("creation"), ctx.zone)
		first_recorded_at = timestamp(first_event["occurred_at"], ctx.zone) if first_event else None
		fact["path_history_complete"] = bool(first_event and first_event["event_kind"] == "Created"
			and first_event["history_complete"] and created_at and first_recorded_at
			and abs((created_at - first_recorded_at).total_seconds()) < 1)
		if not fact["stage_entered_at"]:
			entries = legacy.get(row["name"], [])
			for event in entries:
				if event.to == row.get("status") and event.to_type == "Lost" and event.to_date:
					fact["lost_date"] = event.to_date
				if event.get("from") == row.get("status") and not event.to and event.from_date:
					fact["stage_entered_at"] = event.from_date
					# A legacy interval is usable only when supported by a recorded transition.
					fact["stage_history_complete"] = any(e.to == row.get("status") and e.to_date == event.from_date for e in entries)
				if event.to and event.to_date:
					fact["transitions"].append({"name": "legacy:" + event.name, "deal": row["name"],
						"from_stage": event.get("from"), "to_stage": event.to, "occurred_at": event.to_date})
		transitions.extend(fact.pop("transitions"))
		attribution = fact.pop("outcome_attribution")
		status_type = status.type if status else None
		captured_owner = None
		if "deal_owner" in available and attribution and attribution["kind"] == status_type:
			closed = calendar_date(row.get("closed_date"), ctx.zone)
			recorded_at = calendar_date(attribution["at"], ctx.zone)
			recorded_close = calendar_date(attribution["closed_date"], ctx.zone)
			# Evidence must describe this exact outcome, including its effective date.
			# A later correction or backdated value has no proven owner at that date.
			if status_type == "Lost" or (closed and closed == recorded_at == recorded_close):
				captured_owner = attribution["owner"]
		normalized.append({"name": row["name"], "title": row.get("deal_name") or row["name"],
			"creation": row.get("creation"), "status": row.get("status"), "status_label": status.deal_status if status else None,
			"status_type": status_type, "pipeline": row.get("pipeline"), "owner": row.get("deal_owner"),
			"outcome_owner": captured_owner,
			"source": row.get("source"), "territory": row.get("territory"), "lead": row.get("lead"), "value": row.get("deal_value"),
			"currency": row.get("currency"),
			"currency_valid": row.get("currency") in valid_currencies if row.get("currency") else None,
			"exchange_rate": row.get("exchange_rate"),
			"expected_value": row.get("expected_deal_value"), "probability": row.get("probability"),
			"expected_date": row.get("expected_closure_date"), "closed_date": row.get("closed_date"),
			"lost_reason": row.get("lost_reason"), **fact})
		if can_read_category:
			normalized[-1]["forecast_category"] = status.get(category_field) if status else None
		if status:
			normalized[-1]["stale_days"] = status.analytics_stale_days
			if disabled_risks := status.get(disabled_risks_field):
				normalized[-1]["disabled_risk_rules"] = tuple(disabled_risks.split(","))
	normalized_leads = [{"name": row["name"], "title": row.get("lead_name") or row["name"], "creation": row.get("creation"),
		"owner": row.get("lead_owner"), "source": row.get("source"), "pipeline": row.get("planned_deal_pipeline"),
		"converted": row.get("converted")} for row in leads]
	normalized_tasks = [{"name": str(row["name"]), "status": row.get("status"), "due_date": row.get("due_date"),
		"reference_name": row.get("reference_docname"), "assigned_to": row.get("assigned_to")}
		for row in tasks if row.get("reference_doctype") == "CRM Deal" and row.get("reference_docname") in permitted_set]
	capabilities = {"money": {"deal_value", "currency", "exchange_rate"} <= deal_fields,
		"forecast": {"expected_deal_value", "probability", "expected_closure_date", "currency", "exchange_rate"} <= deal_fields,
		"status": "status" in deal_fields, "source": "source" in deal_fields, "owner": "deal_owner" in deal_fields,
		"lead_status": "converted" in lead_fields, "territory": "territory" in deal_fields,
		"history": can_history, "tasks": {"reference_docname", "reference_doctype", "status", "due_date"} <= task_fields,
		"lead_source": "source" in lead_fields, "forecast_category": can_read_category}
	return normalized, normalized_leads, normalized_tasks, transitions, capabilities, statuses


def calculate(ctx, *, include_source_revision=True):
	deals, leads, tasks, events, capabilities, statuses = source_snapshot(ctx)
	# The service issues a revision covering native permissions and source facts.
	report = build_report(deals, leads, tasks, ctx, events=events,
		tasks_available=capabilities["tasks"], include_snapshot=False)
	report["permissions"] = capabilities
	report["context"]["access_basis"] = "native_visible_records"
	report["context"]["viewer"] = frappe.session.user
	report["options"] = {key: sorted({row.get(key) for row in deals if row.get(key)}) for key in ["owner", "source", "pipeline"]}
	visible_stage_ids = {row["status"] for row in deals if row.get("status")}
	visible_stage_ids.update(row["stage"] for row in report["funnel"]["visited"] if row.get("stage"))
	stage_identity = {key: ((statuses[key].deal_status or key), statuses[key].pipeline)
		for key in visible_stage_ids if key in statuses}
	label_counts = Counter(label for label, _pipeline in stage_identity.values())
	stage_labels = {key: f"{label} · {pipeline}" if label_counts[label] > 1 and pipeline else label
		for key, (label, pipeline) in stage_identity.items()}
	report["labels"] = {"stages": stage_labels,
		"owners": {name: name for name in report["options"]["owner"]}, "pipelines": {name: name for name in report["options"]["pipeline"]}}
	# Tasks are actual readable CRM records. Unverified provider channels never
	# become invented zero calls/messages or made-up sales targets.
	visible_deals = {deal["name"] for deal in deals if ctx.includes(deal)}
	visible_tasks = [row for row in tasks if row.get("reference_name") in visible_deals]
	report["activity"] = {"tasks": {"available": capabilities["tasks"], "open": sum(row.get("status") not in {"Done", "Completed", "Canceled", "Cancelled"} for row in visible_tasks) if capabilities["tasks"] else None,
		"overdue": sum(row.get("status") not in {"Done", "Completed", "Canceled", "Cancelled"} and bool((due := timestamp(row.get("due_date"), ctx.zone)) and due < ctx.as_of) for row in visible_tasks) if capabilities["tasks"] else None},
		"calls": {"available": False, "reason": "provider_contract_not_verified"},
		"messages": {"available": False, "reason": "provider_contract_not_verified"}, "goals": {"available": False, "reason": "no_verified_plan"}}
	report["history_coverage"] = {"available": capabilities["history"], "open": report["metrics"]["open_count"]["value"],
		"confirmed_current_stage": sum(row.get("stage_history_complete", False) for row in deals if ctx.includes(row) and row.get("status_type") not in {"Won", "Lost"}),
		"basis": "recorded_events", "historical_dimensions": False}
	if not capabilities["money"]:
		for key in ["won_value", "open_value", "forecast", "risk_value", "stalled_value", "average_won_value", "median_won_value"]:
			report["metrics"][key] = {"value": None, "complete": False, "redacted": True, "basis": report["metrics"][key]["basis"]}
		for group in ["sources", "owners", "closing_owners", "open_owners", "open_pipelines", "stages"]:
			for row in report[group]:
				row.update(value=None, complete=False, redacted=True)
		for row in report["trend"]:
			row["won_value"] = None
		for row in report["attention"]:
			for key in ["value", "expected_value", "probability", "exchange_rate", "currency", "currency_valid"]:
				row.pop(key, None)
		report["quality"] = [row for row in report["quality"] if row["code"] not in {"unknown_or_invalid_amount", "unknown_currency", "incomplete_forecast"}]
	if not capabilities["status"]:
		for key in set(report["metrics"]) - {"new_leads", "new_deals"}:
			report["metrics"][key] = {"value": None, "complete": False, "redacted": True, "basis": report["metrics"][key]["basis"]}
		report.update(attention=[], sources=[], owners=[], closing_owners=[], open_owners=[], open_pipelines=[], stages=[], funnel=None)
	if not capabilities["forecast"]:
		report["metrics"]["forecast"] = {"value": None, "complete": False, "redacted": True, "basis": "horizon"}
	report["forecast_categories"] = []
	settings_role = frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()
	report["can_manage_forecast_categories"] = capabilities["forecast_category"] and settings_role
	report["can_manage_attention_rules"] = bool(settings_role and frappe.has_permission("CRM Deal Status", "write")
		and frappe.db.has_column("CRM Deal Status", "analytics_disabled_risks"))
	if all(capabilities[key] for key in ("forecast_category", "forecast", "status")):
		forecast_ids = set(report["selections"]["forecast"])
		buckets = defaultdict(list)
		for row in deals:
			if row["name"] in forecast_ids:
				category = row.get("forecast_category")
				buckets[category if category in FORECAST_CATEGORIES else "Uncategorized"].append(row)
		report["forecast_categories"] = [{
			"key": key, "count": len(items), "record_ids": [row["name"] for row in items],
			**amount(items, ctx, forecast=True),
		} for key in (*FORECAST_CATEGORIES, "Uncategorized") if (items := buckets.get(key))]
	if not (capabilities["owner"] and capabilities["history"]):
		report["closing_owners"] = []
	if not capabilities["source"]:
		report["sources"] = []
		report["quality"] = [row for row in report["quality"] if row["code"] != "missing_source"]
	if not capabilities["lead_source"]:
		report["source_cohorts"] = []
	if not capabilities["lead_status"]:
		if report["funnel"]:
			report["funnel"].update(converted_leads=None, won_leads=None, outcome_complete=False)
		report["source_cohorts"] = []
	# The observation clock labels the read but does not by itself change its
	# facts. Keep the revision stable across focus refreshes with identical
	# permitted sources and derived values. Time-driven changes to overdue work,
	# stages, or periods remain in the report and still change the revision.
	revision_report = {key: value for key, value in report.items() if key not in {"snapshot", "context"}}
	revision_report["context"] = {key: value for key, value in report["context"].items() if key != "as_of"}
	# Include every permitted analytical source value, not only visible totals.
	report["snapshot"] = snapshot_hash(revision_report, deals, leads, tasks, events)
	# Keep source comparison independent of the observation clock. This internal
	# revision is stored with new forecast snapshots, avoiding another full read.
	if include_source_revision:
		report["_source_revision"] = snapshot_hash(deals, leads, tasks, events, capabilities)
	return report, {"CRM Deal": deals, "CRM Lead": leads}


def _public(value):
	if isinstance(value, dict):
		return {key: _public(item) for key, item in value.items()
			if key not in {"selections", "record_ids", "_source_revision", "disabled_risk_rules", "close_date_push"}}
	if isinstance(value, list):
		return [_public(item) for item in value]
	return value


def _sign(payload):
	encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode().rstrip("=")
	key = frappe.local.conf.get("encryption_key")
	if not key:
		frappe.throw(_("Analytics signing is not configured."))
	signature = hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
	return encoded + "." + signature


def _verify(token):
	try:
		if not isinstance(token, str) or len(token) > 4000:
			raise ValueError
		encoded, signature = token.split(".")
		payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
		if len(token) > 4000 or not hmac.compare_digest(_sign(payload).split(".")[1], signature):
			raise ValueError
		if payload["user"] != frappe.session.user or payload["site"] != frappe.local.site or payload["expires"] < time.time():
			raise ValueError
		return payload
	except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
		frappe.throw(_("This analytics snapshot expired. Refresh the report."), frappe.TimestampMismatchError)


def import_coverage():
	"""Describe recent failed native imports without treating them as source rows.

	Only readable Data Import jobs are considered. The result is operational
	context, not an assertion that every external channel was imported.
	"""
	if not frappe.has_permission("Data Import", "read"):
		return {"available": False, "basis": "native_data_import", "window_days": 30}
	since = now_datetime() - timedelta(days=30)
	issues = frappe.get_list("Data Import", filters={
		"reference_doctype": ["in", ["CRM Lead", "CRM Deal"]],
		"status": ["in", ["Partial Success", "Error", "Timed Out"]],
		"modified": [">=", since],
	}, fields=["name"], limit_page_length=1)
	return {"available": True, "recent_issue": bool(issues), "basis": "native_data_import",
		"window_days": 30, "scope": "readable_jobs"}


def _loss_reasons(deals, ctx, permissions):
	if not permissions["status"] or "lost_reason" not in get_permitted_fields("CRM Deal", permission_type="read"):
		return []
	categories = {}
	for row in closing([deal for deal in deals if ctx.includes(deal)], "Lost", ctx.period, ctx):
		categories.setdefault(row.get("lost_reason") or "", []).append(row["name"])
	return [{"key": key, "count": len(ids), "record_ids": ids} for key, ids in
		sorted(categories.items(), key=lambda item: (-len(item[1]), item[0]))]


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_report(filters: dict | str | None = None, check_summary_calls: bool = False) -> dict:
	ctx = normalize_filters(filters)
	if ctx.period.start > ctx.as_of.date():
		frappe.throw(_("The results period has not begun. Select an observed date or use the forecast horizon."), frappe.ValidationError)
	report, sources = calculate(ctx, include_source_revision=False)
	public = _public({**report, "attention": report["attention"][:50],
		"loss_reasons": _loss_reasons(sources["CRM Deal"], ctx, report["permissions"])})
	public["import_coverage"] = import_coverage()
	public["metric_catalog"] = sales_catalog(report["metrics"])
	public["attention"] = public["attention"][:50]
	if check_summary_calls:
		from crm.analytics.summary import call_summary

		calls = call_summary(ctx)
		public["summary_calls"] = {"revision": calls["revision"], "status": calls["status"]}
	public["snapshot_token"] = _sign({"user": frappe.session.user, "site": frappe.local.site,
		"filters": {key: value for key, value in (frappe.parse_json(filters) if isinstance(filters, str) else filters or {}).items()},
		"observed_at": ctx.as_of.isoformat(), "snapshot": report["snapshot"], "expires": time.time() + 120})
	return exact_json(public)


def _detail_selection(snapshot_token: str, metric: str, group_key: str | None = None):
	"""Recheck the signed report and current permissions for every detail consumer."""
	payload = _verify(snapshot_token)
	ctx = normalize_filters(payload["filters"])
	report, sources = calculate(ctx, include_source_revision=False)  # Current permissions are always checked again.
	if report["snapshot"] != payload["snapshot"]:
		frappe.throw(_("The source data or access changed. Refresh analytics before opening details."), frappe.TimestampMismatchError)
	if metric in report["selections"]:
		if report["metrics"][metric].get("redacted"):
			frappe.throw(_("This analytics detail is unavailable."), frappe.PermissionError)
		ids, descriptor = report["selections"][metric], report["metrics"][metric]
	elif metric == "loss_reasons":
		group = next((row for row in _loss_reasons(sources["CRM Deal"], ctx, report["permissions"])
			if row["key"] == group_key), None)
		if not group:
			frappe.throw(_("This analytics detail is unavailable."), frappe.PermissionError)
		ids, descriptor = group["record_ids"], {"count": group["count"]}
	elif metric in {"sources", "owners", "closing_owners", "open_owners", "open_pipelines", "stages", "quality", "forecast_categories"}:
		group = next((row for row in report[metric] if str(row.get("key", row.get("code"))) == group_key), None)
		if not group or group.get("redacted"):
			frappe.throw(_("This analytics detail is unavailable."), frappe.PermissionError)
		ids, descriptor = group["record_ids"], {key: value for key, value in group.items() if key != "record_ids"}
	else:
		frappe.throw(_("This analytics detail is unavailable."), frappe.PermissionError)
	doctype = "CRM Lead" if metric == "new_leads" else "CRM Deal"
	rows = {row["name"]: row for row in sources[doctype]}
	return report, ids, descriptor, doctype, rows, ctx


def _detail_row(row, doctype, permissions, ctx):
	row = dict(row)
	row.pop("disabled_risk_rules", None)
	row.pop("close_date_push", None)
	if not permissions["money"]:
		for key in ["value", "expected_value", "probability", "exchange_rate", "currency", "currency_valid"]:
			row.pop(key, None)
	elif doctype == "CRM Deal":
		row["base_value"] = money(row, ctx)
	row["path"] = "/crm/" + ("leads/" if doctype == "CRM Lead" else "deals/") + row["name"]
	return row


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(snapshot_token: str, metric: str, start: int = 0, limit: int = 50, group_key: str | None = None) -> dict:
	report, ids, descriptor, doctype, rows, ctx = _detail_selection(snapshot_token, metric, group_key)
	try:
		start, limit = max(0, int(start)), min(200, max(1, int(limit)))
	except (ValueError, TypeError):
		frappe.throw(_("Invalid analytics page."), frappe.ValidationError)
	page = [_detail_row(rows[name], doctype, report["permissions"], ctx) for name in ids[start:start + limit]]
	if metric in ("risk_count", "risk_value"):
		facts = {row["name"]: row["reason_facts"] for row in report["attention"]}
		for row in page:
			row["reason_facts"] = facts[row["name"]]
	if metric in ("forecast", "forecast_categories") and report["permissions"]["forecast"]:
		for row in page:
			row["forecast_contribution"] = forecast_value(rows[row["name"]], ctx)
	return exact_json({"rows": page, "total": len(ids), "start": start, "limit": limit,
		"has_more": start + len(page) < len(ids), "snapshot": report["snapshot"], "metric": descriptor})


def _csv_cell(value):
	"""Prevent imported spreadsheet formulas without changing numeric cells."""
	if value is None:
		return ""
	if isinstance(value, str):
		return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
	return str(value)


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export_details(snapshot_token: str, metric: str, group_key: str | None = None) -> dict:
	"""Export the full current, permission-filtered detail selection as CSV text."""
	report, ids, _descriptor, doctype, rows, ctx = _detail_selection(snapshot_token, metric, group_key)
	if doctype == "CRM Lead":
		columns = [("name", "ID"), ("title", "Lead"), ("creation", "Created at"),
			("owner", "Owner"), ("pipeline", "Pipeline"), ("converted", "Converted")]
		if report["permissions"]["lead_source"]:
			columns.insert(4, ("source", "Source"))
	else:
		columns = [("name", "ID"), ("title", "Deal"), ("status_label", "Stage"),
			("pipeline", "Pipeline"), ("creation", "Created at"), ("closed_date", "Closed at"),
			("expected_date", "Expected close")]
		if report["permissions"]["owner"]:
			columns.insert(4, ("owner", "Owner"))
			if metric == "closing_owners":
				columns.insert(5, ("outcome_owner", "Owner at close"))
		if report["permissions"]["source"]:
			columns.insert(5 if report["permissions"]["owner"] else 4, ("source", "Source"))
		if report["permissions"]["money"]:
			columns.extend([("value", "Deal value"), ("currency", "Currency"),
				("exchange_rate", "Exchange rate"), ("base_value", f"Deal value ({ctx.currency})"),
				("expected_value", "Expected value"), ("probability", "Probability")])
			if metric in ("forecast", "forecast_categories"):
				columns.append(("forecast_category", "Forecast category"))
				columns.append(("forecast_contribution", f"Forecast contribution ({ctx.currency})"))
	facts = None
	if metric in ("risk_count", "risk_value"):
		facts = {row["name"]: row["reason_facts"] for row in report["attention"]}
		columns.extend([("reason_codes", "Attention reasons"), ("reason_evidence", "Attention evidence")])
	columns.append(("path", "CRM link"))
	output = io.StringIO(newline="")
	writer = csv.writer(output, lineterminator="\r\n")
	writer.writerow([label for _field, label in columns])
	for name in ids:
		row = _detail_row(rows[name], doctype, report["permissions"], ctx)
		if doctype == "CRM Deal" and report["permissions"]["money"] and metric in ("forecast", "forecast_categories"):
			row["forecast_contribution"] = forecast_value(row, ctx)
		if facts is not None:
			row["reason_codes"] = ", ".join(facts[name])
			row["reason_evidence"] = frappe.as_json(exact_json(facts[name]), indent=None)
		writer.writerow([_csv_cell(row.get(field)) for field, _label in columns])
	return {"filename": f"crm-analytics-{metric}-{report['snapshot'][:12]}.csv",
		"csv": output.getvalue(), "total": len(ids), "snapshot": report["snapshot"]}
