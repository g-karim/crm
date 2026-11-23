"""Existing chart/layout schema backed by the shared authorized calculations."""

from collections import defaultdict
from decimal import Decimal

import frappe

from crm.analytics.engine import amount, calendar_date, closing, forecast_value
from crm.analytics.service import exact_json, normalize_filters


def context(from_date=None, to_date=None, user=None, *, days=None):
	filters = {key: str(value) for key, value in {"from_date": from_date, "to_date": to_date, "owner": user}.items() if value}
	# The legacy date picker selects the results period. Forecast keeps its
	# own rolling future horizon, as it does on the main Analytics page.
	if days is not None and (days not in (7, 30, 60, 90) or from_date or to_date):
		frappe.throw(frappe._("Select a supported dashboard period or enter dates."), frappe.ValidationError)
	return normalize_filters(filters, default_days=days or 30)


def chart(name, report, sources, ctx):
	m = report["metrics"]
	deals = [r for r in sources["CRM Deal"] if ctx.includes(r)]
	leads = [r for r in sources["CRM Lead"] if ctx.includes(r)]
	opened = [r for r in deals if r["status_type"] not in {"Won", "Lost"}]
	won = closing(deals, "Won", ctx.period, ctx)
	lost = closing(deals, "Lost", ctx.period, ctx)
	created = [r for r in deals if ctx.period.contains(r["creation"], ctx.zone)]
	metrics = {"total_leads": ("new_leads", "New leads"), "ongoing_deals": ("open_count", "Open deals now"),
		"won_deals": ("won_count", "Won deals by closure date"), "average_won_deal_value": ("average_won_value", "Average won deal value"),
		"average_time_to_close_a_deal": ("average_cycle", "Average deal cycle"),
		"average_time_to_close_a_lead": ("lead_cycle", "Median lead-to-win cycle")}
	if name in metrics:
		key, title = metrics[name]
		return exact_json({"title": frappe._(title), "tooltip": frappe._("Current dimensions. Known values only; see Analytics for coverage."),
			"value": m[key]["value"], "delta": m[key].get("delta"), "deltaSuffix": "%", "complete": m[key].get("complete", True),
			"suffix": " days" if key in {"average_cycle", "lead_cycle"} else " " + ctx.currency if key == "average_won_value" else ""})
	if name in {"average_ongoing_deal_value", "average_deal_value"}:
		rows = opened if name == "average_ongoing_deal_value" else created
		total = amount(rows, ctx)
		return exact_json({"title": frappe._("Average open value now" if name == "average_ongoing_deal_value" else "Average newly created deal value"),
			"tooltip": frappe._("Known complete amounts only"), "value": ctx.round(total["value"] / len(rows)) if rows and total["complete"] and report["permissions"]["money"] else None,
			"suffix": " " + ctx.currency, "complete": total["complete"] and report["permissions"]["money"], "delta": None})
	if name == "sales_trend":
		return {"title": frappe._("Daily results"), "subtitle": frappe._("Wins use closure date; leads and deals use creation date"),
			"data": [{"date": d["date"], "leads": d["new_leads"], "deals": d["new_deals"], "won_deals": d["won_count"]} for d in report["trend"]],
			"xAxis": {"title": frappe._("Date"), "key": "date", "type": "time", "timeGrain": "day"}, "yAxis": {"title": frappe._("Count")},
			"series": [{"name": key, "type": "line", "showDataPoints": True} for key in ["leads", "deals", "won_deals"]]}
	if name == "forecasted_revenue":
		groups = defaultdict(lambda: Decimal(0))
		for row in opened:
			if ctx.horizon.contains(row.get("expected_date"), ctx.zone) and (value := forecast_value(row, ctx)) is not None:
				groups[str(calendar_date(row["expected_date"], ctx.zone))[:7] + "-01"] += value
		return exact_json({"title": frappe._("Weighted open forecast"), "subtitle": f"{ctx.horizon.start} — {ctx.horizon.end}; {ctx.currency}",
			"data": [{"date": key, "value": value} for key, value in sorted(groups.items())] if report["permissions"]["forecast"] else [],
			"complete": m["forecast"]["complete"], "xAxis": {"title": frappe._("Expected close"), "key": "date", "type": "time", "timeGrain": "month"},
			"yAxis": {"title": ctx.currency}, "series": [{"name": "value", "type": "bar"}]})
	if name == "open_value_by_pipeline":
		if not report["permissions"]["money"] or not report["permissions"]["status"]:
			return {"unavailable": True, "message": frappe._("Open pipeline values are unavailable with current permissions.")}
		groups = sorted(report["open_pipelines"], key=lambda row: (-Decimal(str(row["value"] or 0)), str(row["key"])))
		if any(abs(Decimal(str(row["value"] or 0))) > 9007199254740991 for row in groups):
			return {"unavailable": True, "message": frappe._("The chart scale cannot represent these amounts safely. Open Analytics for exact values.")}
		data = [{"pipeline": report["labels"]["pipelines"].get(row["key"], row["key"]) or frappe._("Unspecified"),
			"value": float(row["value"]), "exact_value": row["value"],
			"count": row["count"], "complete": row["complete"]} for row in groups]
		return exact_json({"title": frappe._("Open value by pipeline now"),
			"subtitle": frappe._("Current readable open deals; known part only") if not m["open_value"]["complete"] else frappe._("Current readable open deals"),
			"data": data, "complete": m["open_value"]["complete"],
			"xAxis": {"title": frappe._("Pipeline"), "key": "pipeline", "type": "category"},
			"yAxis": {"title": ctx.currency}, "swapXY": True,
			"echartOptions": {"grid": {"right": "12%"}},
			"series": [{"name": "value", "type": "bar", "showDataLabels": True}]})
	if name == "funnel_conversion":
		rows = report["funnel"]["visited"] if report["funnel"] else []
		return {"title": frappe._("Distinct deals visiting each stage"), "subtitle": frappe._("Creation cohort; repeated visits count once"),
			"data": [{"stage": report["labels"]["stages"].get(r["stage"], r["stage"]), "count": r["count"]} for r in rows],
			"xAxis": {"title": frappe._("Stage"), "key": "stage", "type": "category"}, "yAxis": {"title": frappe._("Deals")}, "series": [{"name": "count", "type": "bar"}]}
	if name in {"deals_by_stage_donut", "deals_by_stage_axis", "deals_by_source", "leads_by_source", "lost_deal_reasons", "deals_by_territory", "deals_by_salesperson"}:
		key, rows, label_key = {
			"deals_by_stage_donut": ("status", opened, "stage"), "deals_by_stage_axis": ("status", opened, "stage"),
			"deals_by_source": ("source", created, "source"), "leads_by_source": ("source", [r for r in leads if ctx.period.contains(r["creation"], ctx.zone)], "source"),
			"lost_deal_reasons": ("lost_reason", lost, "reason"), "deals_by_territory": ("territory", created, "territory"),
			"deals_by_salesperson": ("owner", won, "salesperson")}[name]
		groups = defaultdict(list)
		for row in rows:
			groups[row.get(key) or ""].append(row)
		data = []
		for group, items in sorted(groups.items()):
			label = report["labels"]["stages"].get(group, group) if key == "status" else group
			data.append({label_key: label or frappe._("Unspecified"), "count": len(items), "deals": len(items),
				"value": amount(items, ctx)["value"] if report["permissions"]["money"] and name != "leads_by_source" else None})
		result = {"title": frappe._({"deals_by_stage_donut": "Open deals now", "deals_by_stage_axis": "Open stages now",
			"deals_by_source": "New deals by current source", "leads_by_source": "New leads by current source",
			"lost_deal_reasons": "Loss reasons by loss date", "deals_by_territory": "New deals by current territory", "deals_by_salesperson": "Wins by current owner"}[name]),
			"data": exact_json(data), "subtitle": frappe._("Current readable dimensions"), "categoryColumn": label_key, "valueColumn": "count",
			"xAxis": {"title": frappe._("Group"), "key": label_key, "type": "category"}, "yAxis": {"title": frappe._("Deals")}, "series": [{"name": "count", "type": "bar"}]}
		return result
	return {"unavailable": True, "message": frappe._("This chart is unavailable.")}
