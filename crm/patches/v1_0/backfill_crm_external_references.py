import frappe

from crm.fcrm.doctype.crm_external_reference.crm_external_reference import (
	DEAL_EXTERNAL_DOCTYPE,
	PIPELINE_EXTERNAL_DOCTYPE,
	REFERENCE_FIELDS,
	STAGE_EXTERNAL_DOCTYPE,
	clean_value,
)


def execute():
	stats = {
		"created": 0,
		"existing": 0,
		"skipped": 0,
		"examples": [],
	}

	if not frappe.db.table_exists("CRM External Reference"):
		return stats

	backfill_sales_pipelines(stats)
	backfill_deal_statuses(stats)
	backfill_deals(stats)
	log_stats(stats)
	return stats


def backfill_sales_pipelines(stats):
	if not has_columns("CRM Sales Pipeline", ["external_source", "external_pipeline_id"]):
		return

	for row in frappe.db.sql(
		"""
		select name, external_source, external_pipeline_id
		from `tabCRM Sales Pipeline`
		where coalesce(external_source, '') != ''
			and coalesce(external_pipeline_id, '') != ''
		""",
		as_dict=True,
	):
		ensure_external_reference(
			stats,
			reference_doctype="CRM Sales Pipeline",
			reference_name=row.name,
			external_source=row.external_source,
			external_doctype=PIPELINE_EXTERNAL_DOCTYPE,
			external_id=row.external_pipeline_id,
		)


def backfill_deal_statuses(stats):
	if not has_columns(
		"CRM Deal Status",
		["pipeline", "external_source", "external_status_id", "external_pipeline_id"],
	):
		return

	for row in frappe.db.sql(
		"""
		select
			status.name,
			status.external_source,
			status.external_status_id,
			coalesce(
				nullif(status.external_pipeline_id, ''),
				case
					when pipeline.external_source = status.external_source
					then nullif(pipeline.external_pipeline_id, '')
				end
			) as external_parent_id
		from `tabCRM Deal Status` status
		left join `tabCRM Sales Pipeline` pipeline
			on pipeline.name = status.pipeline
		where coalesce(status.external_source, '') != ''
			and coalesce(status.external_status_id, '') != ''
		""",
		as_dict=True,
	):
		ensure_external_reference(
			stats,
			reference_doctype="CRM Deal Status",
			reference_name=row.name,
			external_source=row.external_source,
			external_doctype=STAGE_EXTERNAL_DOCTYPE,
			external_id=row.external_status_id,
			external_parent_id=row.external_parent_id,
		)


def backfill_deals(stats):
	if not has_columns("CRM Deal", ["external_source", "external_record_id"]):
		return

	for row in frappe.db.sql(
		"""
		select name, external_source, external_record_id
		from `tabCRM Deal`
		where coalesce(external_source, '') != ''
			and coalesce(external_record_id, '') != ''
		""",
		as_dict=True,
	):
		ensure_external_reference(
			stats,
			reference_doctype="CRM Deal",
			reference_name=row.name,
			external_source=row.external_source,
			external_doctype=DEAL_EXTERNAL_DOCTYPE,
			external_id=row.external_record_id,
		)


def ensure_external_reference(
	stats,
	reference_doctype,
	reference_name,
	external_source,
	external_doctype,
	external_id,
	external_parent_id=None,
):
	reference_doctype = clean_value(reference_doctype)
	reference_name = clean_value(reference_name)
	external_source = clean_value(external_source)
	external_doctype = clean_value(external_doctype)
	external_id = clean_value(external_id)
	external_parent_id = clean_value(external_parent_id)

	if not all([reference_doctype, reference_name, external_source, external_doctype, external_id]):
		record_skip(stats, reference_doctype, reference_name, "missing required external reference data")
		return

	existing_for_reference = find_reference_by_local_key(
		reference_doctype,
		reference_name,
		external_source,
		external_doctype,
	)
	if len(existing_for_reference) > 1:
		record_skip(stats, reference_doctype, reference_name, "multiple local mappings already exist")
		return
	if existing_for_reference:
		existing = existing_for_reference[0]
		if same_external_key(existing, external_id, external_parent_id):
			stats["existing"] += 1
		else:
			record_skip(
				stats,
				reference_doctype,
				reference_name,
				f"local mapping already points to external ID {existing.external_id}",
			)
		return

	existing_for_external = find_reference_by_external_key(
		external_source,
		external_doctype,
		external_id,
		external_parent_id,
	)
	if len(existing_for_external) > 1:
		record_skip(stats, reference_doctype, reference_name, "multiple external mappings already exist")
		return
	if existing_for_external:
		existing = existing_for_external[0]
		if (
			existing.reference_doctype == reference_doctype
			and existing.reference_name == reference_name
		):
			stats["existing"] += 1
		else:
			record_skip(
				stats,
				reference_doctype,
				reference_name,
				f"external ID already points to {existing.reference_doctype} {existing.reference_name}",
			)
		return

	frappe.get_doc(
		{
			"doctype": "CRM External Reference",
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"external_source": external_source,
			"external_doctype": external_doctype,
			"external_id": external_id,
			"external_parent_id": external_parent_id,
		}
	).insert(ignore_permissions=True)
	stats["created"] += 1


def find_reference_by_local_key(reference_doctype, reference_name, external_source, external_doctype):
	return frappe.get_all(
		"CRM External Reference",
		filters={
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"external_source": external_source,
			"external_doctype": external_doctype,
		},
		fields=REFERENCE_FIELDS,
		limit=2,
	)


def find_reference_by_external_key(external_source, external_doctype, external_id, external_parent_id):
	fields = ", ".join(f"`{field}`" for field in REFERENCE_FIELDS)
	return frappe.db.sql(
		f"""
		select {fields}
		from `tabCRM External Reference`
		where external_source = %s
			and external_doctype = %s
			and external_id = %s
			and coalesce(external_parent_id, '') = %s
		limit 2
		""",
		(
			external_source,
			external_doctype,
			external_id,
			external_parent_id or "",
		),
		as_dict=True,
	)


def same_external_key(reference, external_id, external_parent_id):
	return (
		clean_value(reference.external_id) == external_id
		and clean_value(reference.external_parent_id) == external_parent_id
	)


def has_columns(doctype, columns):
	return frappe.db.table_exists(doctype) and all(frappe.db.has_column(doctype, column) for column in columns)


def record_skip(stats, reference_doctype, reference_name, reason):
	stats["skipped"] += 1
	if len(stats["examples"]) < 20:
		stats["examples"].append(f"{reference_doctype} {reference_name}: {reason}")


def log_stats(stats):
	frappe.logger("crm.patches").info(
		"Backfilled CRM External Reference: "
		f"created={stats['created']}, existing={stats['existing']}, skipped={stats['skipped']}"
	)
	if stats["examples"]:
		frappe.logger("crm.patches").warning(
			"Skipped CRM External Reference backfill rows: " + "; ".join(stats["examples"])
		)
