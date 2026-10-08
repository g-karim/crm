"""Phone lookup and optional site-specific lead ordering."""

import re

STATUS_SORT_FIELD = "custom_crm_status_sort_date"
STATUS_SORT_LABEL = "Created or Status Changed"
PHONE_FIELDS = ("mobile_no", "phone")


def normalize_phone_filters(doctype, filters):
	"""Match numeric LIKE searches across both phone fields, ignoring separators.

	Keep non-phone searches and explicit equality filters unchanged. Return ordinary
	Frappe filter expressions with explicit field checks; get_list still applies
	document permissions.
	"""
	if doctype not in ("CRM Lead", "CRM Deal") or not filters:
		return filters

	conditions = []
	changed = False
	if isinstance(filters, dict):
		items = [
			[field, *value] if isinstance(value, list | tuple) else [field, "=", value]
			for field, value in filters.items()
		]
	else:
		items = filters

	for condition in items:
		if not isinstance(condition, list | tuple) or len(condition) not in (3, 4):
			return filters
		field, operator, value = condition[-3:]
		pattern = phone_like_pattern(value) if str(operator).lower() == "like" else None
		if field in PHONE_FIELDS and pattern:
			conditions.append(phone_search_condition(doctype, field, pattern))
			changed = True
		else:
			conditions.append(condition)

	if not changed:
		return filters
	# Frappe ANDs ordinary filter conditions and Criteria in this list. A phone
	# Criterion contains its own OR, so status/source/name filters remain required.
	return conditions


def phone_search_condition(doctype, requested_field, pattern):
	import frappe
	from frappe.model import get_permitted_fields
	from pypika import Criterion

	permitted_fields = get_permitted_fields(doctype)
	if requested_field not in permitted_fields:
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	table = frappe.qb.DocType(doctype)
	return Criterion.any(
		[table[field].regexp(pattern) for field in PHONE_FIELDS if field in permitted_fields]
	)


def phone_like_pattern(value):
	if not isinstance(value, str):
		return None
	text = value.strip("%")
	if not re.fullmatch(r"[0-9\s()+.\-]+", text):
		return None
	digits = re.sub(r"\D", "", text)
	if not digits or len(digits) > 20:
		return None
	pattern = "[^0-9]*".join(digits)
	if not value.startswith("%"):
		pattern = "^[^0-9]*" + pattern
	if not value.endswith("%"):
		pattern += "[^0-9]*$"
	return pattern


def update_lead_sort_date(doc):
	"""Only sites that installed the optional field use this ordering."""
	if not doc.meta.has_field(STATUS_SORT_FIELD):
		return
	if doc.is_new() or doc.has_value_changed("status"):
		from frappe.utils import now_datetime

		doc.set(STATUS_SORT_FIELD, doc.get("modified") or now_datetime())
