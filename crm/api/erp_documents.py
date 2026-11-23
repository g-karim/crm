"""Optional local ERP document integration; CRM remains usable without ru_erp."""

import frappe


@frappe.whitelist()
def capabilities():
	return {"enabled": "ru_erp" in frappe.get_installed_apps()}


def require_app():
	if not capabilities()["enabled"]:
		frappe.throw("Российский контур ERP не установлен")


@frappe.whitelist()
def get_deal_documents(deal):
	if not capabilities()["enabled"]:
		return {"enabled": False}
	from ru_erp.crm import deal_documents

	return deal_documents(deal)


@frappe.whitelist()
def document_route(deal, doctype, source_doctype=None, source_name=None):
	require_app()
	from ru_erp.crm import document_route as route

	return route(deal, doctype, source_doctype, source_name)


@frappe.whitelist()
def set_seller(deal, company):
	require_app()
	from ru_erp.crm import set_seller as save

	return save(deal, company)
