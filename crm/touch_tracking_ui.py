"""Permission-checked settings, list ordering and minimal touch explanations."""

import json

import frappe
from frappe.model import get_permitted_fields
from frappe.utils import cint, get_absolute_url, get_datetime
from pypika import Order
from pypika.functions import Coalesce

from crm import touch_tracking as touch
from crm.touch_tracking_channels import CHANNEL_RULES, capabilities
from crm.touch_tracking_internal import ADDITIONAL_POLICY_FIELDS, available_fields, selections

DEFAULT_ORDER = "last_touch_at desc, creation desc, name desc"
RULE_LABELS = {
	"comment_created": "New comment",
	"comment_edited": "Comment edited",
	"note_created": "New note",
	"note_edited": "Note edited",
	"task_created": "New task",
	"task_completed": "Task completed",
	"task_status": "Task status changed",
	"task_due_date": "Task deadline changed",
	"task_start_date": "Task start date changed",
	"task_priority": "Task priority changed",
	"task_assigned_to": "Task assignee changed",
	"task_title": "Task title changed",
	"task_description": "Task description changed",
	"task_comment": "New task comment",
}


def enabled_for(doctype):
	if doctype not in touch.TARGETS or not frappe.get_meta(doctype).has_field(touch.FIELD):
		return False
	try:
		return bool(
			touch.policy_accepts(frappe.get_cached_doc(touch.SETTINGS), doctype, "Created")
			and touch.FIELD in get_permitted_fields(doctype)
		)
	except frappe.DoesNotExistError:
		return False  # Code may be present before site migration.


def default_order(doctype):
	return DEFAULT_ORDER if enabled_for(doctype) else "modified desc"


def resolve_order(doctype, order_by, view):
	if not view.get("default_sort"):
		return order_by or "modified desc"
	# A stored choice always wins, including a standard view saved by the user.
	if view.get("custom_view_name") and order_by:
		stored = frappe.db.get_value(
			"CRM View Settings",
			{"name": view["custom_view_name"], "dt": doctype},
			["order_by", "is_standard", "user"],
			as_dict=True,
		)
		if (
			stored
			and stored.user in ("", None, frappe.session.user)
			and (stored.order_by or not stored.is_standard)
		):
			return stored.order_by or order_by or "modified desc"
	if order_by and order_by not in ("modified desc", DEFAULT_ORDER):
		return order_by
	if order_by and not view.get("custom_view_name"):
		stored = frappe.db.get_value(
			"CRM View Settings",
			{
				"dt": doctype,
				"type": view.get("view_type") or "list",
				"is_standard": 1,
				"user": frappe.session.user,
			},
			"order_by",
		)
		if stored:
			return stored
	return default_order(doctype)


def list_records(doctype, *, fields, filters, order_by, page_length, start=0):
	parts = [part.strip().split() for part in (order_by or "").split(",")]
	if doctype not in touch.TARGETS or not any(part and part[0] == touch.FIELD for part in parts):
		return frappe.get_list(
			doctype, fields=fields, filters=filters, order_by=order_by, page_length=page_length, start=start
		)
	permitted = set(get_permitted_fields(doctype))
	if touch.FIELD not in permitted or "creation" not in permitted:
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	# Framework query builder keeps document/user/hierarchy and field permissions.
	# Expressions are built from validated field names, never client SQL strings.
	query = frappe.qb.get_query(
		doctype,
		fields=fields,
		filters=filters,
		limit=cint(page_length) if page_length is not None else None,
		offset=cint(start),
		ignore_permissions=False,
	)
	table = frappe.qb.DocType(doctype)
	seen = set()
	for part in parts:
		if len(part) != 2 or part[0] not in permitted or part[1].lower() not in ("asc", "desc"):
			frappe.throw(frappe._("Invalid touch sort"))
		name, direction = part
		seen.add(name)
		field = Coalesce(table[touch.FIELD], table.creation) if name == touch.FIELD else table[name]
		query = query.orderby(field, order=Order.asc if direction.lower() == "asc" else Order.desc)
	for name in ("creation", "name"):
		if name not in seen:
			query = query.orderby(table[name], order=Order.desc)
	return query.run(as_dict=True)


def _settings_permission():
	if not {"System Manager", "Sales Manager"}.intersection(frappe.get_roles()):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	frappe.get_doc(touch.SETTINGS).check_permission("write")


@frappe.whitelist()
def get_settings() -> dict:
	_settings_permission()
	doc = frappe.get_doc(touch.SETTINGS)
	values = {field: doc.get(field) for field in (*touch.POLICY_FIELDS, *ADDITIONAL_POLICY_FIELDS)}
	for prefix in ("lead", "deal"):
		for suffix in ("fields", "events", "channels"):
			values[f"{prefix}_{suffix}"] = selections(values[f"{prefix}_{suffix}"])
	return {
		"settings": values,
		"modified": str(get_datetime(doc.modified)) if doc.modified else "",
		"fields": {
			dt: [
				{"value": name, "label": frappe._(field.label or name)}
				for name, field in available_fields(dt).items()
			]
			for dt in touch.TARGETS
		},
		"events": [{"value": key, "label": frappe._(label)} for key, label in RULE_LABELS.items()],
		"channels": _channel_capabilities(),
	}


