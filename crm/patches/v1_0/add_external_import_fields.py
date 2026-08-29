import frappe

from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_default_pipeline


def execute():
	frappe.reload_doc("fcrm", "doctype", "crm_sales_pipeline")
	frappe.reload_doc("fcrm", "doctype", "crm_deal_status")
	frappe.reload_doc("fcrm", "doctype", "crm_deal")

	get_default_pipeline()
