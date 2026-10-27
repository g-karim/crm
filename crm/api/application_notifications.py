"""CRM UI for the shared subscription; never a second settings record."""
import frappe
from frappe import _


def _service():
	if not frappe.has_permission("CRM Task", "read") or not frappe.db.get_value("User", frappe.session.user, "enabled"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)
	if "exp_theme" not in frappe.get_installed_apps() or not frappe.db.table_exists("EXP Notification Subscription"):
		frappe.throw(_("Notification delivery is not ready on this site."))
	from exp_theme.notifications import api

	return api


@frappe.whitelist(methods=["GET"])
def get_settings():
	return _service().get_settings()


@frappe.whitelist(methods=["POST"])
def save_settings(enabled: bool, sender: str | None = None, push_route: str = "None", expected_revision: int = 0,
	mutation_id: str | None = None, expected_viewer: str | None = None):
	return _service().save_settings("crm", enabled, sender, push_route, expected_revision, mutation_id, expected_viewer)
