"""Personal channel controls and permission-filtered choices for the CRM rule editor."""

import frappe
from exp_theme.notifications import policy, settings
from exp_theme.notifications.push import preferences
from frappe import _
from frappe.utils import cint

from crm.notification_rules import mutation, schema


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def save_channels(
	crm_push: bool,
	one_message: bool,
	one_push: bool,
	sender: str | None,
	expected_revision: int,
	expected_primary_revision: int,
	expected_one_revision: int,
	mutation_id: str,
	expected_viewer: str,
	email: bool | None = None,
):
	from crm.notification_rules.api import _state, viewer

	user = viewer(expected_viewer)
	if not expected_viewer or any(type(value) is not bool for value in [crm_push, one_message, one_push]):
		schema.invalid()
	if email is not None and type(email) is not bool:
		schema.invalid()
	if one_push and not one_message:
		schema.invalid()
	if any(
		type(value) is not int or value < 0 for value in [expected_primary_revision, expected_one_revision]
	):
		schema.invalid()
	action = {
		"channels": [
			crm_push,
			one_message,
			one_push,
			sender,
			expected_primary_revision,
			expected_one_revision,
		]
	}

	if email is not None:
		action["email"] = email

	def transform(current):
		primary = preferences.preference(user, "crm", lock=True)
		one = settings.subscription(user, "crm")
		actual_one = frappe.db.get_value(settings.SUBSCRIPTION, one.name, "revision", for_update=True) or 0
		if primary.revision != expected_primary_revision or cint(actual_one) != expected_one_revision:
			frappe.throw(
				_("Notification settings changed. Reload before saving."), frappe.TimestampMismatchError
			)
		preferences.save(user, "crm", crm_push, primary.revision, mutation_id + ":push")
		settings.save(
			user,
			"crm",
			one_message,
			sender,
			"One" if one_push else "None",
			expected_one_revision,
			mutation_id + ":one",
		)
		current = current or {"schema_version": 1, "mode": "legacy", "rules": [], "records": []}
		if email is not None:
			current = {**current, "email_enabled": email}
		return current

	row, replayed, applied = policy.update(user, "crm", action, expected_revision, mutation_id, transform)
	return {**_state(user, row), "replayed": replayed, "applied_revision": applied}


@frappe.whitelist(methods=["GET"])
def record_state(doctype: str, record_id: str, expected_viewer: str | None = None):
	from crm.notification_rules.access import require_record
	from crm.notification_rules.api import viewer

	user = viewer(expected_viewer)
	require_record(doctype, record_id, user)
	row = policy.load(user, "crm")
	values = policy.configuration(row)
	record = next(
		(r for r in values.get("records", []) if (r["object"], r["record_id"]) == (doctype, record_id)), {}
	)
	return {
		"viewer": user,
		"revision": cint(row.revision),
		"followed": bool(record.get("followed")),
		"muted": bool(record.get("muted")),
		"has_follow_rule": any(
			rule["enabled"] and rule["object"] == doctype and rule["scope"] == "followed"
			for rule in values.get("rules", [])
		),
	}


@frappe.whitelist(methods=["GET"])
def people(query: str = "", expected_viewer: str | None = None):
	from crm.notification_rules.api import viewer

	viewer(expected_viewer)
	if not isinstance(query, str) or len(query) > 100:
		schema.invalid()
	from crm.api.celio_tasks import search_people

	# This reuses CRM's existing assignment directory; it does not access Celio.
	return search_people(query=query)


def metadata(user):
	status_options = {}
	for kind, status, label in [
		("CRM Lead", "CRM Lead Status", "lead_status"),
		("CRM Deal", "CRM Deal Status", "deal_status"),
	]:
		fields = ["name as value", label + " as label"] + (["pipeline"] if kind == "CRM Deal" else [])
		status_options[kind] = frappe.get_list(status, fields=fields, limit_page_length=100)
		for item in status_options[kind]:
			item.label = _(item.label)
			if item.get("pipeline"):
				item.label = f"{item.label} · {item.pipeline}"
	status_options["CRM Task"] = [
		{"value": value, "label": _(value)}
		for value in frappe.get_meta("CRM Task").get_field("status").options.splitlines()
		if value
	]
	return {
		"status_options": status_options,
		"presets": [
			{
				"id": "mentions",
				"label": "Mentions of me",
				"object": "CRM Lead",
				"event": "record_mentioned",
				"scope": "all_accessible",
			},
			{
				"id": "comments",
				"label": "Comments on followed records",
				"object": "CRM Lead",
				"event": "comment_added",
				"scope": "followed",
			},
			{
				"id": "task_deadlines",
				"label": "Standalone task deadlines",
				"object": "CRM Task",
				"event": "task_due_soon",
				"scope": "owned",
				"reminder_minutes": 60,
			},
			{
				"id": "assignments",
				"label": "Assignments to me",
				"object": "CRM Lead",
				"event": "lead_assigned",
				"scope": "owned",
			},
			{
				"id": "following",
				"label": "Changes to followed records",
				"object": "CRM Lead",
				"event": "lead_status_changed",
				"scope": "followed",
			},
			{
				"id": "selected",
				"label": "Selected leads and statuses",
				"object": "CRM Lead",
				"event": "lead_status_changed",
				"scope": "selected",
			},
		],
	}
