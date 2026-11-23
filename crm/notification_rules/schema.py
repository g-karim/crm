"""Bounded declarative CRM rules; no evaluated expressions or recipient lists."""

import re

import frappe
from frappe import _

from crm.notification_rules.access import OBJECTS, require_record

EVENTS = {
	"record_inactive": {"objects": ["CRM Lead", "CRM Deal"], "available": True},
	"message_received": {"objects": ["CRM Lead", "CRM Deal"], "available": True},
	"record_mentioned": {"objects": ["CRM Lead", "CRM Deal"], "available": True},
	"comment_added": {"objects": ["CRM Lead", "CRM Deal"], "available": True},
	"lead_status_changed": {"objects": ["CRM Lead"], "available": True},
	"task_assigned": {"objects": ["CRM Lead", "CRM Deal", "CRM Task"], "available": True},
	"lead_assigned": {"objects": ["CRM Lead"], "available": True},
	"deal_assigned": {"objects": ["CRM Deal"], "available": True},
	"deal_stage_changed": {"objects": ["CRM Deal"], "available": True},
	"task_due_soon": {"objects": ["CRM Lead", "CRM Deal", "CRM Task"], "available": True},
	"task_overdue": {"objects": ["CRM Lead", "CRM Deal", "CRM Task"], "available": True},
}
LISTS = {"record_ids", "statuses", "to_statuses", "owners", "sources", "pipelines"}
KEYS = LISTS | {
	"id",
	"name",
	"enabled",
	"object",
	"event",
	"scope",
	"channels",
	"include_self",
	"reminder_minutes",
	"conditions",
	"inactive_minutes",
}
CHANNELS = {"crm_push", "one_message", "one_push", "email"}


def normalize_channels(values):
	# Existing three-key payloads stay valid and never opt into the new channel.
	if not isinstance(values, dict) or set(values) not in (CHANNELS, CHANNELS - {"email"}):
		invalid()
	if any(type(value) is not bool for value in values.values()):
		invalid()
	return {"email": False, **values}


def invalid():
	frappe.throw(_("Invalid CRM notification rule."))


def rule_id(value):
	if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{32}", value):
		invalid()
	return value


def names(value):
	if not isinstance(value, list) or len(value) > 100:
		invalid()
	if any(not isinstance(item, str) or not item or len(item) > 140 or "\0" in item for item in value):
		invalid()
	return sorted(set(value))


def validate(values, user):
	if not isinstance(values, dict) or set(values) - KEYS:
		invalid()
	rule_id(values.get("id"))
	if not isinstance(values.get("name"), str) or not 1 <= len(values["name"].strip()) <= 100:
		invalid()
	if type(values.get("enabled")) is not bool or type(values.get("include_self", False)) is not bool:
		invalid()
	if not isinstance(values.get("object"), str) or not isinstance(values.get("event"), str):
		invalid()
	obj, event = values.get("object"), EVENTS.get(values.get("event"))
	if obj not in OBJECTS or not event or obj not in event["objects"]:
		invalid()
	if not event["available"]:
		frappe.throw(_("This CRM event is planned but is not connected yet."))
	if values.get("scope") not in {"owned", "followed", "selected", "all_accessible"}:
		invalid()
	channels = normalize_channels(values.get("channels"))
	if channels["one_push"] and not channels["one_message"]:
		invalid()
	if not any(channels[key] for key in ("crm_push", "one_message", "email")):
		invalid()
	result = {
		**values,
		"channels": channels,
		"name": values["name"].strip(),
		"include_self": values.get("include_self", False),
	}
	if values["event"] == "task_due_soon":
		if type(values.get("reminder_minutes")) is not int or values["reminder_minutes"] not in (
			15,
			60,
			1440,
		):
			invalid()
	elif "reminder_minutes" in values:
		invalid()
	if values["event"] == "record_inactive":
		from crm.notification_rules.inactivity import available

		if (
			type(values.get("inactive_minutes")) is not int
			or not 30 <= values["inactive_minutes"] <= 43200
			or not available(obj)
		):
			invalid()
	elif "inactive_minutes" in values:
		invalid()
	if values["event"] in {"task_due_soon", "task_overdue", "record_inactive"} and result["include_self"]:
		invalid()
	for key in LISTS:
		result[key] = names(values.get(key, []))
	if (values["scope"] == "selected") != bool(result["record_ids"]):
		invalid()
	for name in result["record_ids"]:
		require_record(obj, name, user)
		if obj == "CRM Task" and frappe.get_doc(obj, name).reference_doctype:
			frappe.throw(_("Choose the linked lead or deal for a linked task."))
	if result["to_statuses"] and values["event"] not in {"lead_status_changed", "deal_stage_changed"}:
		invalid()
	if result["pipelines"] and obj != "CRM Deal":
		invalid()
	if "conditions" in values:
		from crm.notification_rules.conditions import validate as validate_conditions

		result["conditions"] = validate_conditions(values["conditions"], obj, user)
	_validate_links(result)
	return result


def _validate_links(rule):
	status_type = {"CRM Lead": "CRM Lead Status", "CRM Deal": "CRM Deal Status"}.get(rule["object"])
	for key, kind in [
		("statuses", status_type),
		("to_statuses", status_type),
		("owners", "User"),
		("sources", "CRM Lead Source"),
		("pipelines", "CRM Sales Pipeline"),
	]:
		for name in rule[key]:
			if key == "owners":
				from crm.api.celio_tasks import search_people

				if not any(person["value"] == name for person in search_people(query=name)):
					invalid()
				continue
			if not kind:
				if (
					key != "statuses"
					or name not in frappe.get_meta("CRM Task").get_field("status").options.splitlines()
				):
					invalid()
			elif not frappe.db.exists(kind, name) or not frappe.has_permission(
				kind, "read", doc=frappe.get_doc(kind, name)
			):
				invalid()
