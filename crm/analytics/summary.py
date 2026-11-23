"""Verified summary grammar. Models may select facts; CRM renders every number.

No customer text, credentials, prompts, or provider network client are included.
A real provider is deliberately opt-in and requires a separately approved adapter.
"""

import frappe
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from crm.analytics.call_reporting import _call_context, _make_report as call_report
from crm.analytics.engine import RISK_REASONS
from crm.analytics.service import _verify, calculate, coherent_read, exact_json, normalize_filters, snapshot_hash
from crm.utils import sales_user_only

ALLOWED = ("won_value", "won_count", "open_value", "forecast", "risk_count", "risk_value", "win_rate")
CALL_FACTS = {
	"calls_total": ("total", "count"),
	"calls_missed": ("missed", "count"),
	"calls_overdue": ("overdue", "count"),
	"calls_sla": ("sla_percent", "percent"),
}
_SELECTION_CACHE_SECONDS = 3600


def configured_selector():
	"""Return a site-approved selector, or None when no provider is connected.

	The CRM core never imports a provider client or credentials. An authorized
	adapter can supply a callable that accepts model_input() and returns only a
	selection of metric keys; the server still validates and renders every fact.
	"""
	return None


def _selection_cache_key(report, payload):
	identity = {"site": frappe.local.site, "user": frappe.session.user,
		"snapshot": report["snapshot"], "permissions": report.get("permissions"),
		"input": payload}
	digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
	return "crm:analytics:summary:selection:" + digest


def _provider_selection(report):
	selector = configured_selector()
	if selector is None:
		return None, "not_configured"
	input_data = model_input(report)
	key = _selection_cache_key(report, input_data)
	cache = frappe.cache()
	# A prior selection is only a suggestion. Every read rechecks source rights
	# and the current snapshot before reaching this cache, and verifies the
	# selected facts again against the freshly computed permitted report.
	cached = cache.get_value(key, shared=True, use_local_cache=False)
	if cached is not None:
		return cached["selection"], cached["status"]
	try:
		with cache.lock(key + ":lock", timeout=120, blocking_timeout=5):
			cached = cache.get_value(key, shared=True, use_local_cache=False)
			if cached is not None:
				return cached["selection"], cached["status"]
			try:
				selection = selector(input_data)
				if not isinstance(selection, dict) or len(json.dumps(selection, ensure_ascii=False).encode()) > 4096:
					selection = {}
				status = "response_received"
			except Exception:
				selection, status = None, "unavailable"
			cache.set_value(key, {"selection": selection, "status": status},
				expires_in_sec=_SELECTION_CACHE_SECONDS if status == "response_received" else 30,
				shared=True)
			return selection, status
	except Exception:
		# A busy or unavailable cache must not start a second provider call.
		return None, "unavailable"


