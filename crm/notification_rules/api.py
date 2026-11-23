"""Personal CRM policy API shared by CRM, Home and One; no caller-selected users."""

from copy import deepcopy

import frappe
from exp_theme.notifications import policy, settings
from exp_theme.notifications.access import require_viewer
from exp_theme.notifications.push import delivery as push_delivery
from exp_theme.notifications.push import preferences
from frappe import _
from frappe.utils import cint, now_datetime

from crm.notification_rules import engine, mutation, schema
from crm.notification_rules.access import (
	OBJECTS,
	readable,
	require_crm,
	require_record,
	title,
	visible_configuration,
)


def viewer(expected_viewer=None):
	user = require_viewer(expected_viewer)
	require_crm(user)
	return user


def _state(user, row=None):
	from exp_theme.notifications import email_channel

	from crm.notification_rules.reminders import enabled

	row = row or policy.load(user, "crm")
	email_enabled = bool(policy.configuration(row).get("email_enabled", False))
	primary = preferences.preference(user, "crm")
	one = settings.subscription(user, "crm")
	destination = (
		frappe.db.get_value(settings.DESTINATION, {"name": one.destination, "user": user}, "push_route")
		if one.destination
		else None
	)
	push_ready = bool(push_delivery.configured())
	channel_state = settings.state(user)
	one_state = next(item for item in channel_state["sources"] if item["id"] == "crm")
	return {
		"viewer": user,
		"revision": cint(row.revision),
		"delivery_epoch": cint(row.delivery_epoch),
		"configuration": visible_configuration(policy.configuration(row), user),
		"email_service_available": email_channel.ready(),
		"email_global_enabled": email_channel.user_enabled(user),
		"masters": {
			"email": email_enabled,
			"crm_push": bool(primary.enabled),
			"one_message": bool(one.enabled),
			"one_push": bool(one.enabled and destination == "One"),
		},
		"push_service_available": push_ready,
		"reminders_available": enabled(),
		"effective_masters": {
			"email": bool(email_enabled and email_channel.ready() and email_channel.user_enabled(user)),
			"crm_push": bool(primary.enabled and push_ready),
			"one_message": one_state["effective"],
			"one_push": bool(one_state["effective"] and destination == "One" and push_ready),
		},
		"one_reason": one_state["reason"],
		"master_revisions": {"crm_push": cint(primary.revision), "one_message": cint(one.revision)},
		"sender": one_state["sender"],
		"senders": channel_state["senders"],
		"legacy": not bool(row.revision) or policy.configuration(row).get("mode") == "legacy",
	}


@frappe.whitelist(methods=["GET"])
def get_settings(expected_viewer: str | None = None):
	return _state(viewer(expected_viewer))


def _apply(user, action, expected_revision, mutation_id, transform):
	row, replayed, applied = policy.update(user, "crm", action, expected_revision, mutation_id, transform)
	return {**_state(user, row), "replayed": replayed, "applied_revision": applied}


def _configuration(values):
	return {
		"schema_version": 1,
		"email_enabled": bool(values.get("email_enabled", False)),
		"rules": values.get("rules", []),
		"records": values.get("records", []),
		"mode": values.get("mode", "rules" if "schema_version" in values else "legacy"),
	}


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def save_rule(values: dict, expected_revision: int, mutation_id: str, expected_viewer: str | None = None):
	if not expected_viewer:
		frappe.throw(_("Reload this page before changing notifications."), frappe.AuthenticationError)
	user = viewer(expected_viewer)
	raw = frappe.parse_json(values)
	rule = schema.validate(raw, user)
	request_rule = {**rule, "channels": dict(rule["channels"])}
	if "email" not in raw["channels"]:
		# Preserve the pre-email request hash for an immutable lost-response replay.
		request_rule["channels"].pop("email")

	def transform(current):
		result = _configuration(current)
		result["mode"] = "rules"
		result["rules"] = [row for row in result["rules"] if row["id"] != rule["id"]] + [rule]
		if len(result["rules"]) > 50:
			frappe.throw(_("The personal rule limit is 50."))
		return result

	return _apply(user, {"save_rule": request_rule}, expected_revision, mutation_id, transform)


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def delete_rule(rule_id: str, expected_revision: int, mutation_id: str, expected_viewer: str | None = None):
	if not expected_viewer:
		frappe.throw(_("Reload this page before changing notifications."), frappe.AuthenticationError)
	user = viewer(expected_viewer)
	schema.rule_id(rule_id)

	def transform(current):
		result = _configuration(current)
		if not any(rule["id"] == rule_id for rule in result["rules"]):
			frappe.throw(_("This rule is no longer available."))
		result["rules"] = [rule for rule in result["rules"] if rule["id"] != rule_id]
		return result

	return _apply(user, {"delete_rule": rule_id}, expected_revision, mutation_id, transform)


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def set_record(
	doctype: str,
	record_id: str,
	followed: bool,
	muted: bool,
	expected_revision: int,
	mutation_id: str,
	expected_viewer: str | None = None,
):
	if not expected_viewer:
		frappe.throw(_("Reload this page before changing notifications."), frappe.AuthenticationError)
	user = viewer(expected_viewer)
	require_record(doctype, record_id, user)
	if type(followed) is not bool or type(muted) is not bool:
		schema.invalid()
	value = {"object": doctype, "record_id": record_id, "followed": followed, "muted": muted}

	def transform(current):
		result = _configuration(current)
		result["records"] = [
			row for row in result["records"] if (row["object"], row["record_id"]) != (doctype, record_id)
		]
		if followed or muted:
			result["records"].append(value)
		if len(result["records"]) > 200:
			frappe.throw(_("The personal record limit is 200."))
		return result

	return _apply(user, {"set_record": value}, expected_revision, mutation_id, transform)


