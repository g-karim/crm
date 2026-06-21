import frappe


def execute():
	frappe.reload_doc("fcrm", "doctype", "crm_sales_pipeline")

	frappe.db.sql(
		"""
		update `tabCRM Sales Pipeline`
		set
			stage_skip_rule = if(
				coalesce(stage_skip_rule, '') = '',
				if(coalesce(warn_on_stage_skip, 0) = 1, 'Warn', 'Allow'),
				stage_skip_rule
			),
			stage_backwards_rule = if(
				coalesce(stage_backwards_rule, '') = '',
				if(coalesce(warn_on_stage_backwards, 0) = 1, 'Warn', 'Allow'),
				stage_backwards_rule
			),
			closing_fields_rule = if(
				coalesce(closing_fields_rule, '') = '',
				if(coalesce(warn_on_closing_without_required_fields, 0) = 1, 'Warn', 'Allow'),
				closing_fields_rule
			)
		"""
	)
