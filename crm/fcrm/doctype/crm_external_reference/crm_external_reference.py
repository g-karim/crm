# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


REFERENCE_FIELDS = [
	"name",
	"reference_doctype",
	"reference_name",
	"external_source",
	"external_doctype",
	"external_id",
	"external_parent_id",
]

DEAL_EXTERNAL_DOCTYPE = "CRM Deal"
PIPELINE_EXTERNAL_DOCTYPE = "CRM Sales Pipeline"
STAGE_EXTERNAL_DOCTYPE = "CRM Deal Status"


class CRMExternalReference(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		external_doctype: DF.Data
		external_id: DF.Data
		external_parent_id: DF.Data | None
		external_source: DF.Data
		reference_doctype: DF.Link
		reference_name: DF.DynamicLink
	# end: auto-generated types

	def before_validate(self):
		self.reference_doctype = clean_value(self.reference_doctype)
		self.reference_name = clean_value(self.reference_name)
		self.external_source = clean_value(self.external_source)
		self.external_doctype = clean_value(self.external_doctype) or self.reference_doctype
		self.external_id = clean_value(self.external_id)
		self.external_parent_id = clean_value(self.external_parent_id)

	def validate(self):
		self.validate_unique_external_id()
		self.validate_unique_reference()

	def validate_unique_external_id(self):
		existing = frappe.db.sql(
			"""
			select name
			from `tabCRM External Reference`
			where name != %s
				and external_source = %s
				and external_doctype = %s
				and external_id = %s
				and coalesce(external_parent_id, '') = %s
			limit 1
			""",
			(
				self.name or "",
				self.external_source,
				self.external_doctype,
				self.external_id,
				self.external_parent_id or "",
			),
			pluck="name",
		)
		if existing:
			frappe.throw(
				_("External ID {0} is already linked by reference {1}.").format(
					frappe.bold(self.external_id),
					frappe.bold(existing[0]),
				),
				frappe.DuplicateEntryError,
			)

	def validate_unique_reference(self):
		existing = frappe.db.exists(
			"CRM External Reference",
			{
				"name": ["!=", self.name],
				"reference_doctype": self.reference_doctype,
				"reference_name": self.reference_name,
				"external_source": self.external_source,
				"external_doctype": self.external_doctype,
			},
		)
		if existing:
			frappe.throw(
				_("Reference {0} {1} already has an external {2} mapping for source {3}.").format(
					frappe.bold(self.reference_doctype),
					frappe.bold(self.reference_name),
					frappe.bold(self.external_doctype),
					frappe.bold(self.external_source),
				),
				frappe.DuplicateEntryError,
			)


def clean_value(value):
	if value is None:
		return None
	value = str(value).strip()
	return value or None


def reference_table_exists():
	return frappe.db.table_exists("CRM External Reference")


def get_external_reference(
	reference_doctype: str,
	reference_name: str,
	external_source: str | None = None,
	external_doctype: str | None = None,
):
	if not reference_table_exists():
		return None

	filters = {
		"reference_doctype": clean_value(reference_doctype),
		"reference_name": clean_value(reference_name),
	}
	if external_source:
		filters["external_source"] = clean_value(external_source)
	if external_doctype:
		filters["external_doctype"] = clean_value(external_doctype)

	return get_single_reference(filters)


def find_external_reference(
	external_source: str,
	external_id: str,
	external_doctype: str | None = None,
	external_parent_id: str | None = None,
):
	if not reference_table_exists():
		return None

	filters = {
		"external_source": clean_value(external_source),
		"external_id": clean_value(external_id),
	}
	if external_doctype:
		filters["external_doctype"] = clean_value(external_doctype)
	if external_parent_id:
		filters["external_parent_id"] = clean_value(external_parent_id)

	return get_single_reference(filters)


def get_single_reference(filters: dict):
	references = frappe.get_all(
		"CRM External Reference",
		filters=filters,
		fields=REFERENCE_FIELDS,
		limit=2,
	)
	if len(references) > 1:
		frappe.throw(
			_("Multiple external references match filters {0}.").format(frappe.bold(str(filters))),
			frappe.ValidationError,
		)
	return references[0] if references else None


def set_external_reference(
	reference_doctype: str,
	reference_name: str,
	external_source: str,
	external_id: str,
	external_doctype: str | None = None,
	external_parent_id: str | None = None,
):
	if not reference_table_exists():
		return None

	reference_doctype = clean_value(reference_doctype)
	reference_name = clean_value(reference_name)
	external_source = clean_value(external_source)
	external_doctype = clean_value(external_doctype) or reference_doctype
	external_id = clean_value(external_id)
	external_parent_id = clean_value(external_parent_id)

	external_reference = find_external_reference(
		external_source,
		external_id,
		external_doctype,
		external_parent_id,
	)
	if external_reference:
		if (
			external_reference.reference_doctype != reference_doctype
			or external_reference.reference_name != reference_name
		):
			frappe.throw(
				_("External ID {0} is already linked to {1} {2}.").format(
					frappe.bold(external_id),
					frappe.bold(external_reference.reference_doctype),
					frappe.bold(external_reference.reference_name),
				),
				frappe.DuplicateEntryError,
			)
		doc = frappe.get_doc("CRM External Reference", external_reference.name)
	else:
		doc = get_doc_for_reference(
			reference_doctype,
			reference_name,
			external_source,
			external_doctype,
		)

	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"external_source": external_source,
			"external_doctype": external_doctype,
			"external_id": external_id,
			"external_parent_id": external_parent_id,
		}
	)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc


def get_doc_for_reference(
	reference_doctype: str,
	reference_name: str,
	external_source: str,
	external_doctype: str,
):
	existing = get_external_reference(
		reference_doctype,
		reference_name,
		external_source,
		external_doctype,
	)
	if existing:
		return frappe.get_doc("CRM External Reference", existing.name)
	return frappe.new_doc("CRM External Reference")


def on_doctype_update():
	frappe.db.add_index(
		"CRM External Reference",
		["external_source", "external_doctype", "external_id", "external_parent_id"],
		index_name="crm_ext_ref_external_idx",
	)
	frappe.db.add_index(
		"CRM External Reference",
		["reference_doctype", "reference_name", "external_source", "external_doctype"],
		index_name="crm_ext_ref_reference_idx",
	)
