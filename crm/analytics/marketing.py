"""Campaign results from visible CRM records and explicit period-specific costs."""

from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
from time import time as now_seconds

import frappe
from frappe import _

from crm.analytics.call_reporting import read_named
from crm.analytics.engine import amount, number
from crm.analytics.sales_plans import company_plan_editor, currency_and_precision
from crm.analytics.service import (
	_csv_cell, _sign, _verify, calculate, coherent_read, exact_json, normalize_filters, snapshot_hash,
)
from crm.analytics.utm import UTM_FIELDS, clean_document_tags, clean_tag, readable_tags
from crm.utils import sales_user_only

SPEND = "CRM Campaign Spend"
SPEND_FIELDS = ["name", *UTM_FIELDS, "confirmed_amount", "source_reference", "modified"]
SOURCES = {"leads": ("CRM Lead", "new_leads"), "won": ("CRM Deal", "won_count")}


def _deny():
	frappe.throw(_("This campaign data is unavailable with your permissions."), frappe.PermissionError)


def _dimensions(row):
	return tuple(row.get(field) or "" for field in UTM_FIELDS)


def _identifier(dimensions, start, end, currency):
	return "spend-" + snapshot_hash(dimensions, str(start), str(end), currency)[:40]


def _dates(start, end):
	try:
		left = date.fromisoformat(str(start))
		right = date.fromisoformat(str(end))
	except (TypeError, ValueError):
		frappe.throw(_("Select valid campaign expense dates."), frappe.ValidationError)
	if left > right or right > normalize_filters().as_of.date() or (right - left).days >= 366:
		frappe.throw(_("Campaign expenses require an observed period of up to 366 days."), frappe.ValidationError)
	return left, right


def _cost(value, precision):
	value = number(value)
	try:
		if value is not None and 0 <= value <= Decimal("1000000000") and value == value.quantize(Decimal(1).scaleb(-precision)):
			return format(value.normalize(), "f")
	except InvalidOperation:
		pass
	frappe.throw(_("Enter a non-negative cost within the reporting currency precision."), frappe.ValidationError)


def validate_spend(doc):
	if not company_plan_editor():
		_deny()
	clean_document_tags(doc)
	left, right = _dates(doc.from_date, doc.to_date)
	currency, precision = currency_and_precision()
	if doc.report_currency != currency or not doc.utm_campaign or doc.name != _identifier(_dimensions(doc), left, right, currency):
		frappe.throw(_("Enter a campaign and the current reporting currency."), frappe.ValidationError)
	doc.confirmed_amount = _cost(doc.confirmed_amount, precision)
	doc.source_reference = clean_tag(doc.source_reference)
	if not doc.source_reference:
		frappe.throw(_("Enter the reference that confirms this expense."), frappe.ValidationError)


def _permitted_tags(doctype):
	return frappe.has_permission(doctype, "read") and set(UTM_FIELDS) <= readable_tags(doctype)


def _can_record(ctx):
	return (company_plan_editor() and not (ctx.owner or ctx.source or ctx.pipeline)
		and all(_permitted_tags(doctype) for doctype, _metric in SOURCES.values()) and frappe.db.table_exists(SPEND))


def _group():
	return {"leads": [], "won": []}


