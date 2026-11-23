"""Company-owned forecast categories assigned to open CRM stages."""

import frappe
from frappe import _

from crm.analytics.engine import OPEN
from crm.analytics.metric_catalog import FORECAST_CATEGORIES
from crm.analytics.sales_plans import company_plan_editor
from crm.analytics.service import coherent_read, readable_rows

STAGE = "CRM Deal Status"
FIELD = "analytics_forecast_category"


def _ensure_editor():
	if not company_plan_editor() or not frappe.has_permission(STAGE, "write"):
		frappe.throw(_("Only system managers may configure forecast categories."), frappe.PermissionError)


def _item(row):
	return {"key": row.get("name"), "label": row.get("deal_status"), "pipeline": row.get("pipeline"),
		"category": row.get(FIELD) or "", "version": str(row.get("modified"))}


@frappe.whitelist(methods=["GET"])
@coherent_read
def get_settings():
	if not company_plan_editor():
		return {"can_edit": False, "stages": []}
	_ensure_editor()
	rows, fields = readable_rows(STAGE, ["name", "deal_status", "pipeline", "position", "modified", FIELD],
		{"type": ["in", sorted(OPEN)], "archived": 0})
	required = {"name", "deal_status", "pipeline", "modified", FIELD}
	if not required <= fields:
		return {"can_edit": False, "stages": []}
	rows.sort(key=lambda row: (row["pipeline"], row.get("position") or 0, row["deal_status"], row["name"]))
	return {"can_edit": True, "viewer": frappe.session.user, "stages": [_item(row) for row in rows]}


@frappe.whitelist(methods=["POST"])
def save_setting(stage: str, category: str, version: str, expected_viewer: str):
	_ensure_editor()
	if expected_viewer != frappe.session.user:
		frappe.throw(_("Reload analytics after switching users."), frappe.PermissionError)
	if category not in ("", *FORECAST_CATEGORIES):
		frappe.throw(_("Choose a valid forecast category."), frappe.ValidationError)
	doc = frappe.get_doc(STAGE, stage, for_update=True)
	doc.check_permission("write")
	if doc.type not in OPEN or doc.archived:
		frappe.throw(_("Choose an active open stage."), frappe.ValidationError)
	if FIELD not in doc.meta.get_valid_columns():
		frappe.throw(_("Forecast categories are unavailable on this site."), frappe.ValidationError)
	if (doc.get(FIELD) or "") == category:
		return _item(doc)
	if version != str(doc.modified):
		frappe.throw(_("This stage has changed. Reload its settings."), frappe.TimestampMismatchError)
	doc.set(FIELD, category)
	doc.save()
	return _item(doc)
