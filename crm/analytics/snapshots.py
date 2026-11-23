"""Explicit immutable forecast snapshots with current source access checks."""

import hashlib
import json
import re
from datetime import date
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import now_datetime

from crm.analytics.history import CRMAnalyticsEvent, internal_write
from crm.analytics.engine import CLOSED, OPEN, Period, amount, calendar_date, closing, number, timestamp
from crm.analytics.service import _public, _verify, calculate, coherent_read, exact_json, normalize_filters
from crm.utils import sales_user_only

DOCTYPE = "CRM Analytics Snapshot"


class CRMAnalyticsSnapshot(CRMAnalyticsEvent):
	pass


def _checked(token):
	payload = _verify(token)
	ctx = normalize_filters(payload["filters"])
	report, sources = calculate(ctx)
	if report["snapshot"] != payload["snapshot"]:
		frappe.throw(frappe._("The report changed. Refresh before saving."), frappe.TimestampMismatchError)
	# Keep the saved report's original observation label after current-state validation.
	report["context"]["as_of"] = payload["observed_at"]
	return payload, report, sources


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_forecast_snapshot(snapshot_token: str, title: str, request_key: str):
	if not re.fullmatch(r"[0-9a-f]{32}", request_key or "") or not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
		frappe.throw(frappe._("Enter a title and a valid request key."), frappe.ValidationError)
	identity = hashlib.sha256(f"{frappe.local.site}:{frappe.session.user}:{request_key}".encode()).hexdigest()
	fingerprint = hashlib.sha256(json.dumps([snapshot_token, title.strip()], sort_keys=True).encode()).hexdigest()
	if frappe.db.exists(DOCTYPE, identity):
		doc = frappe.get_doc(DOCTYPE, identity)
		if doc.viewer != frappe.session.user or doc.fingerprint != fingerprint:
			frappe.throw(frappe._("This request key has already been used."), frappe.ValidationError)
		_check_access(doc)
		return {"name": doc.name, "replayed": True}
	payload, report, sources = _checked(snapshot_token)
	access = {"ids": {dt: sorted(row["name"] for row in rows) for dt, rows in sources.items()},
		"permissions": report["permissions"], "source_revision": report["_source_revision"],
		"forecast_ids": sorted(report["selections"]["forecast"]),
		"forecast_categories": {row["key"]: row["record_ids"] for row in report["forecast_categories"]}}
	with internal_write():
		doc = frappe.get_doc({"doctype": DOCTYPE, "name": identity, "viewer": frappe.session.user,
			"title": title.strip(), "observed_at": timestamp(report["context"]["as_of"], report["context"]["timezone"]).replace(tzinfo=None), "fingerprint": fingerprint,
			"filters": json.dumps(payload["filters"]), "source_access": json.dumps(access),
			"payload": json.dumps(exact_json(_public(report)), ensure_ascii=False),
		}).insert(ignore_permissions=True, set_name=identity)
	return {"name": doc.name, "replayed": False}


def _check_access(doc):
	if doc.viewer != frappe.session.user:
		frappe.throw(frappe._("This saved forecast is private."), frappe.PermissionError)
	# Never trust a saved authorization decision after a share/role/owner changes.
	ctx = normalize_filters(frappe.parse_json(doc.filters))
	report, sources = calculate(ctx)
	access = json.loads(doc.source_access)
	for dt, names in access["ids"].items():
		if not set(names) <= {row["name"] for row in sources[dt]}:
			frappe.throw(frappe._("Source access changed. This snapshot is no longer available."), frappe.PermissionError)
	if any(value and not report["permissions"].get(key) for key, value in access["permissions"].items()):
		frappe.throw(frappe._("Field access changed. This snapshot is no longer available."), frappe.PermissionError)
	return report, sources, ctx


