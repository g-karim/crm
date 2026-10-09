import frappe
from frappe.model.document import Document

from crm.touch_tracking import TARGETS, event_key


class CRMTouchEvent(Document):
	def validate(self):
		if not self.is_new() or not self.flags.touch_internal:
			frappe.throw(frappe._("Touch events are managed by the server"), frappe.PermissionError)
		if self.reference_doctype not in TARGETS or self.event_type not in (
			"Created",
			"Status Changed",
			"Internal Changed",
			"Channel Interaction",
		):
			frappe.throw(frappe._("Unsupported touch event"))
		self.name = event_key(
			self.reference_doctype,
			self.reference_name,
			self.event_type,
			self.source_doctype,
			self.source_name,
			self.source_revision,
		)
