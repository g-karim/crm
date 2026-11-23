from frappe.model.document import Document

from crm.analytics.signals import validate_document


class CRMAnalyticsMonitor(Document):
	def validate(self):
		validate_document(self)
