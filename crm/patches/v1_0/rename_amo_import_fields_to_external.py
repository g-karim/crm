import frappe


def execute():
	copy_if_columns_exist(
		"CRM Sales Pipeline",
		{
			"amo_pipeline_id": "external_pipeline_id",
		},
		source_value="amocrm",
	)
	copy_if_columns_exist(
		"CRM Deal Status",
		{
			"amo_pipeline_id": "external_pipeline_id",
			"amo_status_id": "external_status_id",
		},
		source_value="amocrm",
	)
	copy_if_columns_exist(
		"CRM Deal",
		{
			"amo_pipeline_id": "external_pipeline_id",
			"amo_status_id": "external_status_id",
			"amo_lead_id": "external_record_id",
		},
		source_value="amocrm",
	)


def copy_if_columns_exist(doctype: str, field_map: dict[str, str], source_value: str):
	table = f"tab{doctype}"
	assignments = []
	old_value_conditions = []

	for old_field, new_field in field_map.items():
		if frappe.db.has_column(doctype, old_field) and frappe.db.has_column(doctype, new_field):
			assignments.append(
				f"`{new_field}` = if(coalesce(`{new_field}`, '') = '', `{old_field}`, `{new_field}`)"
			)
			old_value_conditions.append(f"coalesce(`{old_field}`, '') != ''")

	if (
		assignments
		and frappe.db.has_column(doctype, "external_source")
		and old_value_conditions
	):
		assignments.append(
			"`external_source` = if(coalesce(`external_source`, '') = '' and ("
			+ " or ".join(old_value_conditions)
			+ "), "
			+ frappe.db.escape(source_value)
			+ ", `external_source`)"
		)

	if not assignments:
		return

	frappe.db.sql(f"update `{table}` set {', '.join(assignments)}")
