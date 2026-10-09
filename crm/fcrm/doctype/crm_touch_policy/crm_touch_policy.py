import frappe
from frappe.model.document import Document


class CRMTouchPolicy(Document):
	def validate(self):
		if not self.is_new() or not self.flags.touch_internal:
			frappe.throw(frappe._("Touch policies are managed by CRM Touch Settings"), frappe.PermissionError)
		if not self.effective_from:
			frappe.throw(frappe._("A touch policy requires an effective time"))
