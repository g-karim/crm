"""Compatibility route to the canonical CRM rule editor."""

import frappe

no_cache = 1


def get_context(context):
	from crm.notification_rules.api import viewer

	viewer()
	frappe.local.flags.redirect_location = "/crm/notification-rules"
	raise frappe.Redirect
