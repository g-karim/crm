"""Personal thresholds evaluated against current authorized data in the CRM."""

from datetime import timedelta

import frappe
from frappe import _

from crm.analytics.call_reporting import _make_report as call_report
from crm.analytics.engine import number
from crm.analytics.goals import goal_report
from crm.analytics.service import calculate, coherent_read, exact_json, normalize_filters, snapshot_hash
from crm.utils import sales_user_only

MONITOR = "CRM Analytics Monitor"
RULES = {
	"calls_overdue": (1, 100_000, "at_least", "calls"),
	"tasks_overdue": (1, 100_000, "at_least", "managers"),
	"monthly_progress": (70, 100, "below", "managers"),
}


def _name(viewer, metric):
	return "monitor-" + snapshot_hash(viewer, metric)[:36]


def _validate(metric, threshold):
	if metric not in RULES or not 1 <= threshold <= RULES[metric][1]:
		frappe.throw(_("Choose a threshold within the displayed range."), frappe.ValidationError)


def validate_document(doc):
	_validate(doc.metric, doc.threshold)
	if doc.name != _name(doc.owner, doc.metric):
		frappe.throw(_("Invalid private monitoring rule."), frappe.ValidationError)


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_monitor(metric: str, threshold: int, enabled: bool, expected_viewer: str, version: str | None = None):
	viewer = frappe.session.user
	if viewer != expected_viewer:
		frappe.throw(_("Reload analytics after switching users."), frappe.PermissionError)
	_validate(metric, threshold)
	name = _name(viewer, metric)
	try:
		current = frappe.db.get_value(MONITOR, name, ["threshold", "enabled", "modified"], as_dict=True, for_update=True)
		if current and (current.threshold, bool(current.enabled)) == (threshold, enabled):
			return {"version": str(current.modified)}
		if (version or "") != (str(current.modified) if current else ""):
			frappe.throw(_("This rule changed. Reopen its current version."), frappe.TimestampMismatchError)
		if current:
			doc = frappe.get_doc(MONITOR, name, for_update=True)
			doc.update({"threshold": threshold, "enabled": enabled})
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": MONITOR, "owner": viewer, "metric": metric, "threshold": threshold,
				"enabled": enabled}).insert(set_name=name, ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.QueryDeadlockError):
		frappe.throw(_("This rule changed. Reopen its current version."), frappe.TimestampMismatchError)
	return {"version": str(doc.modified)}


def _actual(metric, ctx):
	try:
		if metric == "calls_overdue":
			start = ctx.as_of.date() - timedelta(days=29)
			return call_report({"from_date": str(start), "to_date": str(ctx.as_of.date())})[0]["metrics"]["overdue"]
		if metric == "tasks_overdue":
			return calculate(ctx, include_source_revision=False)[0]["activity"]["tasks"]["overdue"]
		goals = goal_report("Month", str(ctx.as_of.date()))
		comparable = [value for row in goals["rows"] if (value := number(row["progress"])) is not None]
		return min(comparable) if comparable else None
	except frappe.PermissionError:
		return None


def _matches(metric, threshold, actual):
	if actual is None:
		return None
	return actual < threshold if RULES[metric][2] == "below" else actual >= threshold


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_signals():
	from crm.analytics.signal_delivery import unread_for_active_rules

	viewer = frappe.session.user
	ctx = normalize_filters()
	records = {row.metric: row for row in frappe.get_all(MONITOR, filters={"owner": viewer},
		fields=["metric", "threshold", "enabled", "modified"])}
	rows = []
	for metric, (default, upper, _condition, destination) in RULES.items():
		rule = records.get(metric)
		enabled = bool(rule.enabled) if rule else False
		threshold = rule.threshold if rule else default
		actual = _actual(metric, ctx) if enabled else None
		active = _matches(metric, threshold, actual)
		rows.append({"metric": metric, "threshold": threshold, "upper": upper, "destination": destination,
			"enabled": enabled, "version": str(rule.modified) if rule else None, "actual": actual, "active": active})
	return exact_json({"viewer": viewer, "observed_at": ctx.as_of, "rows": rows,
		"inbox": unread_for_active_rules(rows)})
