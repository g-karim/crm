import frappe
from frappe import _


def reject_lead_share(doc, method=None):
	# Lead visibility follows the owner and open ToDo assignments only.
	if doc.share_doctype == "CRM Lead":
		frappe.throw(
			_("CRM Lead access is controlled by assignments, not document shares."),
			frappe.PermissionError,
		)
