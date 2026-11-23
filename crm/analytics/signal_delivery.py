"""Deliver analytics threshold episodes to a private CRM inbox."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from crm.analytics.service import normalize_filters, snapshot_hash
from crm.analytics.signals import MONITOR, RULES, _actual, _matches
from crm.utils import is_sales_user, sales_user_only

NOTICE = "CRM Analytics Signal Notice"
OPEN = ("Unread", "Read")
RULE_FIELDS = ["name", "owner", "metric", "threshold", "enabled", "modified"]


def _available():
	return frappe.db.table_exists(MONITOR) and frappe.db.table_exists(NOTICE)


def _enabled_user(viewer):
	return viewer != "Guest" and bool(frappe.db.get_value("User", viewer, "enabled"))


def schedule():
	"""Run from the native Frappe scheduler when that site's scheduler is active."""
	if not _available():
		return 0
	users = set(frappe.get_all(MONITOR, filters={"enabled": 1}, pluck="owner", distinct=True))
	users.update(frappe.get_all(NOTICE, filters={"state": ["in", OPEN]}, pluck="owner", distinct=True))
	for viewer in sorted(users):
		frappe.enqueue(evaluate_recipient, queue="short",
			job_id="crm-analytics-signals-" + snapshot_hash(viewer)[:24], deduplicate=True, viewer=viewer)
	return len(users)


def _notice(rule):
	return frappe.db.get_value(NOTICE, {"monitor": rule.name, "owner": rule.owner, "state": ["in", OPEN]},
		["name", "rule_version", "state"], as_dict=True, for_update=True)


def _evaluate(rule, actual):
	current = frappe.db.get_value(MONITOR, rule.name, RULE_FIELDS, as_dict=True, for_update=True)
	if current != rule:
		return "changed"
	previous = _notice(current)
	active = bool(current.enabled and _matches(current.metric, current.threshold, actual))
	version = str(current.modified)
	if previous and (not active or version != previous.rule_version):
		frappe.db.set_value(NOTICE, previous.name, {"state": "Resolved", "resolved_at": now_datetime()})
		previous = None
		if not active:
			return "resolved"
	if not active or previous:
		return "unchanged"
	frappe.get_doc({"doctype": NOTICE, "owner": current.owner, "monitor": current.name,
		"metric": current.metric, "rule_version": version, "state": "Unread"}).insert(ignore_permissions=True)
	return "delivered"


def evaluate_recipient(viewer):
	"""Recompute live metrics with the recipient's native CRM permissions."""
	if not _available():
		return {"available": False}
	previous = frappe.session.user
	try:
		valid = _enabled_user(viewer)
		if valid:
			frappe.set_user(viewer)
			valid = is_sales_user()
		rules = frappe.get_all(MONITOR, filters={"owner": viewer}, fields=RULE_FIELDS, order_by="name")
		ctx = normalize_filters() if valid and any(row.enabled for row in rules) else None
		changes = {}
		for row in rules:
			if row.metric not in RULES:
				continue
			actual = _actual(row.metric, ctx) if ctx and row.enabled else None
			changes[row.metric] = _evaluate(row, actual)
		return {"available": True, "changes": changes}
	finally:
		frappe.set_user(previous)


def unread_for_active_rules(rows):
	"""Expose recent notices only if their rules still match current live facts."""
	if not _available():
		return []
	live = {row["metric"]: row for row in rows if row["enabled"] and row["active"] is True}
	if not live:
		return []
	requested = frappe.get_all(NOTICE, filters={"owner": frappe.session.user,
		"metric": ["in", sorted(live)], "state": "Unread"},
		fields=["name", "metric", "creation", "rule_version"], order_by="creation desc, name desc", limit_page_length=30)
	return [{"name": row.name, "metric": row.metric, "arrived_at": row.creation}
		for row in requested if live[row.metric]["version"] == row.rule_version]


@frappe.whitelist(methods=["POST"])
@sales_user_only
def acknowledge(name: str, expected_viewer: str):
	viewer = frappe.session.user
	if viewer != expected_viewer:
		frappe.throw(_("This signal is unavailable."), frappe.PermissionError)
	row = frappe.db.get_value(NOTICE, name, ["name", "owner", "state"], as_dict=True, for_update=True)
	if not row or row.owner != viewer:
		frappe.throw(_("This signal is unavailable."), frappe.PermissionError)
	if row.state == "Unread":
		frappe.db.set_value(NOTICE, row.name, "state", "Read")
	return {"read": True}
