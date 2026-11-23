"""CRM Deal import validation for fields that Frappe intentionally cannot map."""

import re

import frappe
from frappe.core.doctype.data_import.import_provider import ImportProvider
from frappe.core.doctype.data_import.importer import INSERT, UPDATE, UPSERT
from frappe.utils import cstr


CREATION_HEADERS = {"creation", "createdon", "datecreated", "creationdate", "датасоздания", "создано"}


class CRMDealImportProvider(ImportProvider):
	"""Keep native row handling, but block an ignored creation-date correction."""

	def validate(self, import_file):
		warnings = []
		for column in import_file.header.columns:
			header = re.sub(r"[\s_-]+", "", str(column.header_title or "").casefold())
			if header not in CREATION_HEADERS:
				continue
			for row_number, value in zip(column.value_row_numbers, column.column_values):
				if value is None or not str(value).strip():
					continue
				warnings.append({
					"row": row_number,
					"code": "crm_creation_date_read_only",
					"type": "error",
					"message": frappe._("CRM deal creation date cannot be changed through import. Remove the Creation column."),
				})
				break
		return warnings

	def import_row(self, importer, doc):
		at = doc.get("analytics_source_event_at")
		event_id = doc.get("analytics_source_event_id")
		if bool(at) != bool(event_id):
			frappe.throw(frappe._("Provide both source event time and source event ID."), frappe.ValidationError)
		if at and event_id:
			if importer.import_type != UPDATE:
				frappe.throw(frappe._("Source events can update existing deals only."), frappe.ValidationError)
			from crm.analytics.source_event_import import check_event_order, parse_event, source_event_scope
			existing = frappe.get_doc("CRM Deal", doc.get("name"))
			event = parse_event(doc.get("external_source") or existing.external_source,
				doc.get("external_record_id") or existing.external_record_id, event_id, at)
			replay = check_event_order(existing.name, event, allow_exact_replay=True)
			# The markers are virtual input, not part of the CRM card. A replay
			# with unchanged business fields returns the native document without
			# a save; a conflicting replay reaches validation and is rejected.
			values = {key: value for key, value in doc.items()
				if key not in {"analytics_source_event_id", "analytics_source_event_at"}}
			from crm.analytics.history import FIELDS, _same_value
			def matches(key, value):
				return key == "name" or not isinstance(value, (dict, list)) and (
					_same_value(key, existing.get(key), value) or
					(existing.get(key) is None and value in (None, "")) or
					str(existing.get(key)) == str(value))
			unchanged = all(matches(key, value) for key, value in values.items())
			analytical_change = any(key in FIELDS["CRM Deal"] and not matches(key, value)
				for key, value in values.items())
			with source_event_scope(event):
				if replay:
					# Lock and recheck before claiming an idempotent replay. Frappe's
					# generic diff treats copied child status logs as new rows, so it
					# would save the parent even when all imported fields are equal.
					locked = frappe.db.sql("SELECT `modified` FROM `tabCRM Deal` WHERE `name`=%s FOR UPDATE",
						existing.name, as_dict=True)
					if not locked or cstr(locked[0].modified) != cstr(existing.modified):
						frappe.throw(frappe._("This deal changed while replaying the source event."), frappe.TimestampMismatchError)
					check_event_order(existing.name, event, allow_exact_replay=True)
					if not unchanged:
						frappe.throw(frappe._("Repeated source event conflicts with the current deal."), frappe.ValidationError)
					return existing, None
				if not analytical_change:
					frappe.throw(frappe._("A new source event must change an analytical deal field."), frappe.ValidationError)
				return importer.update_record(values), None
		if importer.import_type == INSERT:
			return importer.insert_record(doc), None
		if importer.import_type == UPDATE:
			return importer.update_record(doc), None
		if importer.import_type == UPSERT:
			return importer.upsert_record(doc)
		frappe.throw(frappe._("Unsupported CRM deal import type."), frappe.ValidationError)
