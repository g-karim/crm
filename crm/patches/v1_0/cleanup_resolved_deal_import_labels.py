import frappe


def execute():
	if not frappe.db.table_exists("CRM Deal"):
		return

	clear_matching_pipeline_labels()
	clear_matching_status_labels()
	log_unresolved_labels()


def clear_matching_pipeline_labels():
	if not frappe.db.has_column("CRM Deal", "pipeline_label"):
		return

	frappe.db.sql(
		"""
		update `tabCRM Deal` deal
		left join `tabCRM Sales Pipeline` pipeline
			on pipeline.name = deal.pipeline
		set deal.pipeline_label = null
		where coalesce(deal.pipeline_label, '') != ''
			and coalesce(deal.pipeline, '') != ''
			and (
				deal.pipeline_label = deal.pipeline
				or deal.pipeline_label = pipeline.pipeline_name
			)
		"""
	)


def clear_matching_status_labels():
	if not frappe.db.has_column("CRM Deal", "status_label"):
		return

	frappe.db.sql(
		"""
		update `tabCRM Deal` deal
		left join `tabCRM Deal Status` status
			on status.name = deal.status
		set deal.status_label = null
		where coalesce(deal.status_label, '') != ''
			and coalesce(deal.status, '') != ''
			and (
				deal.status_label = deal.status
				or deal.status_label = status.deal_status
			)
		"""
	)


def log_unresolved_labels():
	remaining = frappe.db.sql(
		"""
		select
			sum(case when coalesce(pipeline_label, '') != '' then 1 else 0 end) as pipeline_labels,
			sum(case when coalesce(status_label, '') != '' then 1 else 0 end) as status_labels
		from `tabCRM Deal`
		""",
		as_dict=True,
	)[0]

	if remaining.pipeline_labels or remaining.status_labels:
		frappe.logger("crm.patches").warning(
			"Unresolved CRM Deal import labels after cleanup: "
			f"pipeline_label={remaining.pipeline_labels or 0}, "
			f"status_label={remaining.status_labels or 0}"
		)
