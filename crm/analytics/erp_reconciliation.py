"""Read CRM products and the auditable native ERPNext document chain."""

from collections import defaultdict
import csv
from decimal import Decimal
import io
from time import time as now_seconds

import frappe
from frappe import _
from frappe.model import get_permitted_fields

from crm.analytics.call_reporting import _batch, read_named
from crm.analytics.engine import calendar_date, money, number
from crm.analytics.service import (
	_csv_cell, _sign, _verify, calculate, coherent_read, exact_json, normalize_filters, snapshot_hash,
)
from crm.utils import sales_user_only

KINDS = ("invoices", "credit_notes", "receipts", "cash_refunds")
INVOICE = "Sales Invoice"
INVOICE_FIELDS = ["name", "company", "customer", "posting_date", "docstatus", "is_return", "return_against", "base_grand_total"]
PAYMENT = "Payment Entry"
PAYMENT_FIELDS = ["name", "company", "posting_date", "docstatus", "payment_type", "party_type", "party",
	"source_exchange_rate", "target_exchange_rate"]


def _fields(doctype, parenttype=None):
	meta = frappe.get_meta(doctype)
	return set(get_permitted_fields(doctype, parenttype=parenttype, permission_type="read")) - {
		field.fieldname for field in meta.get_masked_fields(parenttype=parenttype)
	}


def _table(doctype, field):
	meta = frappe.get_meta(doctype)
	link = meta.get_field(field)
	return bool(link and link.fieldtype in ("Table", "Table MultiSelect")
		and link.permlevel in meta.get_permlevel_access("read")
		and field not in {item.fieldname for item in meta.get_masked_fields()})


def _children(child, parent, parentfield, match_field, values, fields, filters=None):
	for batch in _batch(values):
		yield from frappe.get_all(child, fields=fields, filters={
			"parenttype": parent, "parentfield": parentfield, match_field: ["in", batch], **(filters or {}),
		}, order_by="name", limit_page_length=0)


def _crm_products(report, deals, ctx):
	fields = {"product_name", "product_code", "qty"}
	if not _table("CRM Deal", "products") or not fields <= _fields("CRM Products", "CRM Deal"):
		return {"available": False, "rows": []}, {}
	names = report["selections"]["won_count"] if not report["metrics"]["won_count"].get("redacted") else []
	deals_by_name = {row["name"]: row for row in deals}
	groups = defaultdict(list)
	money_visible = report["permissions"]["money"] and "net_amount" in _fields("CRM Products", "CRM Deal")
	columns = ["parent", "name", *sorted(fields), *(["net_amount"] if money_visible else [])]
	for item in _children("CRM Products", "CRM Deal", "products", "parent", names, columns):
		deal = deals_by_name[item.parent]
		value = money({**deal, "value": item.get("net_amount")}, ctx) if money_visible else None
		qty = number(item.qty)
		groups[item.product_code or item.product_name or ""].append({
			"name": item.name, "deal": item.parent, "title": deal["title"],
			"amount": value, "quantity": qty if qty is not None and qty >= 0 else None,
			"product": item.product_name or item.product_code or "", "kind": "products",
		})
	rows, selections = [], {}
	for code, items in sorted(groups.items()):
		key = snapshot_hash(code)[:24]
		selections[key] = items
		quantities = [row["quantity"] for row in items if row["quantity"] is not None]
		amounts = [row["amount"] for row in items if row["amount"] is not None]
		rows.append({"key": key, "product_code": code, "label": items[0]["product"],
			"deal_count": len({row["deal"] for row in items}), "quantity": sum(quantities) if quantities else None,
			"quantity_complete": len(quantities) == len(items), "amount": sum(amounts) if amounts else None,
			"amount_complete": len(amounts) == len(items)})
	return {"available": True, "rows": rows}, selections


def _erp_available():
	if "erpnext" not in frappe.get_installed_apps():
		return "local_erp_unavailable"
	if frappe.db.get_single_value("ERPNext CRM Settings", "is_erpnext_in_different_site"):
		return "remote_erp_unavailable"
	required = {
		"Quotation": {"name", "crm_deal", "company", "docstatus"},
		"Sales Order": {"name", "company", "docstatus"},
		INVOICE: set(INVOICE_FIELDS) - {"base_grand_total"},
		PAYMENT: {"name", "company", "posting_date", "docstatus", "payment_type", "party_type", "party"},
	}
	children = {
		("Sales Order Item", "Sales Order", "items"): {"name", "parent", "prevdoc_docname"},
		("Sales Invoice Item", INVOICE, "items"): {"name", "parent", "sales_order", "so_detail"},
		("Payment Entry Reference", PAYMENT, "references"): {"name", "parent", "reference_name", "reference_doctype"},
	}
	if not frappe.get_meta("Quotation").has_field("crm_deal"):
		return "missing_quotation_links"
	if any(not frappe.has_permission(dt, "read") or not fields <= _fields(dt) for dt, fields in required.items()):
		return "source_permissions"
	if any(not _table(parent, field) or not fields <= _fields(child, parent)
		for (child, parent, field), fields in children.items()):
		return "source_permissions"
	return None