def _observed_forecast_outcome(saved, access, sources, ctx, *, group=None):
	"""Current confirmed wins from the saved forecast cohort, by actual close date.

	This is an observed sales outcome, not a payment or an immutable historical
	state. Before the saved horizon ends, the result is explicitly provisional.
	"""
	cohort = access.get("forecast_categories", {}).get(group["key"]) if group else access.get("forecast_ids")
	if not isinstance(cohort, list) or any(not isinstance(name, str) for name in cohort):
		return {"available": False, "reason": "legacy_snapshot"}
	metadata = saved["context"]
	if metadata["timezone"] != ctx.zone or metadata["currency"] != ctx.currency:
		return {"available": False, "reason": "report_context_changed"}
	horizon = Period(date.fromisoformat(metadata["forecast_from"]), date.fromisoformat(metadata["forecast_to"]))
	observed = ctx.as_of.astimezone(ZoneInfo(ctx.zone)).date()
	if observed < horizon.start:
		return {"available": False, "reason": "horizon_not_started"}
	rows_by_name = {row["name"]: row for row in sources["CRM Deal"]}
	if len(set(cohort)) != len(cohort) or not set(cohort) <= rows_by_name.keys():
		return {"available": False, "reason": "cohort_unavailable"}
	rows = [rows_by_name[name] for name in cohort]
	won = closing(rows, "Won", horizon, ctx)
	uncertain = 0
	for row in rows:
		status = row.get("status_type")
		if status not in OPEN | CLOSED:
			uncertain += 1
		elif status == "Won":
			closed = calendar_date(row.get("closed_date"), ctx.zone)
			created = calendar_date(row.get("creation"), ctx.zone)
			if closed is None or created is None or closed < created or closed > observed:
				uncertain += 1
	measured = amount(won, ctx, extra_missing=uncertain)
	prediction = group if group else saved["metrics"]["forecast"]
	saved_value = number(prediction.get("value"))
	finished = observed > horizon.end
	difference = (str(ctx.round(measured["value"] - saved_value))
		if finished and measured["complete"] and prediction.get("complete") is True
		and saved_value is not None else None)
	return {"available": True, "value": str(measured["value"]), "complete": measured["complete"],
		"missing_count": measured["missing_count"], "won_count": len(won), "cohort_count": len(cohort),
		"period_finished": finished, "observed_at": ctx.as_of.isoformat(),
		"forecast_from": str(horizon.start), "forecast_to": str(horizon.end),
		"currency": ctx.currency, "difference_from_saved": difference,
		"basis": "current_won_deals_from_saved_forecast_cohort_closed_in_saved_horizon"}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def list_forecast_snapshots(start: int = 0, limit: int = 20):
	start, limit = max(0, int(start)), min(100, max(1, int(limit)))
	rows = frappe.get_all(DOCTYPE, filters={"viewer": frappe.session.user}, fields=["name", "title", "observed_at", "creation"],
		order_by="creation desc, name asc", start=start, limit_page_length=limit + 1)
	return {"rows": rows[:limit], "has_more": len(rows) > limit, "start": start}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_forecast_snapshot(name: str):
	doc = frappe.get_doc(DOCTYPE, name)
	current, sources, ctx = _check_access(doc)
	saved = json.loads(doc.payload)
	access = json.loads(doc.source_access)
	if access.get("source_revision"):
		same_source_version = access["source_revision"] == current["_source_revision"]
	else:
		# Older snapshots have no source revision. Their full report revision
		# includes the observation time, so compare at the saved time.
		comparable, _ = calculate(normalize_filters(frappe.parse_json(doc.filters),
			observed_at=saved["context"]["as_of"]))
		same_source_version = saved["snapshot"] == comparable["snapshot"]
	# Historical values remain immutable; current values are clearly separate.
	saved_forecast = saved["metrics"]["forecast"]
	current_forecast = current["metrics"]["forecast"]
	saved_value = number(saved_forecast.get("value"))
	current_value = number(current_forecast.get("value"))
	delta_available = (
		saved_forecast.get("complete") is True
		and current_forecast.get("complete") is True
		and saved["context"]["currency"] == current["context"]["currency"]
		and saved_value is not None and current_value is not None
	)
	forecast_delta = str(current_value - saved_value) if delta_available else None
	category_results = [
		{"key": group["key"], "weighted": group["value"], "weighted_complete": group["complete"],
			"actual": _observed_forecast_outcome(saved, access, sources, ctx, group=group)}
		for group in saved.get("forecast_categories", [])
		if group["key"] in access.get("forecast_categories", {})
	]
	return exact_json({"name": doc.name, "title": doc.title, "saved": saved,
		"current": _public(current), "same_source_version": same_source_version,
		"basis": "saved_forecast", "observed_at": doc.observed_at,
		"comparison": {"forecast_delta": forecast_delta,
			"currency": current["context"]["currency"] if delta_available else None,
			"actual": _observed_forecast_outcome(saved, access, sources, ctx), "categories": category_results}})
