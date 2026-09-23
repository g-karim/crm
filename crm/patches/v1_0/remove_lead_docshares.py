import frappe


def execute():
	# Frappe combines DocShare with permission query conditions using OR.
	# Old shares would otherwise keep revoked Leads in list responses.
	frappe.db.delete("DocShare", {"share_doctype": "CRM Lead"})
