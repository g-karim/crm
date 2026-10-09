"""CRM-only export parity. Other views keep the native framework endpoint."""

import json

import frappe
from frappe.desk import reportview
from frappe.model import get_permitted_fields
from frappe.utils import cint

from crm import touch_tracking as touch
from crm.list_settings import normalize_phone_filters
from crm.touch_tracking_ui import list_records


@frappe.whitelist()
@frappe.read_only()
def export_query():
	params = reportview.get_form_params()
	doctype = params.get("doctype")
	parts = [part.strip().split() for part in (params.get("order_by") or "").split(",")]
	if doctype not in touch.TARGETS or not any(part and part[0] == touch.FIELD for part in parts):
		return reportview.export_query()
	if params.get("export_in_background") or params.get("group_by") or params.get("or_filters"):
		frappe.throw(frappe._("Unsupported CRM export parameters"))
	permitted = set(get_permitted_fields(doctype))
	fields = list(params.get("fields") or [])
	# CRM columns are direct fields. Never accept arbitrary SQL/joins from the URL.
	if any(not isinstance(field, str) or field not in permitted for field in fields):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	fields = list(dict.fromkeys([*fields, "owner"]))
	filters = params.get("filters") or {}
	if params.get("selected_items"):
		selected = frappe.parse_json(params.selected_items)
		if not isinstance(selected, list) or any(not isinstance(name, str) for name in selected):
			frappe.throw(frappe._("Invalid CRM export selection"))
		# Selection intersects the current filters; it does not replace them.
		if isinstance(filters, dict):
			filters = [
				[key, *(value if isinstance(value, list) else ["=", value])] for key, value in filters.items()
			]
		filters = [*filters, ["name", "in", selected]]
	filters = normalize_phone_filters(doctype, filters)
	query_fields = list(dict.fromkeys([*fields, "creation"]))
	data = list_records(
		doctype,
		fields=query_fields,
		filters=filters,
		order_by=params.order_by,
		page_length=cint(params.page_length) or None,
		start=cint(params.start),
	)
	if not frappe.permissions.can_export(doctype):
		if not frappe.permissions.can_export(doctype, is_owner=True) or any(
			row.owner != frappe.session.user for row in data
		):
			frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	for row in data:
		if touch.FIELD in fields:
			row[touch.FIELD] = row.get(touch.FIELD) or row.creation
	info = reportview.get_field_info(fields, doctype)
	values = [[frappe._("Sr"), *[field["label"] for field in info]]]
	for index, row in enumerate(data, 1):
		values.append(
			[
				index,
				*[
					frappe._(row[field])
					if params.get("translate_values") == "1" and meta["translatable"]
					else row.get(field)
					for field, meta in zip(fields, info, strict=True)
				],
			]
		)
	values = reportview.handle_duration_fieldtype_values(doctype, values, fields)
	from frappe.core.doctype.access_log.access_log import make_access_log
	from frappe.desk.utils import get_csv_bytes, pop_csv_params, provide_binary_file
	from frappe.utils.xlsxutils import get_default_xlsx_styles, handle_html, make_xlsx

	file_type = params.get("file_format_type") or "Excel"
	title = params.get("title") or doctype
	if file_type == "CSV":
		content = get_csv_bytes(
			[[handle_html(value) if isinstance(value, str) else value for value in row] for row in values],
			pop_csv_params(params),
		)
		extension = "csv"
	elif file_type == "Excel":
		styles = get_default_xlsx_styles(
			columns=[{"fieldname": "sr", "label": frappe._("Sr"), "fieldtype": "Int"}, *info],
			data=values[1:],
			has_total_row=False,
		)
		content = make_xlsx(values, doctype, styles=styles).getvalue()
		extension = "xlsx"
	else:
		frappe.throw(frappe._("Unsupported CRM export format"))
	make_access_log(
		doctype=doctype,
		file_type=file_type,
		report_name=title,
		filters=json.dumps(params.get("filters"), default=str),
	)
	provide_binary_file(frappe._(title), extension, content)
