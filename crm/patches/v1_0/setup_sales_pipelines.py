import frappe

from crm.install import ensure_sales_pipeline_fields_layouts
from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_or_create_default_pipeline


def execute():
	frappe.reload_doc("fcrm", "doctype", "crm_sales_pipeline")
	frappe.reload_doc("fcrm", "doctype", "crm_deal_status")
	frappe.reload_doc("fcrm", "doctype", "crm_deal")
	frappe.reload_doc("fcrm", "doctype", "crm_lead")

	default_pipeline = get_or_create_default_pipeline()

	for status in frappe.get_all("CRM Deal Status", filters={"pipeline": ["is", "not set"]}, pluck="name"):
		frappe.db.set_value(
			"CRM Deal Status",
			status,
			"pipeline",
			default_pipeline,
			update_modified=False,
		)

	for deal in frappe.get_all("CRM Deal", filters={"pipeline": ["is", "not set"]}, pluck="name"):
		frappe.db.set_value(
			"CRM Deal",
			deal,
			"pipeline",
			default_pipeline,
			update_modified=False,
		)

	ensure_sales_pipeline_fields_layouts()
