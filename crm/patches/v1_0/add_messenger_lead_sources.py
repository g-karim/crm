import frappe


def execute():
	for source in ("VK", "Telegram bot", "MAX"):
		if not frappe.db.exists("CRM Lead Source", source):
			frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source}).insert(
				ignore_if_duplicate=True
			)
