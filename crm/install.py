# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
import json

import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from crm.branding import ensure_crm_branding_defaults
from crm.desk import hide_legacy_erpnext_crm
from crm.dropdown import ensure_crm_dropdown_items
from crm.fcrm.doctype.crm_dashboard.crm_dashboard import create_default_manager_dashboard
from crm.fcrm.doctype.crm_products.crm_products import create_product_details_script
from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import (
	get_default_deal_stage_label,
	get_or_create_default_pipeline,
)


def before_install():
	pass


def after_install(force=False):
	add_default_lead_statuses()
	add_default_sales_pipeline()
	add_default_deal_statuses()
	add_default_communication_statuses()
	add_default_fields_layout(force)
	ensure_sales_pipeline_fields_layouts()
	add_property_setter()
	add_email_template_custom_fields()
	add_email_account_custom_field()
	add_default_industries()
	add_default_lead_sources()
	add_default_lost_reasons()
	add_default_quick_filters()
	add_standard_dropdown_items()
	ensure_crm_dropdown_items()
	hide_legacy_erpnext_crm()
	add_default_scripts()
	create_default_manager_dashboard(force)
	create_assignment_rule_custom_fields()
	add_assignment_rule_property_setters()
	ensure_crm_branding_defaults()
	frappe.db.commit()


def add_default_lead_statuses():
	statuses = {
		"New": {
			"color": "gray",
			"type": "Open",
			"position": 1,
		},
		"Contacted": {
			"color": "orange",
			"type": "Ongoing",
			"position": 2,
		},
		"Nurture": {
			"color": "blue",
			"type": "Ongoing",
			"position": 3,
		},
		"Qualified": {
			"color": "green",
			"type": "Won",
			"position": 4,
		},
		"Converted": {
			"color": "teal",
			"type": "Won",
			"position": 5,
		},
		"Unqualified": {
			"color": "red",
			"type": "Lost",
			"position": 6,
		},
		"Junk": {
			"color": "purple",
			"type": "Lost",
			"position": 7,
		},
	}

	for status in statuses:
		if frappe.db.exists("CRM Lead Status", status):
			continue

		doc = frappe.new_doc("CRM Lead Status")
		doc.lead_status = status
		doc.color = statuses[status]["color"]
		doc.type = statuses[status]["type"]
		doc.position = statuses[status]["position"]
		doc.insert()


def add_default_sales_pipeline():
	get_or_create_default_pipeline()


def add_default_deal_statuses():
	default_pipeline = get_or_create_default_pipeline()
	statuses = {
		"Qualification": {
			"color": "gray",
			"type": "Open",
			"probability": 10,
			"position": 1,
		},
		"Demo/Making": {
			"color": "orange",
			"type": "Ongoing",
			"probability": 25,
			"position": 2,
		},
		"Proposal/Quotation": {
			"color": "blue",
			"type": "Ongoing",
			"probability": 50,
			"position": 3,
		},
		"Negotiation": {
			"color": "yellow",
			"type": "Ongoing",
			"probability": 70,
			"position": 4,
		},
		"Ready to Close": {
			"color": "purple",
			"type": "Ongoing",
			"probability": 90,
			"position": 5,
		},
		"Won": {
			"color": "green",
			"type": "Won",
			"probability": 100,
			"position": 6,
		},
		"Lost": {
			"color": "red",
			"type": "Lost",
			"probability": 0,
			"position": 7,
		},
	}

	for status, config in statuses.items():
		stage_label = get_default_deal_stage_label(status)
		existing = (
			frappe.db.exists(
				"CRM Deal Status",
				{"deal_status": stage_label, "pipeline": default_pipeline},
			)
			or frappe.db.exists(
				"CRM Deal Status",
				{"deal_status": status, "pipeline": default_pipeline},
			)
			or frappe.db.exists("CRM Deal Status", stage_label)
			or frappe.db.exists("CRM Deal Status", status)
		)
		if existing:
			if not frappe.db.get_value("CRM Deal Status", existing, "pipeline"):
				frappe.db.set_value("CRM Deal Status", existing, "pipeline", default_pipeline)
			continue

		doc = frappe.new_doc("CRM Deal Status")
		doc.name = stage_label
		doc.deal_status = stage_label
		doc.pipeline = default_pipeline
		doc.color = config["color"]
		doc.type = config["type"]
		doc.probability = config["probability"]
		doc.position = config["position"]
		doc.insert()


