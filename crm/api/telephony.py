"""Read-only workspace over native call logs and their permitted CRM context."""
import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.query_builder import Criterion, Order
from frappe.query_builder.functions import Coalesce
from frappe.utils import add_days, cint, today

REFERENCES = {
	"CRM Lead": ("lead_name", "leads"),
	"CRM Deal": ("deal_name", "deals"),
	"Contact": ("full_name", "contacts"),
}
MISSED_STATUSES = ("No Answer", "Busy", "Failed", "Canceled")
ROW_FIELDS = [
	"name", "type", "status", "duration", "from", "to", "caller", "receiver",
	"start_time", "creation", "recording_url", "reference_doctype", "reference_docname",
	"exolve_recording_state",
]


def _check_read():
	if not frappe.has_permission("CRM Call Log", "read"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)


def _reference_query(doctype, search=None):
	if not frappe.has_permission(doctype, "read"):
		return None
	query = frappe.qb.get_query(doctype, fields=["name"], ignore_permissions=False)
	if search:
		table = frappe.qb.DocType(doctype)
		matches = [table[REFERENCES[doctype][0]].like(_pattern(search))]
		if doctype == "CRM Deal":
			matches.extend([table.lead_name.like(_pattern(search)), table.organization_name.like(_pattern(search))])
			if (contacts := _reference_query("Contact", search)) is not None:
				links = frappe.qb.DocType("CRM Contacts")
				linked_deals = frappe.qb.from_(links).select(links.parent).where(
					(links.parenttype == "CRM Deal") & (links.is_primary == 1) & links.contact.isin(contacts))
				matches.append(table.name.isin(linked_deals))
		query = query.where(Criterion.any(matches))
	return query



def has_customer_reference(doc):
	# Old Call Logs may contain the schema's default Lead type with no customer.
	# Treat that exact legacy shape as unlinked without rewriting provider records.
	kind, name = getattr(doc, 'reference_doctype', None), getattr(doc, 'reference_docname', None)
	return bool(name or kind not in (None, '', 'CRM Lead'))


def unlinked_condition(table):
	return ((Coalesce(table.reference_doctype, '') == '') | (table.reference_doctype == 'CRM Lead')) & (Coalesce(table.reference_docname, '') == '')

def _base_query(fields=None):
	_check_read()
	table = frappe.qb.DocType("CRM Call Log")
	query = frappe.qb.get_query("CRM Call Log", fields=fields or ROW_FIELDS, ignore_permissions=False)
	# Apply context permissions in SQL before filtering, pagination and has_more.
	allowed = unlinked_condition(table)
	for doctype in REFERENCES:
		if (references := _reference_query(doctype)) is not None:
			allowed |= (table.reference_doctype == doctype) & table.reference_docname.isin(references)
	return query.where(allowed)


def _pattern(value):
	return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _search(value):
	value = str(value or "").strip()[:100]
	if re.fullmatch(r"[+\d\s().-]+", value):
		digits = re.sub(r"\D", "", value)
		return "7" + digits[1:] if len(digits) == 11 and digits.startswith("8") else digits
	return value


def _reference_labels(rows):
	result = {}
	for doctype, (title_field, route) in REFERENCES.items():
		names = list({row.reference_docname for row in rows if row.reference_doctype == doctype and row.reference_docname})
		if not names or not frappe.has_permission(doctype, "read"):
			continue
		for item in frappe.get_list(doctype, filters={"name": ["in", names]},
			fields=["name", title_field], limit_page_length=len(names)):
			result[(doctype, item.name)] = {
				"doctype": doctype, "name": item.name, "title": item.get(title_field) or item.name,
				"path": f"/crm/{route}/{quote(item.name, safe='')}",
			}
	# Resolve explicit primary contacts only, under their independent permissions.
	deal_names = [name for doctype, name in result if doctype == "CRM Deal"]
	if deal_names and frappe.has_permission("Contact", "read"):
		links = frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal", "parent": ["in", deal_names], "is_primary": 1}, fields=["parent", "contact"])
		contacts = {row.name: row.full_name for row in frappe.get_list("Contact",
			filters={"name": ["in", [link.contact for link in links]]}, fields=["name", "full_name"], limit_page_length=len(links) or 1)} if links else {}
		for link in links:
			if label := contacts.get(link.contact):
				result[("CRM Deal", link.parent)]["client_name"] = label
	return result


