import frappe


LEAD_STATUS_FIELDS = ["name", "color", "position", "type"]
DEAL_STATUS_FIELDS = [
	"name",
	"deal_status",
	"pipeline",
	"color",
	"position",
	"type",
	"archived",
]
COMMUNICATION_STATUS_FIELDS = ["name"]


@frappe.whitelist()
def get_lead_statuses():
	return frappe.get_list(
		"CRM Lead Status",
		fields=LEAD_STATUS_FIELDS,
		order_by="position asc",
		limit_page_length=0,
	)


@frappe.whitelist()
def get_deal_statuses():
	return frappe.get_list(
		"CRM Deal Status",
		fields=DEAL_STATUS_FIELDS,
		order_by="position asc",
		limit_page_length=0,
	)


@frappe.whitelist()
def get_communication_statuses():
	return frappe.get_list(
		"CRM Communication Status",
		fields=COMMUNICATION_STATUS_FIELDS,
		limit_page_length=0,
	)