@frappe.whitelist(methods=["GET"])
def options(expected_viewer: str | None = None):
	from crm.notification_rules.conditions import fields
	from crm.notification_rules.controls import metadata

	user = viewer(expected_viewer)
	return {
		**metadata(user),
		"events": deepcopy(schema.EVENTS),
		"condition_fields": {kind: fields(kind, user) for kind in sorted(OBJECTS)},
		"objects": sorted(OBJECTS),
		"statuses": {
			kind: frappe.get_list(status, pluck="name", limit_page_length=100)
			for kind, status in [("CRM Lead", "CRM Lead Status"), ("CRM Deal", "CRM Deal Status")]
		},
		"sources": frappe.get_list("CRM Lead Source", pluck="name", limit_page_length=100),
		"pipelines": frappe.get_list("CRM Sales Pipeline", pluck="name", limit_page_length=100),
	}


@frappe.whitelist(methods=["GET"])
def search_records(doctype: str, query: str = "", expected_viewer: str | None = None):
	user = viewer(expected_viewer)
	if doctype not in OBJECTS or not isinstance(query, str) or len(query) > 100:
		schema.invalid()
	title_field = "title" if doctype == "CRM Task" else frappe.get_meta(doctype).title_field or "name"
	rows = frappe.get_list(
		doctype,
		filters={"reference_doctype": ["is", "not set"]} if doctype == "CRM Task" else {},
		fields=list(dict.fromkeys(["name", title_field])),
		or_filters=[["name", "like", "%" + query + "%"], [title_field, "like", "%" + query + "%"]],
		limit_page_length=20,
		order_by="modified desc",
	)
	return [
		{"id": str(row.name), "label": title(doctype, row.name)}
		for row in rows
		if readable(doctype, row.name, user)
	]


@frappe.whitelist(methods=["POST"])
def explain_record(
	doctype: str,
	record_id: str,
	event: str,
	previous_status: str | None = None,
	new_status: str | None = None,
	expected_viewer: str | None = None,
):
	user = viewer(expected_viewer)
	require_record(doctype, record_id, user)
	info = schema.EVENTS.get(event)
	if not info or not info["available"]:
		schema.invalid()
	if event == "task_assigned" and doctype != "CRM Task":
		schema.invalid()
	if event in {"lead_status_changed", "lead_assigned"} and doctype != "CRM Lead":
		schema.invalid()
	if event in {"deal_stage_changed", "deal_assigned"} and doctype != "CRM Deal":
		schema.invalid()
	facts = engine.snapshot(
		doctype, record_id, event, actor=None, occurred_at=now_datetime(), previous_status=previous_status
	)
	if event in {"lead_status_changed", "deal_stage_changed"}:
		status_type = "CRM Lead Status" if doctype == "CRM Lead" else "CRM Deal Status"
		for status in [previous_status, new_status]:
			if not status or not frappe.db.exists(status_type, status):
				schema.invalid()
		facts["status"] = new_status
	result = engine.evaluate(facts, user)
	masters = _state(user)["effective_masters"]
	return {
		**result,
		"hypothetical": True,
		"effective_channels": {key: value and masters[key] for key, value in result["channels"].items()},
	}
