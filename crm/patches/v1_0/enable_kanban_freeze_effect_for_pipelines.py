import frappe


def execute():
	if not frappe.db.exists("DocType", "CRM Sales Pipeline"):
		return

	if not frappe.get_meta("CRM Sales Pipeline").has_field("enable_kanban_freeze_effect"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabCRM Sales Pipeline`
		SET `enable_kanban_freeze_effect` = 1
		"""
	)
