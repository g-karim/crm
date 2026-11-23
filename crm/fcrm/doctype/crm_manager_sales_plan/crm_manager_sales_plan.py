import frappe
from frappe.model.document import Document


class CRMManagerSalesPlan(Document):
	def validate(self):
		from crm.analytics.sales_plans import plan_name, validate_targets

		month = frappe.utils.getdate(self.month_start)
		if month.day != 1 or self.name != plan_name(self.manager, month):
			frappe.throw(frappe._("The manager and month of a sales plan cannot change."))
		before = self.get_doc_before_save()
		if before and (self.manager != before.manager or month != frappe.utils.getdate(before.month_start)):
			frappe.throw(frappe._("The manager and month of a sales plan cannot change."))
		validate_targets(self.target_amount or None, self.target_wins or None, precision=6)