@frappe.whitelist()
def save_settings(settings: dict, expected_modified: str) -> dict:
	_settings_permission()
	settings = frappe.parse_json(settings)
	allowed = set((*touch.POLICY_FIELDS, *ADDITIONAL_POLICY_FIELDS))
	if not isinstance(settings, dict) or set(settings) - allowed:
		frappe.throw(frappe._("Invalid touch settings"))
	doc = frappe.get_doc(touch.SETTINGS, for_update=True)
	if (str(get_datetime(doc.modified)) if doc.modified else "") != (
		str(get_datetime(expected_modified)) if expected_modified else ""
	):
		frappe.throw(frappe._("Settings changed. Reload before saving."), frappe.TimestampMismatchError)
	for field, value in settings.items():
		doc.set(
			field,
			json.dumps(value)
			if field.endswith(("_fields", "_events", "_channels")) and isinstance(value, list)
			else value,
		)
	doc.save()
	return get_settings()


def _channel_capabilities():
	return [
		{
			**channel,
			"label": frappe._(channel["label"]),
			"description": frappe._(channel["description"]),
			"rules": [
				{
					"value": key,
					"label": frappe._(CHANNEL_RULES[key]),
					"available": bool(channel["available"] or key == "call_manual"),
				}
				for key in channel["rules"]
			],
		}
		for channel in capabilities()
	]


@frappe.whitelist()
def get_reason(doctype: str, name: str) -> dict:
	if doctype not in touch.TARGETS:
		frappe.throw(frappe._("Unsupported touch target"))
	parent = frappe.get_doc(doctype, name)
	parent.check_permission("read")
	if touch.FIELD not in get_permitted_fields(doctype):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	date = parent.get(touch.FIELD)
	if not date:
		return {
			"date": parent.creation,
			"reasons": [frappe._("Creation date; no recorded interaction")],
			"source": None,
		}
	rows = frappe.get_all(
		touch.EVENT,
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"occurred_at": date,
			"state": "Applied",
		},
		fields=["*"],
		order_by="name desc",
		limit_page_length=1,
	)
	if not rows:
		return {"date": date, "reasons": [frappe._("Initial date; no recorded reason")], "source": None}
	event = rows[0]
	if not _can_read_source(event, parent):
		return {"date": date, "reasons": [frappe._("Interaction details are unavailable")], "source": None}
	reasons = selections(event.reasons) or (
		["created"] if event.event_type == "Created" else ["status_changed"]
	)
	permitted = set(get_permitted_fields(doctype))
	labels = []
	for reason in reasons:
		if reason.startswith("field:"):
			fieldname = reason.removeprefix("field:")
			if fieldname not in permitted:
				continue
			field = parent.meta.get_field(fieldname)
			labels.append(
				frappe._("Field changed: {0}").format(frappe._(field.label if field else fieldname))
			)
		else:
			if reason == "status_changed" and "status" not in permitted:
				continue
			label = {
				"created": "Record created",
				"status_changed": "Status changed",
				**RULE_LABELS,
				**CHANNEL_RULES,
			}.get(reason)
			if label:
				labels.append(frappe._(label))
	if not labels:
		return {"date": date, "reasons": [frappe._("Interaction details are unavailable")], "source": None}
	source_type, source_name = event.source_doctype, event.source_name
	if source_type == "CRM Status Change Log":
		source_type, source_name = doctype, name
	return {
		"date": date,
		"reasons": labels,
		"source": {
			"url": get_absolute_url(source_type, source_name),
			"label": frappe._("Open source record"),
		},
	}


def _can_read_source(event, parent):
	if event.source_doctype == "CRM Status Change Log":
		return bool(
			frappe.db.exists(
				event.source_doctype,
				{"name": event.source_name, "parent": parent.name, "parenttype": parent.doctype},
			)
		)
	if event.source_doctype not in (
		*touch.TARGETS,
		"Comment",
		"FCRM Note",
		"CRM Task",
		"ToDo",
		"Communication",
		"CRM Call Log",
		"Messenger Message",
	):
		return False
	if not frappe.db.exists(event.source_doctype, event.source_name):
		return False
	source = frappe.get_doc(event.source_doctype, event.source_name)
	if not frappe.has_permission(source.doctype, "read", doc=source):
		return False
	# Linked sources may have moved to a different/private card since the event.
	dt = source.get("reference_doctype") or source.get("reference_type")
	nm = source.get("reference_docname") or source.get("reference_name")
	if source.doctype == "Messenger Message":
		if not frappe.db.exists("Messenger Conversation", source.conversation):
			return False
		conversation = frappe.get_doc("Messenger Conversation", source.conversation)
		if not frappe.has_permission(conversation.doctype, "read", doc=conversation):
			return False
		dt, nm = conversation.reference_doctype, conversation.reference_name
	if dt == "CRM Task" and nm:
		if not frappe.db.exists(dt, nm):
			return False
		task = frappe.get_doc(dt, nm)
		if not frappe.has_permission(dt, "read", doc=task):
			return False
		dt, nm = task.reference_doctype, task.reference_docname
	if dt in touch.TARGETS and nm:
		return bool(
			frappe.db.exists(dt, nm) and frappe.has_permission(dt, "read", doc=frappe.get_doc(dt, nm))
		)
	return source.doctype in touch.TARGETS
