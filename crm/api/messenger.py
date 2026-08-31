import frappe


@frappe.whitelist()
def is_messenger_installed() -> bool:
	"""Let the CRM settings UI hide Messenger when its app is not installed."""
	return bool(frappe.db.exists("DocType", "Messenger Settings"))
