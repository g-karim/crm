"""Campaign attribution from saved CRM references, in the viewer's call scope."""

from collections import defaultdict
import csv
from dataclasses import replace
import io
from time import time as now_seconds

import frappe
from frappe import _
from frappe.model import get_permitted_fields

from crm.analytics.call_reporting import CALL, _batch, call_facts, read_named
from crm.analytics.service import (
	_csv_cell, _sign, _verify, coherent_read, exact_json, normalize_filters, readable_rows,
	related_scope, snapshot_hash, source_snapshot,
)
from crm.analytics.utm import UTM_FIELDS
from crm.utils import sales_user_only

LEAD = "CRM Lead"
DEAL = "CRM Deal"
PURPOSE = "call_attribution"


def _campaign(reference):
	if reference is None or not all(field in reference for field in UTM_FIELDS):
		return "unavailable", ("", "", "")
	values = tuple(reference.get(field) or "" for field in UTM_FIELDS)
	return ("campaign", values) if values[-1] else ("untagged", ("", "", ""))


def _can_read_deal_lead():
	return "lead" in get_permitted_fields(DEAL, permission_type="read") and "lead" not in {
		field.fieldname for field in frappe.get_meta(DEAL).get_masked_fields()
	}


def _references(calls):
	direct_leads = {row["parent_name"] for row in calls if row["parent_type"] == LEAD and row["parent_name"]}
	direct_deals = {row["parent_name"] for row in calls if row["parent_type"] == DEAL and row["parent_name"]}
	deals = {row["name"]: row for row in read_named(DEAL, ["name", "lead", *UTM_FIELDS], direct_deals)}
	lead_names = direct_leads | {row.get("lead") for row in deals.values() if row.get("lead")}
	leads = {row["name"]: row for row in read_named(LEAD, ["name", *UTM_FIELDS], lead_names)}
	deal_links = defaultdict(set)
	if _can_read_deal_lead():
		for batch in _batch(direct_leads & leads.keys()):
			rows, _ = readable_rows(DEAL, ["name", "lead"], {"lead": ["in", batch]})
			for row in rows:
				if row.get("lead") in leads:
					deal_links[row["lead"]].add(row["name"])
	return leads, deals, deal_links


def _calculate(filters):
	ctx = normalize_filters(filters)
	context = ctx.metadata()
	if ctx.period.start > ctx.as_of.date() or not frappe.has_permission(CALL, "read"):
		return {"available": False, "context": context, "rows": []}, {}, ""
	related = None
	if ctx.pipeline or ctx.source:
		scope = replace(ctx, owner=None)
		deals, leads, *_ = source_snapshot(scope)
		related = related_scope(deals, leads, scope)
	calls, _, _ = call_facts(ctx, related=related)
	leads, deals, deal_links = _references(calls)
	groups = defaultdict(list)
	for call in calls:
		kind, name = call["parent_type"], call["parent_name"]
		lead, deal_names = None, []
		if kind == LEAD and name:
			state, dimensions = _campaign(leads.get(name))
			lead = name if name in leads else None
			deal_names = sorted(deal_links.get(name, ()))
		elif kind == DEAL and name:
			deal = deals.get(name)
			state, dimensions = _campaign(deal)
			if deal:
				deal_names = [name]
				lead = deal.get("lead") if deal.get("lead") in leads else None
		else:
			state, dimensions = "unlinked", ("", "", "")
		groups[(state, dimensions)].append({
			"name": call["name"], "at": call["at"], "direction": call["direction"],
			"lead": lead, "deals": deal_names,
		})
	rows, selections = [], {}
	for (state, dimensions), entries in groups.items():
		key = snapshot_hash(state, dimensions)[:24]
		selections[key] = entries
		rows.append({
			"key": key, "state": state, **dict(zip(UTM_FIELDS, dimensions, strict=True)),
			"calls": len(entries), "with_lead": sum(bool(row["lead"]) for row in entries),
			"with_deal": sum(bool(row["deals"]) for row in entries),
		})
	rows.sort(key=lambda row: (row["state"] != "campaign", -row["calls"], row["utm_campaign"], row["key"]))
	report = {"available": True, "context": context, "total": len(calls),
		"tagged": sum(row["calls"] for row in rows if row["state"] == "campaign"), "rows": rows}
	revision = snapshot_hash(report["rows"], selections, {key: value for key, value in context.items() if key != "as_of"})
	return report, selections, revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_report(filters: dict | str | None = None):
	report, _, revision = _calculate(filters)
	if report["available"]:
		report["token"] = _sign({"site": frappe.local.site, "user": frappe.session.user, "purpose": PURPOSE,
			"filters": filters, "revision": revision, "expires": now_seconds() + 120})
	return exact_json(report)


def _selected(token, group):
	claim = _verify(token)
	if claim.get("purpose") != PURPOSE:
		frappe.throw(_("This campaign call selection is unavailable."), frappe.PermissionError)
	report, selections, revision = _calculate(claim["filters"])
	if revision != claim["revision"]:
		frappe.throw(_("The campaign call report changed. Refresh the figures."), frappe.TimestampMismatchError)
	if not report["available"] or group not in selections:
		frappe.throw(_("This campaign call selection is unavailable."), frappe.PermissionError)
	return selections[group], revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(token: str, group: str, start: int = 0):
	rows, _ = _selected(token, group)
	start = max(0, start)
	return exact_json({"rows": rows[start:start + 50], "total": len(rows)})


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export_details(token: str, group: str):
	rows, revision = _selected(token, group)
	stream = io.StringIO(newline="")
	writer = csv.writer(stream, lineterminator="\r\n")
	writer.writerow(["Call", "Time", "Direction", "Lead", "Deals"])
	for row in rows:
		writer.writerow([_csv_cell(value) for value in (
			row["name"], row["at"].isoformat(), row["direction"], row["lead"] or "", " | ".join(row["deals"]),
		)])
	return {"filename": f"crm-call-attribution-{revision[:12]}.csv", "csv": stream.getvalue(), "total": len(rows)}
