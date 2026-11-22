"""Apply the customer record's read restrictions to tasks saved through the adapter."""

import frappe

from crm.api.celio_tasks import CONTEXTS


def task_query(user=None):
	if not frappe.db.table_exists("CRM Task Operation"):
		return ""
	user = user or frappe.session.user
	task = frappe.qb.DocType("CRM Task")
	receipt = frappe.qb.DocType("CRM Task Operation")
	customer_types = [doctype for doctype, _label in CONTEXTS.values()]
	# Pre-existing tasks follow their original CRM rules. For tasks managed by the
	# adapter, intersect those rules with the linked customer's native list access.
	allowed = (
		task.name.notin(frappe.qb.from_(receipt).select(receipt.task))
		| task.reference_docname.isnull()
		| (task.reference_docname == "")
		| task.reference_doctype.isnull()
		| task.reference_doctype.notin(customer_types)
	)
	for doctype in customer_types:
		if frappe.has_permission(doctype, "read", user=user):
			customers = frappe.qb.get_query(doctype, fields=["name"], ignore_permissions=False, user=user)
			allowed |= (task.reference_doctype == doctype) & task.reference_docname.isin(customers)
	return allowed.get_sql(with_namespace=True, quote_char="`", secondary_quote_char="'")


def task_permission(doc, ptype, user=None):
	if not doc.reference_docname or doc.reference_doctype not in {dt for dt, _label in CONTEXTS.values()}:
		return True
	if not frappe.db.table_exists("CRM Task Operation") or not frappe.db.exists(
		"CRM Task Operation", {"task": doc.name}
	):
		return True
	return frappe.has_permission(doc.reference_doctype, "read", doc.reference_docname, user=user)