def _rows(rows):
	references = _reference_labels(rows)
	result = []
	for row in rows:
		reference = references.get((row.reference_doctype, row.reference_docname))
		incoming = row.type == "Incoming"
		result.append({
			"name": row.name, "type": row.type, "status": row.status,
			"duration": row.duration, "timestamp": row.start_time or row.creation,
			"number": row.get("from") if incoming else row.to,
			"line": row.to if incoming else row.get("from"),
			"agent": row.receiver if incoming else row.caller,
			"has_recording": bool(row.get("recording_url")),
			"recording_state": "ready" if row.get("recording_url") else "pending" if row.get("exolve_recording_state") == "pending" or row.status in {"Initiated","Ringing","In Progress","Queued"} else "unavailable",
			"reference": reference, "client_name": reference.get("client_name") or reference["title"] if reference else "",
		})
	from crm.api.call_followups import summary

	summary(result)
	return result


def filtered_query(search="", view="all", period="30", mine=0, employee="", line="", outcome="", fields=None):
	from crm.api.call_followups import OUTCOMES, due_calls, review_calls

	if (view not in {"all", "missed", "incoming", "outgoing", "recorded", "attention"}
		or str(period) not in {"all", "today", "7", "30"}
		or outcome not in ("", "unprocessed", *OUTCOMES)
		or not isinstance(employee, str) or len(employee) > 140
		or not isinstance(line, str) or len(line) > 100):
		frappe.throw(_("Invalid call filters."), frappe.ValidationError)
	query = _base_query(fields)
	table = frappe.qb.DocType("CRM Call Log")
	employee = frappe.session.user if cint(mine) else employee
	if view == "attention":
		missed = (table.type == "Incoming") & table.status.isin(MISSED_STATUSES) & table.name.notin(review_calls())
		if employee:
			missed &= table.receiver == employee
		query = query.where(missed | table.name.isin(due_calls(employee)))
	elif view == "missed":
		query = query.where((table.type == "Incoming") & table.status.isin(MISSED_STATUSES))
	elif view in {"incoming", "outgoing"}:
		query = query.where(table.type == ("Incoming" if view == "incoming" else "Outgoing"))
	elif view == "recorded":
		query = query.where(Coalesce(table.recording_url, "") != "")
	if employee and view != "attention":
		query = query.where(((table.type == "Incoming") & (table.receiver == employee)) | ((table.type == "Outgoing") & (table.caller == employee)))
	if line:
		query = query.where(((table.type == "Incoming") & (table.to == line)) | ((table.type == "Outgoing") & (table["from"] == line)))
	if outcome:
		query = query.where(table.name.notin(review_calls()) if outcome == "unprocessed" else table.name.isin(review_calls(outcome)))
	if str(period) != "all" and view != "attention":
		days = 0 if period == "today" else int(period) - 1
		query = query.where(Coalesce(table.start_time, table.creation) >= add_days(today(), -days))
	if search := _search(search):
		matches = [table["from"].like(_pattern(search)), table.to.like(_pattern(search))]
		for doctype in REFERENCES:
			if (references := _reference_query(doctype, search)) is not None:
				matches.append((table.reference_doctype == doctype) & table.reference_docname.isin(references))
		# Call permissions and customer permissions are already applied to the outer query.
		# Only raw ASR is searchable; manager notes and private drafts are untouched.
		if frappe.db.table_exists("CRM Call Analysis"):
			from crm.call_analysis.workspace import run_query
			ai = frappe.qb.DocType("CRM Call Analysis")
			matches.append(table.name.isin(run_query([ai.call_log]).where(ai.raw_transcript.like(_pattern(search)))))
		matches.append(table.ai_transcript.like(_pattern(search)))
		query = query.where(Criterion.any(matches))
	return query


