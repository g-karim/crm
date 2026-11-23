"""Administrator-owned schedule for the current CRM site."""

from datetime import time
import re
from zoneinfo import ZoneInfoNotFoundError

import frappe
from frappe import _

from crm.analytics.call_sla import WorkingHours
from crm.analytics.service import coherent_read, exact_json

DOCTYPE = "CRM Call SLA"
NAME = "Default"
FIELDS = ["enabled", "timezone", "weekdays", "work_start", "work_end", "response_minutes", "modified"]
HANDOFF_FIELD = "require_original_employee"


def validate_schedule(zone, weekdays, start, end, minutes):
	try:
		if not (re.fullmatch(r"[0-6](?:,[0-6]){0,6}", weekdays)
			and re.fullmatch(r"\d{2}:\d{2}", start) and re.fullmatch(r"\d{2}:\d{2}", end)
			and 1 <= minutes <= 10080):
			raise ValueError
		days = tuple(sorted({int(day) for day in weekdays.split(",")}))
		return WorkingHours(zone, days, time.fromisoformat(start), time.fromisoformat(end))
	except (TypeError, ValueError, ZoneInfoNotFoundError):
		frappe.throw(_("Choose a timezone, workdays, an ordered work interval and a response time between 1 and 10,080 minutes."),
			frappe.ValidationError)


def _row(*, for_update=False):
	if frappe.db.table_exists(DOCTYPE):
		fields = [*FIELDS, HANDOFF_FIELD] if frappe.db.has_column(DOCTYPE, HANDOFF_FIELD) else FIELDS
		return frappe.db.get_value(DOCTYPE, NAME, fields, as_dict=True, for_update=for_update)
	return None


def _legacy_values():
	config = frappe.conf.get("crm_call_analytics_sla")
	if not config:
		return {}
	try:
		return {"enabled": 1, "timezone": config["timezone"], "weekdays": ",".join(map(str, config["days"])),
			"work_start": config["start"], "work_end": config["end"], "response_minutes": int(config["minutes"])}
	except (KeyError, TypeError, ValueError):
		frappe.throw(_("The configured call SLA is invalid."), frappe.ValidationError)


def actual_schedule():
	row = _row()
	if row is None:
		row = _legacy_values()
	if not row.get("enabled"):
		return None, None, False
	hours = validate_schedule(row["timezone"], row["weekdays"], row["work_start"], row["work_end"], row["response_minutes"])
	return hours, row["response_minutes"], bool(row.get(HANDOFF_FIELD))


def can_manage():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _serialize(row):
	zone = frappe.db.get_single_value("System Settings", "time_zone") or "UTC"
	values = dict(_legacy_values() if row is None else row)
	values.update(version=str(values.pop("modified", "") or ""),
		available=frappe.db.table_exists(DOCTYPE) and frappe.db.has_column(DOCTYPE, HANDOFF_FIELD))
	return {
		"enabled": False, "timezone": zone, "weekdays": "0,1,2,3,4", "work_start": "09:00",
		"work_end": "18:00", "response_minutes": 60, HANDOFF_FIELD: False, **values,
	}


@frappe.whitelist(methods=["GET"])
@coherent_read
def get_settings():
	if not can_manage():
		frappe.throw(_("Only system managers may configure call SLA."), frappe.PermissionError)
	return exact_json(_serialize(_row()))


@frappe.whitelist(methods=["POST"])
def save_settings(enabled: bool, timezone: str, weekdays: str, work_start: str, work_end: str,
	response_minutes: int, version: str = "", require_original_employee: bool | None = None):
	if not can_manage():
		frappe.throw(_("Only system managers may configure call SLA."), frappe.PermissionError)
	validate_schedule(timezone, weekdays, work_start, work_end, response_minutes)
	if not frappe.db.table_exists(DOCTYPE) or not frappe.db.has_column(DOCTYPE, HANDOFF_FIELD):
		frappe.throw(_("Install the call SLA settings schema before editing."), frappe.ValidationError)
	current = _row(for_update=True)
	if version != (str(current.modified) if current else ""):
		frappe.throw(_("The call SLA settings changed. Reload before saving."), frappe.TimestampMismatchError)
	values = dict(enabled=int(enabled), timezone=timezone,
		weekdays=",".join(sorted(set(weekdays.split(",")))), work_start=work_start, work_end=work_end,
		response_minutes=response_minutes)
	if require_original_employee is not None:
		values[HANDOFF_FIELD] = int(require_original_employee)
	try:
		if current:
			doc = frappe.get_doc(DOCTYPE, NAME, for_update=True)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": DOCTYPE, **values}).insert(ignore_permissions=True, set_name=NAME)
	except (frappe.QueryDeadlockError, frappe.DuplicateEntryError):
		frappe.throw(_("The call SLA settings changed. Reload before saving."), frappe.TimestampMismatchError)
	return exact_json(_serialize({field: doc.get(field) for field in [*FIELDS, HANDOFF_FIELD]}))
