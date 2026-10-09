import frappe
from frappe.model.document import Document


class CRMTouchReceipt(Document):
	def validate(self):
		if not self.flags.touch_internal:
			frappe.throw(frappe._("Touch receipts are managed by the server"), frappe.PermissionError)
		from crm.touch_tracking_channels import identity

		self.name = identity(self.source_doctype, self.source_name)
		previous = self.get_doc_before_save()
		if previous:
			fixed = (
				"source_doctype",
				"source_name",
				"reference_doctype",
				"reference_name",
				"adapter",
				"origin",
				"actor",
				"bound_at",
				"event_source_doctype",
				"event_source_name",
				"provider_started_at",
				"provider_timezone",
				"provider_agent_id",
				"provider_phone_key",
				"provider_call_key",
			)
			if previous.occurred_at:
				fixed += ("rule", "occurred_at", "confirmation_key", "policy_revision", "change_name")
			if any(self.get(field) != previous.get(field) for field in fixed):
				frappe.throw(frappe._("Confirmed touch receipts are immutable"))
