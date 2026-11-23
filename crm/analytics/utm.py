"""UTM dimensions shared by CRM source records and marketing expenses."""

import frappe
from frappe import _
from frappe.model import get_permitted_fields

UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign")


def clean_tag(value):
	if value is None:
		return ""
	if not isinstance(value, str):
		frappe.throw(_("Use text for UTM values."), frappe.ValidationError)
	value = value.strip()
	if len(value) > 120 or (value and not value.isprintable()):
		frappe.throw(_("Use a single line of up to 120 characters per UTM value."), frappe.ValidationError)
	return value


def clean_document_tags(doc):
	for field in UTM_FIELDS:
		if doc.get(field) is not None:
			doc.set(field, clean_tag(doc.get(field)))


def readable_tags(doctype):
	meta = frappe.get_meta(doctype)
	return set(UTM_FIELDS) & (
		set(get_permitted_fields(doctype, permission_type="read"))
		- {field.fieldname for field in meta.get_masked_fields()}
	)
