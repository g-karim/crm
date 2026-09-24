import frappe


def execute():
	for role in ("CRM Manager", "CRM User"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)
