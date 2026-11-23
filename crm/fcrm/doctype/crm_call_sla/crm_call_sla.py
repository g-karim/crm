from frappe.model.document import Document


class CRMCallSLA(Document):
	def validate(self):
		from crm.analytics.call_sla_settings import validate_schedule

		validate_schedule(self.timezone, self.weekdays, self.work_start, self.work_end, self.response_minutes)