def measured_source_contribution(report, selected):
	"""Describe a complete permitted partition of won amount, never a cause."""
	permissions = report.get("permissions", {})
	metrics = report["metrics"]
	amount = metrics["won_value"]
	count = metrics["won_count"]
	if "won_value" not in selected or not permissions.get("money") or not permissions.get("source"):
		return None
	if not amount.get("complete") or not count.get("complete") or amount.get("redacted"):
		return None
	total = Decimal(str(amount["value"]))
	if total <= 0 or not report.get("sources"):
		return None
	groups = report["sources"]
	if any(not row.get("complete") or row.get("redacted") or row.get("currency") != report["context"]["currency"]
		or row.get("value") is None or Decimal(str(row["value"])) < 0 for row in groups):
		return None
	if sum(Decimal(str(row["value"])) for row in groups) != total:
		return None
	if sum(row["count"] for row in groups) != count["value"]:
		return None
	leaders = sorted(groups, key=lambda row: (-Decimal(str(row["value"])), row["key"]))
	first = leaders[0]
	value = Decimal(str(first["value"]))
	return {"kind": "measured", "dimension": "source", "key": first["key"],
		"metric": "won_value", "value": value, "total": total,
		"share_pct": (value * 100 / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
		"count": first["count"], "total_count": count["value"], "basis": "current_dimensions"}


def call_summary(ctx):
	"""Get permitted facts for the same date and CRM filters as the sales summary."""
	filters = {"from_date": str(ctx.period.start), "to_date": str(ctx.period.end),
		"employee": ctx.owner, "pipeline": ctx.pipeline, "source": ctx.source}
	try:
		calls, _rows, revision = call_report(filters, _call_context(filters, observed_at=ctx.as_of))
	except (frappe.PermissionError, frappe.ValidationError):
		return {"status": "unavailable", "revision": None, "facts": {}}
	metrics = calls["metrics"]
	if not metrics["total"]:
		return {"status": "empty", "revision": revision, "facts": {}}
	facts = {}
	for key, (detail_metric, unit) in CALL_FACTS.items():
		value = metrics[detail_metric]
		if value is None:
			continue
		fact = {"value": value, "unit": unit, "detail_metric": detail_metric}
		if basis := metrics["rate_bases"].get(detail_metric):
			fact["basis"] = basis
		facts[key] = fact
	return {"status": "available", "revision": revision, "facts": facts}


def _summary_revision(report):
	calls = report.get("_summary_calls")
	return snapshot_hash(report["snapshot"], calls["status"], calls["revision"]) if calls else report["snapshot"]


def _selection_metrics(report):
	permitted = {key: report["metrics"][key] for key in ALLOWED if not report["metrics"][key].get("redacted")}
	for key, fact in report.get("_summary_calls", {}).get("facts", {}).items():
		permitted[key] = {"value": fact["value"], "unit": fact["unit"]}
	return permitted


def model_input(report):
	return exact_json({"contract": report["context"]["contract"], "snapshot": _summary_revision(report),
		"metrics": _selection_metrics(report),
		"period": {key: report["context"][key] for key in ("from_date", "to_date", "forecast_from", "forecast_to", "currency")}})


def measured_risk_reasons(report, selected):
	"""Count permitted attention reasons once per deal without summing overlapping causes."""
	if "risk_count" not in selected or report["metrics"]["risk_count"].get("redacted"):
		return []
	attention = report.get("attention", [])
	if len(attention) != report["metrics"]["risk_count"]["value"]:
		return []
	counts = {code: 0 for code in RISK_REASONS}
	for row in attention:
		for code in set(row.get("reasons") or []) & counts.keys():
			counts[code] += 1
	return [{"code": code, "count": counts[code]} for code in sorted(
		RISK_REASONS, key=lambda key: (-counts[key], RISK_REASONS.index(key))
	) if counts[code]]


def verified_summary(report, *, selection=None, provider_status="not_configured"):
	permitted = list(_selection_metrics(report))
	keys = permitted[:]
	status = "deterministic"
	if selection is not None:
		# Reject prose, supplied numeric claims, IDs, links, and unsupported causes.
		valid = isinstance(selection, dict) and set(selection) == {"snapshot", "facts"} and selection["snapshot"] == _summary_revision(report)
		facts = selection.get("facts") if valid else None
		valid = valid and isinstance(facts, list) and 1 <= len(facts) <= len(permitted) and all(isinstance(f, str) and f in permitted for f in facts) and len(set(facts)) == len(facts)
		if valid:
			keys, status = facts, "verified_selection"
		else:
			provider_status = "invalid_response"
	no_period_outcomes = all(
		report["metrics"][key].get("complete") is True and report["metrics"][key].get("value") == 0
		for key in ("new_deals", "won_count", "lost_count")
	)
	sales_keys = [key for key in keys if key in ALLOWED]
	result = {"snapshot": report["snapshot"], "context": report["context"], "mode": status,
		"provider_status": provider_status,
		"facts": [{"metric": key, **report["metrics"][key]} for key in sales_keys],
		"source_contribution": measured_source_contribution(report, keys),
		"risk_reasons": measured_risk_reasons(report, keys),
		"limits": ["current_dimensions", "won_is_not_payment", "no_causal_claims"]
			+ (["incomplete_data"] if any(not report["metrics"][key].get("complete", True) for key in sales_keys) else [])
			+ (["no_period_outcomes"] if no_period_outcomes else [])}
	if calls := report.get("_summary_calls"):
		result["calls"] = {**calls, "facts": [{"metric": key, **calls["facts"][key]}
			for key in keys if key in calls["facts"]]}
	return result


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_summary(snapshot_token: str, include_calls: bool = False):
	payload = _verify(snapshot_token)
	ctx = normalize_filters(payload["filters"])
	report, _ = calculate(ctx, include_source_revision=False)
	if report["snapshot"] != payload["snapshot"]:
		frappe.throw(frappe._("The report changed. Refresh before generating a summary."), frappe.TimestampMismatchError)
	# Preserve the signed report label when only the observation clock moved.
	report["context"]["as_of"] = payload["observed_at"]
	if include_calls:
		report["_summary_calls"] = call_summary(ctx)
	selection, provider_status = _provider_selection(report)
	return exact_json(verified_summary(report, selection=selection, provider_status=provider_status))
