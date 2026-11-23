from frappe.model.document import Document


class CRMAnalyticsBoard(Document):
	def validate(self):
		from crm.analytics.boards import validate_document

		validate_document(self)