def add_default_communication_statuses():
	statuses = ["Open", "Replied"]

	for status in statuses:
		if frappe.db.exists("CRM Communication Status", status):
			continue

		doc = frappe.new_doc("CRM Communication Status")
		doc.status = status
		doc.insert()


def add_default_fields_layout(force=False):
	quick_entry_layouts = {
		"CRM Lead-Quick Entry": {
			"doctype": "CRM Lead",
			"layout": '[{"name": "person_section", "columns": [{"name": "column_5jrk", "fields": ["salutation", "email"]}, {"name": "column_5CPV", "fields": ["first_name", "mobile_no"]}, {"name": "column_gXOy", "fields": ["last_name", "gender"]}]}, {"name": "organization_section", "columns": [{"name": "column_GHfX", "fields": ["organization", "territory"]}, {"name": "column_hXjS", "fields": ["website", "annual_revenue"]}, {"name": "column_RDNA", "fields": ["no_of_employees", "industry"]}]}, {"name": "lead_section", "columns": [{"name": "column_EO1H", "fields": ["status"]}, {"name": "column_RWBe", "fields": ["lead_owner"]}]}]',
		},
		"CRM Deal-Quick Entry": {
			"doctype": "CRM Deal",
			"layout": '[{"name": "organization_section", "hidden": true, "editable": false, "columns": [{"name": "column_GpMP", "fields": ["organization"]}, {"name": "column_FPTn", "fields": []}]}, {"name": "organization_details_section", "editable": false, "columns": [{"name": "column_S3tQ", "fields": ["organization_name", "territory"]}, {"name": "column_KqV1", "fields": ["website", "annual_revenue"]}, {"name": "column_1r67", "fields": ["no_of_employees", "industry"]}]}, {"name": "contact_section", "hidden": true, "editable": false, "columns": [{"name": "column_CeXr", "fields": ["contact"]}, {"name": "column_yHbk", "fields": []}]}, {"name": "contact_details_section", "editable": false, "columns": [{"name": "column_ZTWr", "fields": ["salutation", "email"]}, {"name": "column_tabr", "fields": ["first_name", "mobile_no"]}, {"name": "column_Qjdx", "fields": ["last_name", "gender"]}]}, {"name": "deal_section", "columns": [{"name": "column_mdps", "fields": ["deal_name", "pipeline", "status"]}, {"name": "column_H40H", "fields": ["deal_owner"]}]}]',
		},
		"Contact-Quick Entry": {
			"doctype": "Contact",
			"layout": '[{"name": "salutation_section", "columns": [{"name": "column_eXks", "fields": ["salutation"]}]}, {"name": "full_name_section", "hideBorder": true, "columns": [{"name": "column_cSxf", "fields": ["first_name"]}, {"name": "column_yBc7", "fields": ["last_name"]}]}, {"name": "email_section", "hideBorder": true, "columns": [{"name": "column_tH3L", "fields": ["email_id"]}]}, {"name": "mobile_gender_section", "hideBorder": true, "columns": [{"name": "column_lrfI", "fields": ["mobile_no"]}, {"name": "column_Tx3n", "fields": ["gender"]}]}, {"name": "organization_section", "hideBorder": true, "columns": [{"name": "column_S0J8", "fields": ["company_name"]}]}, {"name": "designation_section", "hideBorder": true, "columns": [{"name": "column_bsO8", "fields": ["designation"]}]}, {"name": "address_section", "hideBorder": true, "columns": [{"name": "column_W3VY", "fields": ["address"]}]}]',
		},
		"CRM Organization-Quick Entry": {
			"doctype": "CRM Organization",
			"layout": '[{"name": "organization_section", "columns": [{"name": "column_zOuv", "fields": ["organization_name"]}]}, {"name": "website_revenue_section", "hideBorder": true, "columns": [{"name": "column_I5Dy", "fields": ["website"]}, {"name": "column_Rgss", "fields": ["annual_revenue"]}]}, {"name": "territory_section", "hideBorder": true, "columns": [{"name": "column_w6ap", "fields": ["territory"]}]}, {"name": "employee_industry_section", "hideBorder": true, "columns": [{"name": "column_u5tZ", "fields": ["no_of_employees"]}, {"name": "column_FFrT", "fields": ["industry"]}]}, {"name": "address_section", "hideBorder": true, "columns": [{"name": "column_O2dk", "fields": ["address"]}]}]',
		},
		"Address-Quick Entry": {
			"doctype": "Address",
			"layout": '[{"name": "details_section", "columns": [{"name": "column_uSSG", "fields": ["address_title", "address_type", "address_line1", "address_line2", "city", "state", "country", "pincode"]}]}]',
		},
		"CRM Call Log-Quick Entry": {
			"doctype": "CRM Call Log",
			"layout": '[{"name":"details_section","columns":[{"name":"column_uMSG","fields":["type","from","duration"]},{"name":"column_wiZT","fields":["to","status","caller","receiver"]}]}]',
		},
		"FCRM Note-Quick Entry": {
			"doctype": "FCRM Note",
			"layout": '[{"name":"details_section","columns":[{"name":"column_o2s9","fields":["title", "content"]}]}]',
		},
		"CRM Task-Quick Entry": {
			"doctype": "CRM Task",
			"layout": '[{"name":"first_tab","sections":[{"name":"details_section","columns":[{"name":"column_X9sG","fields":["title","description"]}]},{"name":"assignment_section","columns":[{"name":"column_9XjK","fields":["priority","due_date"]},{"name":"column_7s8n","fields":["assigned_to","status"]}],"hideBorder":true}]}]',
		},
	}

	deal_side_panel_layout = [
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

	sidebar_fields_layouts = {
		"CRM Lead-Side Panel": {
			"doctype": "CRM Lead",
			"layout": '[{"label": "Details", "name": "details_section", "opened": true, "columns": [{"name": "column_kl92", "fields": ["organization", "website", "territory", "industry", "job_title", "source", "lead_owner"]}]}, {"label": "Person", "name": "person_section", "opened": true, "columns": [{"name": "column_XmW2", "fields": ["salutation", "first_name", "last_name", "email", "mobile_no"]}]}]',
		},
		"CRM Deal-Side Panel": {
			"doctype": "CRM Deal",
			"layout": json.dumps(deal_side_panel_layout),
		},
		"Contact-Side Panel": {
			"doctype": "Contact",
			"layout": '[{"label": "Details", "name": "details_section", "opened": true, "columns": [{"name": "column_eIWl", "fields": ["salutation", "first_name", "last_name", "email_id", "mobile_no", "gender", "company_name", "designation", "address"]}]}]',
		},
		"CRM Organization-Side Panel": {
			"doctype": "CRM Organization",
			"layout": '[{"label": "Details", "name": "details_section", "opened": true, "columns": [{"name": "column_IJOV", "fields": ["organization_name", "website", "territory", "industry", "no_of_employees", "address"]}]}]',
		},
	}

	deal_data_fields_layout = [
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
						{
							"name": "forecast_money_column",
							"fields": ["deal_value", "expected_deal_value", "currency"],
						},
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

	data_fields_layouts = {
		"CRM Lead-Data Fields": {
			"doctype": "CRM Lead",
			"layout": '[{"label": "Details", "name": "details_section", "opened": true, "columns": [{"name": "column_ZgLG", "fields": ["organization", "industry", "lead_owner"]}, {"name": "column_TbYq", "fields": ["website", "job_title"]}, {"name": "column_OKSX", "fields": ["territory", "source"]}]}, {"label": "Person", "name": "person_section", "opened": true, "columns": [{"name": "column_6c5g", "fields": ["salutation", "email"]}, {"name": "column_1n7Q", "fields": ["first_name", "mobile_no"]}, {"name": "column_cT6C", "fields": ["last_name"]}]}]',
		},
		"CRM Deal-Data Fields": {
			"doctype": "CRM Deal",
			"layout": json.dumps(deal_data_fields_layout),
		},
	}

	for layout in quick_entry_layouts:
		if frappe.db.exists("CRM Fields Layout", layout):
			if force:
				frappe.delete_doc("CRM Fields Layout", layout)
			else:
				continue

		doc = frappe.new_doc("CRM Fields Layout")
		doc.type = "Quick Entry"
		doc.dt = quick_entry_layouts[layout]["doctype"]
		doc.layout = quick_entry_layouts[layout]["layout"]
		doc.insert()

	for layout in sidebar_fields_layouts:
		if frappe.db.exists("CRM Fields Layout", layout):
			if force:
				frappe.delete_doc("CRM Fields Layout", layout)
			else:
				continue

		doc = frappe.new_doc("CRM Fields Layout")
		doc.type = "Side Panel"
		doc.dt = sidebar_fields_layouts[layout]["doctype"]
		doc.layout = sidebar_fields_layouts[layout]["layout"]
		doc.insert()

	for layout in data_fields_layouts:
		if frappe.db.exists("CRM Fields Layout", layout):
			if force:
				frappe.delete_doc("CRM Fields Layout", layout)
			else:
				continue

		doc = frappe.new_doc("CRM Fields Layout")
		doc.type = "Data Fields"
		doc.dt = data_fields_layouts[layout]["doctype"]
		doc.layout = data_fields_layouts[layout]["layout"]
		doc.insert()


def ensure_sales_pipeline_fields_layouts():
	layout_fields = [
		{
			"layout": "CRM Lead-Quick Entry",
			"section": "lead_section",
			"field": "planned_deal_pipeline",
			"reference": "status",
		},
		{
			"layout": "CRM Lead-Side Panel",
			"section": "details_section",
			"field": "planned_deal_pipeline",
			"reference": "source",
		},
		{
			"layout": "CRM Lead-Data Fields",
			"section": "details_section",
			"field": "planned_deal_pipeline",
			"reference": "lead_owner",
			"before": True,
		},
		{
			"layout": "CRM Deal-Quick Entry",
			"section": "deal_section",
			"field": "deal_name",
			"reference": "pipeline",
			"before": True,
		},
		{
			"layout": "CRM Deal-Quick Entry",
			"section": "deal_section",
			"field": "pipeline",
			"reference": "status",
			"before": True,
		},
		{
			"layout": "CRM Deal-Side Panel",
			"section": "organization_section",
			"field": "deal_name",
			"reference": "organization",
			"before": True,
		},
		{
			"layout": "CRM Deal-Side Panel",
			"section": "organization_section",
			"field": "pipeline",
			"reference": "organization",
		},
		{
			"layout": "CRM Deal-Data Fields",
			"section": "details_section",
			"field": "deal_name",
			"reference": "organization",
			"before": True,
		},
		{
			"layout": "CRM Deal-Data Fields",
			"section": "details_section",
			"field": "pipeline",
			"reference": "organization",
		},
	]

	for field in layout_fields:
		add_field_to_fields_layout(
			field["layout"],
			field["section"],
			field["field"],
			field.get("reference"),
			field.get("before", False),
		)


def add_field_to_fields_layout(layout_name, section_name, fieldname, reference_field=None, before=False):
	if not frappe.db.exists("CRM Fields Layout", layout_name):
		return

	doc = frappe.get_doc("CRM Fields Layout", layout_name)
	layout = json.loads(doc.layout or "[]")

	if layout_has_field(layout, fieldname):
		return

	section = find_layout_section(layout, section_name)
	if not section or not section.get("columns"):
		return

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

	doc.layout = json.dumps(layout)
	doc.save(ignore_permissions=True)


def layout_has_field(layout, fieldname):
	return any(
		fieldname in (column.get("fields") or [])
		for section in iter_layout_sections(layout)
		for column in section.get("columns", [])
	)


def find_layout_section(layout, section_name):
	return next(
		(section for section in iter_layout_sections(layout) if section.get("name") == section_name),
		None,
	)


def iter_layout_sections(layout):
	for item in layout:
		if item.get("sections"):
			for section in item.get("sections") or []:
				yield section
		else:
			yield item


def add_property_setter():
	if not frappe.db.exists("Property Setter", {"name": "Contact-main-search_fields"}):
		doc = frappe.new_doc("Property Setter")
		doc.doctype_or_field = "DocType"
		doc.doc_type = "Contact"
		doc.property = "search_fields"
		doc.property_type = "Data"
		doc.value = "email_id"
		doc.insert()


def add_email_template_custom_fields():
	meta = frappe.get_meta("Email Template")

	fields = [
		{
			"default": "0",
			"fieldname": "enabled",
			"fieldtype": "Check",
			"label": "Enabled",
			"insert_after": "",
		},
		{
			"fieldname": "reference_doctype",
			"fieldtype": "Link",
			"label": "Doctype",
			"options": "DocType",
			"insert_after": "enabled",
		},
	]

	fields = [field for field in fields if not meta.has_field(field["fieldname"])]
	if not fields:
		return

	click.secho("* Installing Custom Fields in Email Template")
	create_custom_fields({"Email Template": fields})
	frappe.clear_cache(doctype="Email Template")


def add_email_account_custom_field():
	if not frappe.get_meta("Email Account").has_field("create_lead_from_incoming_email"):
		click.secho("* Installing Custom Fields in Email Account")

		create_custom_fields(
			{
				"Email Account": [
					{
						"default": "0",
						"fieldname": "create_lead_from_incoming_email",
						"fieldtype": "Check",
						"label": "Create Lead from Incoming Emails",
						"description": "Automatically create a lead when an incoming email is received from an unknown contact",
						"insert_after": "create_contact",
					}
				]
			}
		)

		frappe.clear_cache(doctype="Email Account")


def add_default_industries():
	industries = [
		"Accounting",
		"Advertising",
		"Aerospace",
		"Agriculture",
		"Airline",
		"Apparel & Accessories",
		"Automotive",
		"Banking",
		"Biotechnology",
		"Broadcasting",
		"Brokerage",
		"Chemical",
		"Computer",
		"Consulting",
		"Consumer Products",
		"Cosmetics",
		"Defense",
		"Department Stores",
		"Education",
		"Electronics",
		"Energy",
		"Entertainment & Leisure, Executive Search",
		"Financial Services",
		"Food",
		"Beverage & Tobacco",
		"Grocery",
		"Health Care",
		"Internet Publishing",
		"Investment Banking",
		"Legal",
		"Manufacturing",
		"Motion Picture & Video",
		"Music",
		"Newspaper Publishers",
		"Online Auctions",
		"Pension Funds",
		"Pharmaceuticals",
		"Private Equity",
		"Publishing",
		"Real Estate",
		"Retail & Wholesale",
		"Securities & Commodity Exchanges",
		"Service",
		"Soap & Detergent",
		"Software",
		"Sports",
		"Technology",
		"Telecommunications",
		"Television",
		"Transportation",
		"Venture Capital",
	]

	for industry in industries:
		if frappe.db.exists("CRM Industry", industry):
			continue

		doc = frappe.new_doc("CRM Industry")
		doc.industry = industry
		doc.insert()


def add_default_lead_sources():
	lead_sources = [
		"Email",
		"Existing Customer",
		"Reference",
		"Advertisement",
		"Cold Calling",
		"Exhibition",
		"Supplier Reference",
		"Mass Mailing",
		"Customer's Vendor",
		"Campaign",
		"Walk In",
		"Facebook",
		"Website",
	]

	for source in lead_sources:
		if frappe.db.exists("CRM Lead Source", source):
			continue

		doc = frappe.new_doc("CRM Lead Source")
		doc.source_name = source
		doc.insert()


def add_default_lost_reasons():
	lost_reasons = [
		{
			"reason": "Pricing",
			"description": "The prospect found the pricing to be too high or not competitive.",
		},
		{"reason": "Competition", "description": "The prospect chose a competitor's product or service."},
		{
			"reason": "Budget Constraints",
			"description": "The prospect did not have the budget to proceed with the purchase.",
		},
		{
			"reason": "Missing Features",
			"description": "The prospect felt that the product or service was missing key features they needed.",
		},
		{
			"reason": "Long Sales Cycle",
			"description": "The sales process took too long, leading to loss of interest.",
		},
		{
			"reason": "No Decision-Maker",
			"description": "The prospect was not the decision-maker and could not proceed.",
		},
		{"reason": "Unresponsive Prospect", "description": "The prospect did not respond to follow-ups."},
		{"reason": "Poor Fit", "description": "The prospect was not a good fit for the product or service."},
		{"reason": "Other", "description": ""},
	]

	for reason in lost_reasons:
		if frappe.db.exists("CRM Lost Reason", reason["reason"]):
			continue

		doc = frappe.new_doc("CRM Lost Reason")
		doc.lost_reason = reason["reason"]
		doc.description = reason["description"]
		doc.insert()


def add_default_quick_filters():
	quick_filters = {
		"CRM Lead": ["lead_name", "email", "organization", "status", "source"],
		"CRM Deal": ["organization", "status", "probability", "email"],
		"Contact": ["status", "email_id", "phone"],
		"CRM Organization": ["organization_name", "no_of_employees", "territory", "industry"],
		"CRM Task": ["title", "priority", "assigned_to", "status", "due_date"],
		"CRM Call Log": ["telephony_medium", "type", "status", "from", "to"],
	}

	for quick_filter in quick_filters:
		if frappe.db.exists("CRM Global Settings", {"dt": quick_filter}):
			continue

		doc = frappe.new_doc("CRM Global Settings")
		doc.dt = quick_filter
		doc.json = json.dumps(quick_filters[quick_filter])
		doc.insert()


def add_standard_dropdown_items():
	crm_settings = frappe.get_single("FCRM Settings")

	# don't add dropdown items if they're already present
	if crm_settings.dropdown_items:
		return

	crm_settings.dropdown_items = []

	for item in frappe.get_hooks("standard_dropdown_items"):
		crm_settings.append("dropdown_items", item)

	crm_settings.save()


def add_default_scripts():
	from crm.fcrm.doctype.fcrm_settings.fcrm_settings import create_forecasting_script

	for doctype in ["CRM Lead", "CRM Deal"]:
		create_product_details_script(doctype)
	create_forecasting_script()


def add_assignment_rule_property_setters():
	"""Add a property setter to the Assignment Rule DocType for assign_condition and unassign_condition."""

	default_fields = {
		"doctype": "Property Setter",
		"doctype_or_field": "DocField",
		"doc_type": "Assignment Rule",
		"property_type": "Data",
		"is_system_generated": 1,
	}

	if not frappe.db.exists("Property Setter", {"name": "Assignment Rule-assign_condition-depends_on"}):
		frappe.get_doc(
			{
				**default_fields,
				"name": "Assignment Rule-assign_condition-depends_on",
				"field_name": "assign_condition",
				"property": "depends_on",
				"value": "eval: !doc.assign_condition_json",
			}
		).insert()
	else:
		frappe.db.set_value(
			"Property Setter",
			{"name": "Assignment Rule-assign_condition-depends_on"},
			"value",
			"eval: !doc.assign_condition_json",
		)
	if not frappe.db.exists("Property Setter", {"name": "Assignment Rule-unassign_condition-depends_on"}):
		frappe.get_doc(
			{
				**default_fields,
				"name": "Assignment Rule-unassign_condition-depends_on",
				"field_name": "unassign_condition",
				"property": "depends_on",
				"value": "eval: !doc.unassign_condition_json",
			}
		).insert()
	else:
		frappe.db.set_value(
			"Property Setter",
			{"name": "Assignment Rule-unassign_condition-depends_on"},
			"value",
			"eval: !doc.unassign_condition_json",
		)


def create_assignment_rule_custom_fields():
	if not frappe.get_meta("Assignment Rule").has_field("assign_condition_json"):
		click.secho("* Installing Custom Fields in Assignment Rule")

		create_custom_fields(
			{
				"Assignment Rule": [
					{
						"description": "Autogenerated field by CRM App",
						"fieldname": "assign_condition_json",
						"fieldtype": "Code",
						"label": "Assign Condition JSON",
						"insert_after": "assign_condition",
						"depends_on": "eval: doc.assign_condition_json",
					},
					{
						"description": "Autogenerated field by CRM App",
						"fieldname": "unassign_condition_json",
						"fieldtype": "Code",
						"label": "Unassign Condition JSON",
						"insert_after": "unassign_condition",
						"depends_on": "eval: doc.unassign_condition_json",
					},
				],
			}
		)

		frappe.clear_cache(doctype="Assignment Rule")
