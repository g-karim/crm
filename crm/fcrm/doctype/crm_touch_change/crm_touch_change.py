import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

from crm.touch_tracking import TARGETS, event_key
from crm.touch_tracking_internal import INTERNAL_EVENTS, selections


class CRMTouchChange(Document):
	def validate(self):
		if not self.is_new() or not self.flags.touch_internal:
			frappe.throw(frappe._("Touch changes are managed by the server"), frappe.PermissionError)
		if self.reference_doctype not in TARGETS or self.event_type not in (
			"Status Changed",
			"Internal Changed",
			"Channel Interaction",
		):
			frappe.throw(frappe._("Unsupported touch change"))
		if get_datetime(self.occurred_at) > now_datetime():
			frappe.throw(frappe._("Touch source timestamp is in the future"))
		from crm.touch_tracking_channels import CHANNEL_RULES

		reasons = selections(self.reasons)
		if not reasons or any(
			reason not in (*INTERNAL_EVENTS, *CHANNEL_RULES)
			and reason != "status_changed"
			and not reason.startswith("field:")
			for reason in reasons
		):
			frappe.throw(frappe._("Invalid touch change reasons"))
		self.name = event_key(
			self.reference_doctype,
			self.reference_name,
			self.event_type,
			self.source_doctype,
			self.source_name,
			self.source_revision,
		)
