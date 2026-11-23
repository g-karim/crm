from frappe.model.document import Document

from crm.analytics.marketing import validate_spend


class CRMCampaignSpend(Document):
	def validate(self):
		validate_spend(self)
