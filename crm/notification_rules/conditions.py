"""Bounded AND predicates over readable CRM scalar fields; never executes expressions."""

from decimal import Decimal, InvalidOperation

import frappe
from frappe.model import get_permitted_fields
from frappe.utils import get_datetime

NUMBER = {"Int", "Float", "Currency", "Percent"}
TEXT = {"Data", "Small Text", "Link", "Select"}
DATES = {"Date", "Datetime"}
OPS = {
	"number": {"eq", "neq", "gt", "gte", "lt", "lte", "is_set", "is_not_set"},
	"text": {"eq", "neq", "contains", "not_contains", "in", "not_in", "is_set", "is_not_set"},
	"date": {"eq", "neq", "gt", "gte", "lt", "lte", "is_set", "is_not_set"},
	"check": {"eq", "neq"},
	"tags": {"contains_any", "contains_all", "contains_none"},
}


def invalid():
	frappe.throw(frappe._("Check the advanced notification conditions."))


def fields(doctype, user):
	if not frappe.has_permission(doctype, "read", user=user):
		return []
	permitted = set(get_permitted_fields(doctype, user=user, permission_type="read"))
	result = []
	for field in frappe.get_meta(doctype).fields:
		kind = (
			"number"
			if field.fieldtype in NUMBER
			else "text"
			if field.fieldtype in TEXT
			else "date"
			if field.fieldtype in DATES
			else "check"
			if field.fieldtype == "Check"
			else None
		)
		if not kind or field.fieldname not in permitted or field.get("hidden") or field.get("is_virtual"):
			continue
		result.append(
			{
				"value": field.fieldname,
				"label": frappe._(field.label or field.fieldname),
				"kind": kind,
				"operators": sorted(OPS[kind]),
				"fieldtype": field.fieldtype,
				"options": field.options.splitlines() if field.fieldtype == "Select" else [],
			}
		)
	if frappe.db.has_column(doctype, "_user_tags"):
		result.append(
			{
				"value": "_user_tags",
				"label": frappe._("Tags"),
				"kind": "tags",
				"operators": sorted(OPS["tags"]),
				"options": [],
			}
		)
	return result


def _number(value):
	if type(value) not in {str, int, float} or len(str(value)) > 64:
		invalid()
	try:
		number = Decimal(str(value))
		if not number.is_finite():
			raise InvalidOperation
		return number
	except (InvalidOperation, ValueError):
		invalid()


def validate(conditions, doctype, user):
	if not isinstance(conditions, list) or len(conditions) > 12:
		invalid()
	available = {row["value"]: row for row in fields(doctype, user)}
	result = []
	for condition in conditions:
		if not isinstance(condition, dict) or set(condition) != {"field", "operator", "value"}:
			invalid()
		field = available.get(condition["field"]) if isinstance(condition["field"], str) else None
		operator, value = condition["operator"], condition["value"]
		if not field or not isinstance(operator, str) or operator not in field["operators"]:
			invalid()
		if operator in {"is_set", "is_not_set"}:
			if value is not None:
				invalid()
		elif operator in {"in", "not_in", "contains_any", "contains_all", "contains_none"}:
			if not isinstance(value, list) or not 1 <= len(value) <= 30:
				invalid()
			if any(not isinstance(v, str) or not v or len(v) > 140 for v in value):
				invalid()
		elif field["kind"] == "number":
			_number(value)
		elif field["kind"] == "check":
			if type(value) is not bool:
				invalid()
		elif field["kind"] == "date":
			try:
				if not isinstance(value, str) or not value or len(value) > 30:
					raise ValueError
				get_datetime(value)
			except (ValueError, TypeError):
				invalid()
		elif not isinstance(value, str) or len(value) > 300:
			invalid()
		if field["options"] and operator not in {"is_set", "is_not_set", "contains", "not_contains"}:
			values = value if isinstance(value, list) else [value]
			if any(v not in field["options"] for v in values):
				invalid()
		result.append(dict(condition))
	return result


def _matches(actual, operator, expected, kind):
	if operator == "is_set":
		return actual is not None and actual != ""
	if operator == "is_not_set":
		return actual is None or actual == ""
	if kind == "tags":
		tags = {tag.strip() for tag in (actual or "").split(",") if tag.strip()}
		wanted = set(expected)
		return (
			bool(tags & wanted)
			if operator == "contains_any"
			else wanted <= tags
			if operator == "contains_all"
			else not bool(tags & wanted)
		)
	if actual is None:
		return False
	if kind == "number":
		actual, expected = _number(actual), _number(expected)
	elif kind == "date":
		actual, expected = get_datetime(actual), get_datetime(expected)
	elif kind == "check":
		actual = bool(actual)
	if operator == "eq":
		return actual == expected
	if operator == "neq":
		return actual != expected
	if operator == "gt":
		return actual > expected
	if operator == "gte":
		return actual >= expected
	if operator == "lt":
		return actual < expected
	if operator == "lte":
		return actual <= expected
	if operator == "contains":
		return expected.casefold() in str(actual).casefold()
	if operator == "not_contains":
		return expected.casefold() not in str(actual).casefold()
	if operator == "in":
		return actual in expected
	if operator == "not_in":
		return actual not in expected
	return False


def matches(rule, facts, user):
	conditions = rule.get("conditions", [])
	if not conditions:
		return True
	available = {row["value"]: row for row in fields(facts["object"], user)}
	doc = frappe.get_doc(facts["object"], facts["record_id"])
	for condition in conditions:
		field = available.get(condition.get("field"))
		if not field or condition.get("operator") not in field["operators"]:
			return False  # Field deletion, hiding or a permission change cancels delivery.
		try:
			if not _matches(
				doc.get(field["value"]), condition["operator"], condition["value"], field["kind"]
			):
				return False
		except (ValueError, TypeError, InvalidOperation):
			return False
	return True
