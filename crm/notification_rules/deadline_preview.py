"""Preview actual assigned tasks, using the same schedule and rule semantics."""

import frappe

from crm.notification_rules import engine, reminders
from crm.notification_rules.access import readable, title


def examples(rule, user, configuration, masters):
	filters = {"assigned_to": user, "due_date": ["is", "set"], "status": ["not in", sorted(reminders.CLOSED)]}
	if rule["object"] == "CRM Task":
		filters["reference_doctype"] = ["is", "not set"]
		if rule["scope"] == "selected":
			filters["name"] = ["in", rule["record_ids"]]
	else:
		filters["reference_doctype"] = rule["object"]
		if rule["scope"] == "selected":
			filters["reference_docname"] = ["in", rule["record_ids"]]
	names = frappe.get_list(
		"CRM Task", filters=filters, pluck="name", order_by="due_date asc", limit_page_length=100
	)
	items = []
	for name in names:
		if not readable("CRM Task", name, user):
			continue
		task = frappe.get_doc("CRM Task", name)
		facts = reminders.facts_for(task, rule["event"], rule.get("reminder_minutes", 0))
		at = reminders.scheduled_at(task, rule["event"], rule.get("reminder_minutes", 0))
		if at < reminders.clock():
			continue  # Saving a new rule never backfills a missed scheduled event.
		result = engine.evaluate_rules(configuration, facts, user)
		if rule["id"] not in result["matched_rules"]:
			continue
		items.append(
			{
				"id": str(name),
				"label": title("CRM Task", name),
				"scheduled_at": at.isoformat(),
				"matched_rules": result["matched_rules"],
				"reason": result["reason"],
				"effective_channels": {
					key: value and masters[key] for key, value in result["channels"].items()
				},
			}
		)
		if len(items) == 20:
			break
	return items
