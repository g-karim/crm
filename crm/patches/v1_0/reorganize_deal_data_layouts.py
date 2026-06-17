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
	set_fields_layout("CRM Deal-Data Fields", "Data Fields", DEAL_DATA_FIELDS_LAYOUT)
	set_fields_layout("CRM Deal-Side Panel", "Side Panel", DEAL_SIDE_PANEL_LAYOUT)


def set_fields_layout(name, layout_type, layout):
	layout_json = json.dumps(layout)

	if frappe.db.exists("CRM Fields Layout", name):
		frappe.db.set_value("CRM Fields Layout", name, "layout", layout_json)
		return

	doc = frappe.new_doc("CRM Fields Layout")
	doc.name = name
	doc.dt = "CRM Deal"
	doc.type = layout_type
	doc.layout = layout_json
	doc.insert()
