from frappe.model.document import Document

from crm.analytics.goals import validate_document


class CRMAnalyticsGoal(Document):
	def validate(self):
		validate_document(self)
