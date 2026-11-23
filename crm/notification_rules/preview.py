"""Hypothetical, permission-filtered preview; never publishes or sends an event."""

from copy import deepcopy

import frappe
from exp_theme.notifications import policy
from frappe.utils import now_datetime

from crm.notification_rules import engine, schema
from crm.notification_rules.access import readable, title


@frappe.whitelist(methods=["POST"])
def preview_rule(values: dict, expected_viewer: str | None = None):
	from crm.notification_rules.api import _state, viewer

	user = viewer(expected_viewer)
	rule = schema.validate(frappe.parse_json(values), user)
	row = policy.load(user, "crm")
	config = deepcopy(policy.configuration(row))
	config["rules"] = [r for r in config.get("rules", []) if r["id"] != rule["id"]] + [rule]
	current = _state(user, row)
	if rule["event"] in {"task_due_soon", "task_overdue"}:
		from crm.notification_rules.deadline_preview import examples

		return {
			"viewer": user,
			"hypothetical": True,
			"items": examples(rule, user, config, current["effective_masters"]),
			"limit": 20,
			"revision": current["revision"],
			"masters": current["effective_masters"],
		}
	if rule["scope"] == "selected":
		names = rule["record_ids"]
	else:
		names = frappe.get_list(
			rule["object"],
			filters={"reference_doctype": ["is", "not set"]} if rule["object"] == "CRM Task" else {},
			pluck="name",
			limit_page_length=100,
			order_by="modified desc",
		)
	items = []
	for name in names:
		if not readable(rule["object"], name, user):
			continue
		facts = engine.snapshot(
			rule["object"],
			name,
			rule["event"],
			actor=None,
			occurred_at=now_datetime(),
			previous_status="__future_transition__",
		)
		# A task on a parent record is previewed using that parent's rule, not a
		# synthetic standalone task or a change to the parent's business data.
		if rule["event"] == "task_assigned":
			facts["object"], facts["record_id"] = rule["object"], str(name)
		if rule["event"] == "record_inactive":
			facts["inactive_minutes"] = rule["inactive_minutes"]
		facts["assignee"] = user
		facts["mention_recipient"] = user if rule["event"] == "record_mentioned" else None
		result = None
		for status in rule["to_statuses"] or [facts["status"]]:
			candidate = {**facts, "status": status}
			matched = engine.evaluate_rules(config, candidate, user)
			if rule["id"] in matched["matched_rules"]:
				result = matched
				break
		if result is None:
			continue
		if rule["id"] not in result["matched_rules"]:
			continue
		items.append(
			{
				"id": str(name),
				"label": title(rule["object"], name),
				"matched_rules": result["matched_rules"],
				"reason": result["reason"],
				"effective_channels": {
					key: value and current["effective_masters"][key]
					for key, value in result["channels"].items()
				},
			}
		)
		if len(items) == 20:
			break
	return {
		"viewer": user,
		"hypothetical": True,
		"items": items,
		"limit": 20,
		"complete": len(names) < 100 and len(items) < 20,
		"revision": current["revision"],
		"masters": current["effective_masters"],
	}