def _calculate(filters):
	ctx = normalize_filters(filters)
	context = ctx.metadata()
	context["viewer"] = frappe.session.user
	if ctx.period.start > ctx.as_of.date():
		return {"context": context, "available": False, "reason": "in_future", "rows": []}, {}, ""
	report, sources = calculate(ctx, include_source_revision=False)
	visible = {kind: _permitted_tags(doctype) and not report["metrics"][metric].get("redacted", False)
		for kind, (doctype, metric) in SOURCES.items()}
	omitted, groups = {}, defaultdict(_group)
	for kind, (doctype, metric) in SOURCES.items():
		if not visible[kind]:
			omitted[kind] = None
			continue
		ids = report["selections"][metric]
		if not ids:
			omitted[kind] = 0
			continue
		named = {row["name"]: row for row in sources[doctype]}
		count = 0
		for row in read_named(doctype, ["name", *UTM_FIELDS], ids):
			if not all(field in row for field in UTM_FIELDS):
				continue
			groups[_dimensions(row)][kind].append(named[row["name"]])
			count += 1
		omitted[kind] = len(ids) - count

	can_record = _can_record(ctx)
	costs = {}
	if can_record:
		costs = {_dimensions(row): row for row in frappe.get_all(SPEND, fields=SPEND_FIELDS,
			filters={"from_date": ctx.period.start, "to_date": ctx.period.end, "report_currency": ctx.currency},
			limit_page_length=0)}

	rows, selections = [], {}
	for key in sorted(groups.keys() | costs.keys()):
		source = groups.get(key, _group())
		row_key = snapshot_hash(key)[:24]
		spend = costs.get(key)
		revenue = amount(source["won"], ctx) if visible["won"] else None
		known = bool(revenue and revenue["complete"] and report["metrics"]["won_value"].get("complete"))
		known = known and not omitted["won"] and not report["metrics"]["won_value"].get("redacted")
		value = revenue["value"] if revenue and not report["metrics"]["won_value"].get("redacted") else None
		cost = number(spend.confirmed_amount) if spend else None
		rows.append({"key": row_key, **dict(zip(UTM_FIELDS, key, strict=True)),
			"leads": len(source["leads"]) if visible["leads"] else None,
			"won": len(source["won"]) if visible["won"] else None,
			"won_value": value, "won_value_complete": bool(known), "cost": cost,
			"revenue_to_cost": ctx.round(value / cost) if cost and known else None,
			"cost_version": str(spend.modified) if spend else None,
			"source_reference": spend.source_reference if spend else None,
		})
		selections[row_key] = {
			kind: [{"name": doc["name"], "title": doc["title"]} for doc in sorted(docs, key=lambda item: item["name"])]
			for kind, docs in source.items()
		}
	rows.sort(key=lambda row: (not row["utm_campaign"], -((row["leads"] or 0) + (row["won"] or 0)),
		row["utm_campaign"], row["utm_source"], row["utm_medium"]))
	payload = {"available": any(visible.values()), "context": context, "visible": visible, "omitted": omitted,
		"costs_enabled": can_record, "rows": rows}
	revision = snapshot_hash({**payload, "context": {key: value for key, value in context.items() if key != "as_of"}}, selections)
	return payload, selections, revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_report(filters: dict | str | None = None):
	report, _rows, revision = _calculate(filters)
	if report["available"]:
		report["token"] = _sign({"site": frappe.local.site, "user": frappe.session.user, "purpose": "marketing",
			"filters": filters, "revision": revision, "expires": now_seconds() + 120})
	return exact_json(report)


def _selected(token, group, kind):
	claim = _verify(token)
	if claim.get("purpose") != "marketing" or kind not in SOURCES:
		_deny()
	report, selections, revision = _calculate(claim["filters"])
	if revision != claim["revision"]:
		frappe.throw(_("The campaign report changed. Refresh the figures."), frappe.TimestampMismatchError)
	if not report["visible"].get(kind) or group not in selections:
		_deny()
	return selections[group][kind], revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(token: str, group: str, kind: str, start: int = 0):
	rows, _revision = _selected(token, group, kind)
	start = max(0, start)
	return {"rows": rows[start:start + 50], "total": len(rows)}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export_details(token: str, group: str, kind: str):
	rows, revision = _selected(token, group, kind)
	stream = io.StringIO(newline="")
	writer = csv.writer(stream, lineterminator="\r\n")
	writer.writerow(["ID", "Title"])
	for row in rows:
		writer.writerow([_csv_cell(row["name"]), _csv_cell(row["title"])])
	return {"filename": f"crm-marketing-{kind}-{revision[:12]}.csv", "csv": stream.getvalue(), "total": len(rows)}


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_cost(
	from_date: str, to_date: str, currency: str, utm_source: str, utm_medium: str, utm_campaign: str,
	confirmed_amount: str, source_reference: str, expected_viewer: str, expected_version: str | None = None,
):
	if expected_viewer != frappe.session.user or not company_plan_editor():
		_deny()
	left, right = _dates(from_date, to_date)
	ctx = normalize_filters({"from_date": str(left), "to_date": str(right)})
	if not _can_record(ctx):
		_deny()
	values = tuple(clean_tag(value) for value in (utm_source, utm_medium, utm_campaign))
	reference = clean_tag(source_reference)
	if not values[-1] or not reference or currency != ctx.currency:
		frappe.throw(_("Confirm the campaign, expense reference and reporting currency."), frappe.ValidationError)
	cost = _cost(confirmed_amount, ctx.precision)
	name = _identifier(values, left, right, currency)
	try:
		current = frappe.db.get_value(SPEND, name, ["modified", "confirmed_amount", "source_reference"], as_dict=True, for_update=True)
		if current and current.confirmed_amount == cost and current.source_reference == reference:
			return {"version": str(current.modified)}
		if (expected_version or "") != (str(current.modified) if current else ""):
			frappe.throw(_("The campaign expense changed. Open the latest version."), frappe.TimestampMismatchError)
		if current:
			doc = frappe.get_doc(SPEND, name, for_update=True)
			doc.update({"confirmed_amount": cost, "source_reference": reference})
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": SPEND, **dict(zip(UTM_FIELDS, values, strict=True)),
				"from_date": left, "to_date": right, "report_currency": currency,
				"confirmed_amount": cost, "source_reference": reference})
			doc.insert(set_name=name, ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.QueryDeadlockError):
		frappe.throw(_("The campaign expense changed. Open the latest version."), frappe.TimestampMismatchError)
	return {"version": str(doc.modified)}