def _quotations(ids):
	rows = {}
	for batch in _batch(ids):
		result = frappe.get_list("Quotation", fields=["name"],
			filters={"crm_deal": ["in", batch], "docstatus": 1}, limit_page_length=0)
		for row in read_named("Quotation", ["name", "crm_deal", "company", "docstatus"], [item["name"] for item in result]):
			if row.get("crm_deal") in ids and row.get("company") and row.get("docstatus") == 1:
				rows[row["name"]] = row
	return rows


def _orders(quotes):
	candidates = list(_children("Sales Order Item", "Sales Order", "items", "prevdoc_docname", quotes,
		["name", "parent", "prevdoc_docname"]))
	orders = {row["name"]: row for row in read_named("Sales Order", ["name", "company", "docstatus"],
		{item.parent for item in candidates}) if row.get("docstatus") == 1}
	return {
		item.name: (item.parent, quotes[item.prevdoc_docname]["crm_deal"], order["company"])
		for item in candidates if (order := orders.get(item.parent)) and order.get("company") == quotes[item.prevdoc_docname]["company"]
	}


def _invoice_map(orders):
	candidate_names = {item.parent for item in _children("Sales Invoice Item", INVOICE, "items", "so_detail", orders, ["parent"])}
	candidates = {row["name"]: row for row in read_named(INVOICE, INVOICE_FIELDS, candidate_names) if row.get("docstatus") == 1}
	lines = defaultdict(list)
	for item in _children("Sales Invoice Item", INVOICE, "items", "parent", candidates, ["name", "parent", "sales_order", "so_detail"]):
		lines[item.parent].append(item)

	result, ambiguous = {}, []
	for key, row in candidates.items():
		if row.get("is_return"):
			continue
		pairs = set()
		for item in lines[key]:
			order = orders.get(item.so_detail)
			pairs.add(order[1] if order and (item.sales_order, row.get("company")) == (order[0], order[2]) else None)
		if len(pairs) != 1 or None in pairs:
			ambiguous.append(row)
			continue
		result[key] = {**row, "deal": pairs.pop()}
	return result, ambiguous


def _returns(invoices):
	names = [
		row["name"] for batch in _batch(invoices)
		for row in frappe.get_list(INVOICE, fields=["name"], filters={
			"is_return": 1, "docstatus": 1, "return_against": ["in", batch],
		}, limit_page_length=0)
	]
	result = {}
	for row in read_named(INVOICE, INVOICE_FIELDS, names):
		original = invoices.get(row.get("return_against"))
		if (original and row.get("docstatus") == 1 and row.get("is_return")
			and row.get("company") == original["company"] and row.get("customer") == original.get("customer")):
			result[row["name"]] = {**row, "deal": original["deal"]}
	return result


def _posted(row, ctx):
	day = calendar_date(row.get("posting_date"), ctx.zone)
	return bool(day and day <= ctx.as_of.date() and ctx.period.contains(day, ctx.zone))


def _payments(invoices, ctx):
	allocated = "allocated_amount" in _fields("Payment Entry Reference", PAYMENT)
	refs = list(_children("Payment Entry Reference", PAYMENT, "references", "reference_name", invoices,
		["name", "parent", "reference_name", *(["allocated_amount"] if allocated else [])],
		{"reference_doctype": INVOICE}))
	parents = {row["name"]: row for row in read_named(PAYMENT, PAYMENT_FIELDS, {ref.parent for ref in refs})
		if row.get("docstatus") == 1 and row.get("party_type") == "Customer" and _posted(row, ctx)}
	for ref in refs:
		row = parents.get(ref.parent)
		invoice = invoices[ref.reference_name]
		if not row or row.get("party") != invoice.get("customer") or row.get("company") != invoice.get("company"):
			continue
		payment_type = row.get("payment_type")
		if payment_type == "Receive":
			kind, rate = "receipts", number(row.get("source_exchange_rate"))
		elif payment_type == "Pay" and invoice.get("is_return"):
			kind, rate = "cash_refunds", number(row.get("target_exchange_rate"))
		else:
			continue
		amount = number(ref.get("allocated_amount"))
		value = ctx.round(amount * rate) if amount is not None and rate is not None and rate > 0 else None
		yield kind, row, invoice, ref, abs(value) if value is not None and kind == "cash_refunds" else value


