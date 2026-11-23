"""CRM source permissions apply to selection, stored rules and delivery."""

import frappe
from frappe import _

OBJECTS = {"CRM Lead", "CRM Deal", "CRM Task"}


def readable(doctype, name, user):
	if type(name) not in {str, int}:
		return False
	name = str(name)
	if doctype not in OBJECTS or not name or len(name) > 140:
		return False
	if not frappe.db.exists(doctype, name):
		return False
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc, user=user):
		return False
	if doctype == "CRM Task" and (doc.reference_doctype or doc.reference_docname):
		return doc.reference_doctype in {"CRM Lead", "CRM Deal"} and readable(
			doc.reference_doctype, doc.reference_docname, user
		)
	return True


def require_record(doctype, name, user):
	if not readable(doctype, name, user):
		frappe.throw(_("This CRM record is not available."), frappe.PermissionError)


def require_crm(user):
	if not any(frappe.has_permission(kind, "read", user=user) for kind in OBJECTS):
		frappe.throw(_("CRM notifications are not available for your account."), frappe.PermissionError)


def title(doctype, name):
	field = "title" if doctype == "CRM Task" else frappe.get_meta(doctype).title_field or "name"
	return frappe.db.get_value(doctype, name, field) or name


def visible_configuration(values, user):
	"""A revoked selected ID must not leak through a settings response."""
	result = {"schema_version": 1, "rules": [], "records": []}
	for rule in values.get("rules", []):
		visible = [name for name in rule["record_ids"] if readable(rule["object"], name, user)]
		result["rules"].append(
			{
				**rule,
				"record_ids": visible,
				"channels": {"email": False, **rule["channels"]},
				"unavailable_selection_count": len(rule["record_ids"]) - len(visible),
			}
		)
	for record in values.get("records", []):
		if readable(record["object"], record["record_id"], user):
			result["records"].append(record)
	return result
