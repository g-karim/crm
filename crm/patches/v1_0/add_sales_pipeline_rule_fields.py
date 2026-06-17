import frappe


def execute():
	frappe.reload_doc("fcrm", "doctype", "crm_sales_pipeline")
