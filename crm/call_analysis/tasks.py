"""Retired unbudgeted worker entrypoints. Stored legacy analysis remains readable."""

from uuid import uuid4

import frappe


def enqueue_call_analysis(call_log, user, *, language=None):
	# No privilege elevation from arbitrary background owners.
	if frappe.session.user != user:
		frappe.throw("Analysis must be requested by its CRM user.", frappe.PermissionError)
	from .workspace import start

	return start(call_log.name, str(uuid4()))


def run_call_analysis(call_log_name, user=None, language=None):
	# Old queued jobs have no explicit spending authorization. Never replay them.
	return {"status": "Failed", "error": "Open Telephony and explicitly request budgeted analysis."}
