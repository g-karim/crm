from crm.install import add_field_to_fields_layout


def execute():
	add_field_to_fields_layout(
		"CRM Deal-Quick Entry",
		"deal_section",
		"deal_name",
		"pipeline",
		before=True,
	)
	add_field_to_fields_layout(
		"CRM Deal-Side Panel",
		"organization_section",
		"deal_name",
		"organization",
		before=True,
	)
	add_field_to_fields_layout(
		"CRM Deal-Data Fields",
		"details_section",
		"deal_name",
		"organization",
		before=True,
	)