def _erp(ids, ctx):
	reason = _erp_available()
	if reason:
		return {"available": False, "reason": reason}, {}
	orders = _orders(_quotations(ids))
	invoices, ambiguous = _invoice_map(orders)
	returns = _returns(invoices)
	invoices_with_returns = invoices | returns
	payments = list(_payments(invoices_with_returns, ctx))
	companies = {row.get("company") for row in invoices_with_returns.values()}
	base = {row["name"]: row.get("default_currency") for row in
		read_named("Company", ["name", "default_currency"], {company for company in companies if company})}
	groups = {key: [] for key in KINDS}
	for kind, records in (("invoices", invoices), ("credit_notes", returns)):
		for row in records.values():
			if not _posted(row, ctx):
				continue
			value = number(row.get("base_grand_total"))
			if base.get(row["company"]) != ctx.currency or value is None or ((value < 0) != (kind == "credit_notes") and value != 0):
				value = None
			groups[kind].append({"name": row["name"], "document": row["name"], "deal": row["deal"],
				"company": row["company"], "date": row["posting_date"], "amount": abs(value) if value is not None else None,
				"doctype": INVOICE, "kind": kind})
	for kind, row, invoice, ref, value in payments:
		groups[kind].append({"name": ref.name, "document": row["name"], "deal": invoice["deal"], "invoice": invoice["name"],
			"company": row["company"], "date": row["posting_date"], "amount": value if base.get(row["company"]) == ctx.currency else None,
			"doctype": PAYMENT, "kind": kind})
	result = {}
	for key, rows in groups.items():
		rows.sort(key=lambda row: (str(row["date"]), row["name"]), reverse=True)
		known = [row["amount"] for row in rows if row["amount"] is not None]
		result[key] = {"documents": len({row["document"] for row in rows}), "rows": len(rows), "currency": ctx.currency,
			"amount": sum(known) if known or not rows else None, "unknown_amounts": len(rows) - len(known)}
	return {"available": True, "ambiguous_invoices": sum(_posted(row, ctx) for row in ambiguous), "metrics": result}, groups


def _calculate(filters):
	ctx = normalize_filters(filters)
	context = ctx.metadata()
	if ctx.period.start > ctx.as_of.date():
		return {"context": context, "products": {"available": False, "rows": []},
			"erp": {"available": False, "reason": "in_future"}}, {}, ""
	report, source = calculate(ctx, include_source_revision=False)
	deals = source["CRM Deal"]
	products, product_rows = _crm_products(report, deals, ctx)
	erp, erp_rows = _erp({row["name"] for row in deals if ctx.includes(row)}, ctx)
	result = {"context": context, "products": products, "erp": erp}
	selections = {"products": product_rows, "erp": erp_rows}
	revision = snapshot_hash({**result, "context": {key: value for key, value in context.items() if key != "as_of"}}, selections)
	return result, selections, revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_report(filters: dict | str | None = None):
	report, _rows, revision = _calculate(filters)
	if revision:
		report["token"] = _sign({"site": frappe.local.site, "user": frappe.session.user, "purpose": "erp-reconciliation",
			"filters": filters, "revision": revision, "expires": now_seconds() + 120})
	return exact_json(report)


def _selected(token, source, group):
	claim = _verify(token)
	if claim.get("purpose") != "erp-reconciliation" or source not in ("erp", "products"):
		frappe.throw(_("This reconciliation detail is unavailable."), frappe.PermissionError)
	_report, selections, revision = _calculate(claim["filters"])
	if revision != claim["revision"]:
		frappe.throw(_("Source documents changed. Refresh the reconciliation."), frappe.TimestampMismatchError)
	if group not in selections[source]:
		frappe.throw(_("This reconciliation detail is unavailable."), frappe.PermissionError)
	return selections[source][group], revision


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_details(token: str, source: str, group: str, start: int = 0):
	rows, _revision = _selected(token, source, group)
	start = max(0, start)
	return exact_json({"rows": rows[start:start + 50], "total": len(rows)})


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def export_details(token: str, source: str, group: str):
	rows, revision = _selected(token, source, group)
	stream = io.StringIO(newline="")
	writer = csv.writer(stream, lineterminator="\r\n")
	columns = (("name", "deal", "product", "quantity", "amount") if source == "products"
		else ("document", "deal", "invoice", "company", "date", "amount"))
	writer.writerow(columns)
	for row in exact_json(rows):
		writer.writerow([_csv_cell(row.get(column)) for column in columns])
	return {"filename": f"crm-reconciliation-{source}-{revision[:12]}.csv", "csv": stream.getvalue(), "total": len(rows)}
