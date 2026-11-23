"""Persist the last processed provider window for each configured SIP account."""

from datetime import datetime, timezone
from hashlib import sha256

import frappe
from frappe.utils import get_datetime

DOCTYPE = "CRM Exolve Sync Window"
FIELDS = ("name", "window_start_utc", "window_end_utc", "checked_at_utc", "result")


def mapping_name(application_id, employee, resource_id):
	identity = f"{application_id}\0{employee}\0{resource_id}"
	return "exolve-window-" + sha256(identity.encode()).hexdigest()


def record_window(application_id, resource_id, start, end, result):
	if not frappe.db.table_exists(DOCTYPE):
		return
	employee = frappe.session.user
	name = mapping_name(application_id, employee, resource_id)
	row = frappe.db.get_value(DOCTYPE, name, ["window_end_utc", "result"], as_dict=True, for_update=True)
	end_utc = end.astimezone(timezone.utc).replace(tzinfo=None)
	if row and (row.window_end_utc > end_utc or (row.window_end_utc == end_utc and row.result == "Read")):
		return
	values = {
		"employee": employee,
		"window_start_utc": start.astimezone(timezone.utc).replace(tzinfo=None),
		"window_end_utc": end_utc,
		"checked_at_utc": datetime.now(timezone.utc).replace(tzinfo=None),
		"result": result,
	}
	if row:
		frappe.db.set_value(DOCTYPE, name, values)
	else:
		frappe.get_doc({"doctype": DOCTYPE, **values}).insert(set_name=name, ignore_permissions=True)


def _iso_utc(value):
	return get_datetime(value).replace(tzinfo=timezone.utc).isoformat()


def recent_windows(allowed_employees, employee=None):
	"""Return window metadata only for currently visible, enabled SIP mappings."""
	if not frappe.db.table_exists(DOCTYPE) or not frappe.db.exists("DocType", "CRM Exolve Settings"):
		return []
	settings = frappe.get_single("CRM Exolve Settings")
	if not settings.enabled or not settings.application_id:
		return []
	mappings = {
		agent.user: agent.sip_resource_id for agent in settings.agents
		if agent.enabled and (allowed_employees is None or agent.user in allowed_employees)
		and (not employee or agent.user == employee)
	}
	if not mappings:
		return []
	names = {
		mapping_name(settings.application_id, row.name, mappings[row.name]): row.full_name or row.name
		for row in frappe.get_all("User", filters={"name": ["in", list(mappings)], "enabled": 1},
			fields=["name", "full_name"], order_by="full_name asc, name asc")
	}
	if not names:
		return []
	windows = {row.name: row for row in frappe.get_all(DOCTYPE, filters={"name": ["in", list(names)]}, fields=FIELDS)}
	result = []
	for name, label in names.items():
		row = windows.get(name)
		entry = {"label": label, "result": "Missing"}
		if row:
			entry.update(result=row.result, from_at=_iso_utc(row.window_start_utc),
				to_at=_iso_utc(row.window_end_utc), checked_at=_iso_utc(row.checked_at_utc))
		result.append(entry)
	return result
