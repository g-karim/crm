"""Analytics charts and versioned shared layouts."""
import json

import frappe
from frappe import _

from crm.analytics import legacy
from crm.analytics.service import calculate, coherent_read
from crm.api.dashboard import CONTRIBUTABLE_CHART_TYPES, get_contributed_charts
from crm.api.dashboard import get_core_chart_options as get_standard_options
from crm.fcrm.doctype.crm_dashboard.crm_dashboard import default_manager_dashboard_layout
from crm.utils import sales_user_only

DEFAULT_LAYOUT_NAME = "Manager Dashboard"


def get_core_chart_options():
	options = get_standard_options()
	options["axis_chart"].append({"label": _("Open Value by Pipeline"), "value": "open_value_by_pipeline"})
	return options


@frappe.whitelist()
@sales_user_only
def get_chart_options():
	"""
	Return the selectable options for the "Add Chart" dialog, grouped by chart
	type — CRM's own built-in charts plus anything contributed via the
	crm_dashboard_charts hook.
	"""
	options = get_core_chart_options()
	contributed = get_contributed_charts()
	for chart_type in CONTRIBUTABLE_CHART_TYPES:
		options[chart_type] = options[chart_type] + [
			{"label": option["label"], "value": option["value"]} for option in contributed[chart_type]
		]
	return options


def _layout():
	if frappe.db.exists("CRM Dashboard", DEFAULT_LAYOUT_NAME):
		doc = frappe.get_doc("CRM Dashboard", DEFAULT_LAYOUT_NAME)
		return json.loads(doc.layout or "[]"), str(doc.modified)
	return json.loads(default_manager_dashboard_layout()), None


def _core_names():
	return {
		option["value"]
		for kind, options in get_core_chart_options().items()
		if kind != "chart_types"
		for option in options
	}


def _additional_chart(option, context):
	roles = set(frappe.get_roles())
	owner = context.owner
	if "Sales User" in roles and not roles.intersection({"Sales Manager", "System Manager"}):
		owner = frappe.session.user
	try:
		return frappe.get_attr(option["resolver"])(str(context.period.start), str(context.period.end), owner)
	except Exception:
		return {"unavailable": True, "message": _("Additional chart could not be loaded.")}


@frappe.whitelist()
@sales_user_only
@coherent_read
def get_dashboard_state(
	from_date: str | None = None, to_date: str | None = None,
	user: str | None = None, days: int | None = None,
):
	context = legacy.context(from_date, to_date, user, days=days)
	report, sources = calculate(context, include_source_revision=False)
	layout, modified = _layout()
	contributed = {o["value"]: o for options in get_contributed_charts().values() for o in options}
	core = _core_names()
	for item in layout:
		name = item.get("name")
		if item.get("type") == "spacer":
			item["data"] = None
		elif name in core:
			item["data"] = legacy.chart(name, report, sources, context)
		elif name in contributed:
			item["data"] = _additional_chart(contributed[name], context)
		else:
			item["data"] = {"unavailable": True, "message": _("This chart is unavailable.")}
	return {"items": layout, "modified": modified, "context": context.metadata()}


@frappe.whitelist()
@sales_user_only
@coherent_read
def get_chart(
	name: str, type: str, from_date: str | None = None,
	to_date: str | None = None, user: str | None = None,
):
	options = get_chart_options()
	if type not in CONTRIBUTABLE_CHART_TYPES or name not in {o["value"] for o in options[type]}:
		return {"error": _("Invalid chart name")}
	context = legacy.context(from_date, to_date, user)
	if name in _core_names():
		report, sources = calculate(context, include_source_revision=False)
		return legacy.chart(name, report, sources, context)
	for option in get_contributed_charts()[type]:
		if option["value"] == name:
			return _additional_chart(option, context)
	return {"error": _("Invalid chart name")}


@frappe.whitelist(methods=["POST"])
def save_layout(layout: str | list, modified: str | None = None):
	frappe.only_for("System Manager", True)
	parsed = frappe.parse_json(layout) if isinstance(layout, str) else layout
	if not isinstance(parsed, list) or len(parsed) > 100:
		frappe.throw(_("Invalid dashboard layout."), frappe.ValidationError)
	options = get_chart_options()
	for item in parsed:
		if not isinstance(item, dict) or set(item) - {"name", "type", "tooltip", "layout"}:
			frappe.throw(_("Invalid dashboard item."), frappe.ValidationError)
		kind = item.get("type")
		if kind == "spacer":
			continue
		if kind not in CONTRIBUTABLE_CHART_TYPES or item.get("name") not in {o["value"] for o in options[kind]}:
			frappe.throw(_("Invalid chart name"), frappe.ValidationError)

	current_version = _layout()[1]
	if modified != current_version:
		frappe.throw(_("The layout changed. Reload before saving."), frappe.TimestampMismatchError)
	if current_version:
		doc = frappe.get_doc("CRM Dashboard", DEFAULT_LAYOUT_NAME)
		doc.layout = json.dumps(parsed)
		doc.save()
	else:
		doc = frappe.get_doc({
			"doctype": "CRM Dashboard", "title": DEFAULT_LAYOUT_NAME, "layout": json.dumps(parsed),
		}).insert()
	return {"modified": str(doc.modified)}


@frappe.whitelist(methods=["POST"])
def reset_to_default(modified: str | None = None):
	return save_layout(default_manager_dashboard_layout(), modified)
