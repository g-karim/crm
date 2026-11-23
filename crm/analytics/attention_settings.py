"""Stage-specific attention rules in the existing CRM sales pipeline."""

import re

import frappe
from frappe import _
from frappe.utils import get_datetime

from crm.analytics.engine import OPEN, RISK_REASONS
from crm.analytics.sales_plans import company_plan_editor
from crm.analytics.service import coherent_read, readable_rows

STAGE = "CRM Deal Status"
DISABLED = "analytics_disabled_risks"
DAYS = "analytics_stale_days"


def _can_edit():
	return company_plan_editor() and frappe.has_permission(STAGE, "write")


def _version(row):
	return get_datetime(row.get("modified")).isoformat(sep=" ", timespec="microseconds")


def _item(row):
	disabled = set((row.get(DISABLED) or "").split(","))
	return {"key": row.get("name"), "label": row.get("deal_status"), "pipeline": row.get("pipeline"),
		"enabled_rules": [rule for rule in RISK_REASONS if rule not in disabled],
		"stale_days": row.get(DAYS), "version": _version(row)}


@frappe.whitelist(methods=["GET"])
@coherent_read
def get_settings():
	if not _can_edit():
		return {"can_edit": False, "stages": []}
	fields = ["name", "deal_status", "pipeline", "position", "modified", DAYS, DISABLED]
	rows, readable = readable_rows(STAGE, fields, {"type": ["in", sorted(OPEN)], "archived": 0})
	if not set(fields) <= readable:
		return {"can_edit": False, "stages": []}
	pipeline_names = sorted({row["pipeline"] for row in rows if row.get("pipeline")})
	pipelines, _fields = readable_rows("CRM Sales Pipeline", ["name", "pipeline_name"], {"name": ["in", pipeline_names]}) if pipeline_names else ([], set())
	labels = {row["name"]: row.get("pipeline_name") for row in pipelines}
	rows.sort(key=lambda row: (row["pipeline"], row.get("position") or 0, row["deal_status"], row["name"]))
	return {"can_edit": True, "viewer": frappe.session.user, "rules": RISK_REASONS,
		"stages": [{**_item(row), "pipeline_label": labels.get(row["pipeline"])} for row in rows]}


@frappe.whitelist(methods=["POST"])
def save_setting(stage: str, enabled_rules: list[str], stale_days: str, version: str, expected_viewer: str):
	if not _can_edit() or expected_viewer != frappe.session.user:
		frappe.throw(_("Only system managers may configure analytics attention rules."), frappe.PermissionError)
	if (not isinstance(enabled_rules, list) or any(rule not in RISK_REASONS for rule in enabled_rules)
		or not re.fullmatch(r"[0-9]{1,4}", stale_days or "") or int(stale_days) > 3650):
		frappe.throw(_("Choose valid attention rules and a stage threshold from 0 to 3650 days."), frappe.ValidationError)
	days = int(stale_days)
	disabled = ",".join(rule for rule in RISK_REASONS if rule not in enabled_rules)
	conflict = _("This stage changed. Reload its settings before saving.")
	try:
		doc = frappe.get_doc(STAGE, stage, for_update=True)
		doc.check_permission("write")
		if doc.type not in OPEN or doc.archived or DISABLED not in doc.meta.get_valid_columns():
			frappe.throw(_("Choose an active open stage with analytics settings."), frappe.ValidationError)
		if (doc.get(DISABLED) or "", doc.get(DAYS)) == (disabled, days):
			return _item(doc)
		if version != _version(doc):
			frappe.throw(conflict, frappe.TimestampMismatchError)
		doc.update({DISABLED: disabled, DAYS: days})
		doc.save()
	except frappe.QueryDeadlockError:
		frappe.throw(conflict, frappe.TimestampMismatchError)
	return _item(doc)
