"""Retry only a complete settings POST; embedded calls keep their caller's transaction."""

from functools import wraps

import frappe
from exp_theme.notifications.transactions import database_conflict


def rpc(method):
	@wraps(method)
	def wrapped(*args, **kwargs):
		actor, site, sid = frappe.session.user, frappe.local.site, frappe.session.sid
		for attempt in range(3):
			try:
				if (frappe.session.user, frappe.local.site, frappe.session.sid) != (actor, site, sid):
					frappe.throw(
						frappe._("Your session changed. Reload this page."), frappe.AuthenticationError
					)
				return method(*args, **kwargs)
			except Exception as error:
				request = getattr(frappe.local, "request", None)
				if (
					not database_conflict(error)
					or attempt == 2
					or not request
					or request.method != "POST"
					or (frappe.form_dict.get("cmd") != f"{method.__module__}.{method.__name__}")
				):
					raise
				frappe.db.rollback()
				frappe.local.cache = {}
				frappe.local.document_cache = {}
				frappe.local.role_permissions = {}
				frappe.local.user_perms = None
				frappe.db.value_cache.clear()

	return wrapped
