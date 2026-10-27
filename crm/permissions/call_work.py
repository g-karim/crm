"""Keep source-owned call work behind its customer in native CRUD and lists too.

Legacy records without an operation receipt retain their existing permissions.
Task-operation records already use this context rule in the source task API.
"""
import frappe

TARGETS = ("CRM Lead", "CRM Deal")


def _condition(doctype, receipt, field, user=None):
	if not frappe.db.table_exists(receipt):
		return ""
	user = user or frappe.session.user
	table = f"`tab{doctype}`"
	allowed = [
		f"NOT EXISTS (SELECT 1 FROM `tab{receipt}` work_receipt WHERE work_receipt.`{field}` = {table}.`name`)",
		f"COALESCE({table}.`reference_docname`, '') = ''",
		f"COALESCE({table}.`reference_doctype`, '') NOT IN ('CRM Lead', 'CRM Deal')",
	]
	for target in TARGETS:
		if frappe.has_permission(target, "read", user=user):
			query = frappe.qb.get_query(target, fields=["name"], ignore_permissions=False, user=user)
			allowed.append(f"({table}.`reference_doctype` = {frappe.db.escape(target)} AND {table}.`reference_docname` IN ({query.get_sql()}))")
	return "(" + " OR ".join(allowed) + ")"


def _permission(doc, receipt, field, user=None):
	if (doc.reference_doctype in TARGETS and doc.reference_docname and frappe.db.table_exists(receipt)
		and frappe.db.exists(receipt, {field: doc.name})
		and not frappe.has_permission(doc.reference_doctype, "read", doc.reference_docname, user=user or frappe.session.user)):
		return False
	return True  # This hook is a veto; Frappe evaluates roles/owner rules afterward.


def note_query(user=None):
	return _condition("FCRM Note", "CRM Note Operation", "note", user)


def task_query(user=None):
	return _condition("CRM Task", "CRM Task Operation", "task", user)


def note_permission(doc, ptype, user=None):
	return _permission(doc, "CRM Note Operation", "note", user)


def task_permission(doc, ptype, user=None):
	return _permission(doc, "CRM Task Operation", "task", user)