@frappe.whitelist()
def get_calls(search="", view="all", period="30", mine=0, offset=0, page_length=40, employee="", line="", outcome=""):
	limit, offset = min(max(cint(page_length), 1), 100), max(cint(offset), 0)
	query = filtered_query(search, view, period, mine, employee, line, outcome)
	table = frappe.qb.DocType("CRM Call Log")
	query = query.orderby(Coalesce(table.start_time, table.creation), order=Order.desc).orderby(table.name, order=Order.desc)
	rows = query.offset(offset).limit(limit + 1).run(as_dict=True)
	return {"calls": _rows(rows[:limit]), "has_more": len(rows) > limit, "next_offset": offset + limit, "today": today(), "yesterday": add_days(today(), -1)}


@frappe.whitelist()
def get_filter_options():
	"""Only identities/lines present on the caller's permitted call set."""
	t = frappe.qb.DocType("CRM Call Log")
	rows = _base_query(["receiver", "to"]).where(t.type == "Incoming").distinct().run(as_dict=True)
	other = _base_query(["caller", "from"]).where(t.type == "Outgoing").distinct().run(as_dict=True)
	agents = sorted(({r.receiver for r in rows} | {r.caller for r in other}) - {None, ""})
	lines = sorted(({r.to for r in rows} | {r.get("from") for r in other}) - {None, ""})
	return {"employees": [{"value": u, "label": frappe.db.get_value("User", u, "full_name") or u} for u in agents], "lines": lines}


@frappe.whitelist()
def get_call(name):
	_check_read()
	doc = frappe.get_doc("CRM Call Log", name)
	doc.check_permission("read")
	if has_customer_reference(doc):
		if doc.reference_doctype not in REFERENCES or not doc.reference_docname or not frappe.has_permission(
			doc.reference_doctype, "read", doc.reference_docname
		):
			frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
	# Also reapply list/user permissions on direct links to a call.
	if not (rows := _base_query().where(frappe.qb.DocType("CRM Call Log").name == name).limit(1).run(as_dict=True)):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
	result = _rows(rows)[0]
	result["recording_path"] = (
		"/api/method/crm.integrations.api.get_recording_url?call_log_name=" + quote(doc.name, safe="")
		if result["has_recording"] else None
	)
	if result["has_recording"] and str(doc.recording_url).startswith(("/files/", "/private/files/")):
		result["recording_path"] = doc.recording_url
	# CRM references are independent documents, never inferred from a shared phone.
	references = [result["reference"]] if result["reference"] else []
	for link in doc.links:
		if link.link_doctype not in REFERENCES or not link.link_name:
			continue
		label = _reference_labels([frappe._dict(reference_doctype=link.link_doctype, reference_docname=link.link_name)])
		if item := label.get((link.link_doctype, link.link_name)):
			if item not in references:
				references.append(item)
	result["references"] = references
	result["has_conversation"] = bool(frappe.db.table_exists("CRM Call Work") and frappe.db.exists("CRM Call Work", {"user":frappe.session.user,"call_log":doc.name}))
	return result


@frappe.whitelist()
def search_customers(search):
	_check_read()
	search = _search(search)
	if len(search) < 2:
		return []
	result = []
	for doctype, (title_field, route) in REFERENCES.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		items = frappe.get_list(doctype,
			fields=["name", title_field, "mobile_no", "phone"],
			or_filters={title_field: ["like", _pattern(search)], "mobile_no": ["like", _pattern(search)], "phone": ["like", _pattern(search)]},
			order_by="modified desc, name desc", limit_page_length=5)
		for item in items:
			if number := item.get("mobile_no") or item.get("phone"):
				result.append({"doctype": doctype, "name": item.name, "title": item.get(title_field) or item.name,
					"number": number, "path": f"/crm/{route}/{quote(item.name, safe='')}"})
	return result[:15]
