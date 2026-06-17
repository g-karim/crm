import json

import frappe


DEAL_DATA_FIELDS_LAYOUT = [
	{
		"label": "Overview",
		"name": "overview_tab",
		"sections": [
			{
				"label": "Deal",
				"name": "deal_section",
				"opened": True,
				"columns": [
					{"name": "deal_main_column", "fields": ["deal_name", "pipeline", "source"]},
					{"name": "deal_owner_column", "fields": ["deal_owner", "next_step"]},
				],
			},
			{
				"label": "Customer",
				"name": "customer_section",
				"opened": True,
				"columns": [
					{"name": "customer_contact_column", "fields": ["email", "mobile_no", "phone"]},
					{
						"name": "customer_org_column",
						"fields": ["organization", "website", "territory", "annual_revenue"],
					},
				],
			},
		],
	},
	{
		"label": "Forecast",
		"name": "forecast_tab",
		"sections": [
			{
				"label": "Forecast & Value",
				"name": "forecast_section",
				"opened": True,
				"columns": [
					{"name": "forecast_money_column", "fields": ["deal_value", "expected_deal_value", "currency"]},
					{
						"name": "forecast_timing_column",
						"fields": ["probability", "expected_closure_date", "closed_date"],
					},
				],
			}
		],
	},
	{
		"label": "Products",
		"name": "products_tab",
		"sections": [
			{
				"label": "Products",
				"name": "products_section",
				"opened": True,
				"columns": [{"name": "products_column", "fields": ["products"]}],
				"hideLabel": True,
			},
			{
				"label": "Totals",
				"name": "totals_section",
				"opened": True,
				"columns": [{"name": "totals_amounts_column", "fields": ["total", "net_total"]}],
			},
		],
	},
]

DEAL_SIDE_PANEL_LAYOUT = [
	{"label": "Contacts", "name": "contacts_section", "opened": True, "editable": False, "contacts": []},
	{
		"label": "Deal Summary",
		"name": "deal_summary_section",
		"opened": True,
		"columns": [
			{
				"name": "deal_summary_column",
				"fields": [
					"deal_name",
					"pipeline",
					"status",
					"source",
					"deal_value",
					"probability",
					"next_step",
					"deal_owner",
				],
			}
		],
	},
	{
		"label": "Customer",
		"name": "customer_section",
		"opened": True,
		"columns": [
			{
				"name": "customer_column",
				"fields": ["organization", "website", "territory", "annual_revenue"],
			}
		],
	},
	{
		"label": "Forecast",
		"name": "forecast_section",
		"opened": False,
		"columns": [
			{
				"name": "forecast_column",
				"fields": ["expected_deal_value", "expected_closure_date", "closed_date", "currency"],
			}
		],
	},
]


def execute():
	ensure_fields_layout("CRM Deal-Data Fields", "Data Fields", DEAL_DATA_FIELDS_LAYOUT)
	ensure_fields_layout("CRM Deal-Side Panel", "Side Panel", DEAL_SIDE_PANEL_LAYOUT)
	ensure_deal_pipeline_fields()


def ensure_fields_layout(name, layout_type, layout):
	if frappe.db.exists("CRM Fields Layout", name):
		return

	layout_json = json.dumps(layout)

	doc = frappe.new_doc("CRM Fields Layout")
	doc.name = name
	doc.dt = "CRM Deal"
	doc.type = layout_type
	doc.layout = layout_json
	doc.insert()


def ensure_deal_pipeline_fields():
	ensure_layout_fields(
		"CRM Deal-Data Fields",
		["deal_section", "details_section", "organization_section"],
		[
			{"fieldname": "deal_name", "reference_field": "source", "before": True},
			{"fieldname": "pipeline", "reference_field": "source", "before": True},
			{"fieldname": "status", "reference_field": "source", "before": True},
		],
	)
	ensure_layout_fields(
		"CRM Deal-Side Panel",
		["deal_summary_section", "organization_section", "details_section"],
		[
			{"fieldname": "deal_name", "reference_field": "source", "before": True},
			{"fieldname": "pipeline", "reference_field": "source", "before": True},
			{"fieldname": "status", "reference_field": "source", "before": True},
		],
	)


def ensure_layout_fields(layout_name, preferred_sections, fields):
	if not frappe.db.exists("CRM Fields Layout", layout_name):
		return

	doc = frappe.get_doc("CRM Fields Layout", layout_name)
	try:
		layout = json.loads(doc.layout or "[]")
	except ValueError:
		return

	if not isinstance(layout, list):
		return

	changed = False
	for field in fields:
		if layout_has_field(layout, field["fieldname"]):
			continue

		section = find_target_section(layout, preferred_sections)
		if not section or not section.get("columns"):
			continue

		insert_field_in_section(
			section,
			field["fieldname"],
			field.get("reference_field"),
			field.get("before", False),
		)
		changed = True

	if changed:
		doc.layout = json.dumps(layout)
		doc.save(ignore_permissions=True)


def insert_field_in_section(section, fieldname, reference_field=None, before=False):
	target_column = section["columns"][0]
	if reference_field:
		target_column = next(
			(
				column
				for column in section["columns"]
				if reference_field in (column.get("fields") or [])
			),
			target_column,
		)

	fields = target_column.setdefault("fields", [])
	if reference_field in fields:
		index = fields.index(reference_field)
		if not before:
			index += 1
		fields.insert(index, fieldname)
	else:
		fields.append(fieldname)


def layout_has_field(layout, fieldname):
	return any(
		fieldname in (column.get("fields") or [])
		for section in iter_layout_sections(layout)
		for column in section.get("columns", [])
	)


def find_target_section(layout, preferred_sections):
	for section_name in preferred_sections:
		section = next(
			(section for section in iter_layout_sections(layout) if section.get("name") == section_name),
			None,
		)
		if section and section.get("columns"):
			return section

	return next(
		(section for section in iter_layout_sections(layout) if section.get("columns")),
		None,
	)


def iter_layout_sections(layout):
	for item in layout:
		if item.get("sections"):
			for section in item.get("sections") or []:
				yield section
		else:
			yield item
