# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


DEFAULT_DEAL_PIPELINE = "Default Deal Pipeline"


class CRMSalesPipeline(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		external_source: DF.Data | None
		external_pipeline_id: DF.Data | None
		archived: DF.Check
		color: DF.Literal[
			"black",
			"gray",
			"blue",
			"green",
			"red",
			"pink",
			"orange",
			"amber",
			"yellow",
			"cyan",
			"teal",
			"violet",
			"purple",
		]
		description: DF.SmallText | None
		enabled: DF.Check
		icon: DF.Data | None
		is_default: DF.Check
		pipeline_name: DF.Data
		position: DF.Int
	# end: auto-generated types

	def validate(self):
		self.validate_external_pipeline_id()

		if self.archived:
			self.enabled = 0

		if self.is_default and (self.archived or not self.enabled):
			frappe.throw(_("Default pipeline must be enabled and not archived."))

	def validate_external_pipeline_id(self):
		if not self.external_pipeline_id:
			return

		filters = {
			"name": ["!=", self.name],
			"external_pipeline_id": self.external_pipeline_id,
		}
		if self.external_source:
			filters["external_source"] = self.external_source

		existing = frappe.db.exists(
			"CRM Sales Pipeline",
			filters,
		)
		if existing:
			frappe.throw(
				_("External pipeline ID {0} is already used by pipeline {1}.").format(
					frappe.bold(self.external_pipeline_id),
					frappe.bold(existing),
				),
				frappe.DuplicateEntryError,
			)

	def on_update(self):
		if self.is_default:
			frappe.db.set_value(
				"CRM Sales Pipeline",
				{"name": ("!=", self.name), "is_default": 1},
				"is_default",
				0,
				update_modified=False,
			)

	def on_trash(self):
		if frappe.db.exists("CRM Deal Status", {"pipeline": self.name}):
			frappe.throw(_("Cannot delete a pipeline that has stages. Archive it instead."))

		if frappe.db.exists("CRM Deal", {"pipeline": self.name}):
			frappe.throw(_("Cannot delete a pipeline that has deals. Archive it instead."))


def get_default_pipeline() -> str:
	pipeline = frappe.db.get_value(
		"CRM Sales Pipeline",
		{"is_default": 1, "enabled": 1, "archived": 0},
		"name",
		order_by="position asc, modified asc",
	)

	if pipeline:
		return pipeline

	return get_or_create_default_pipeline()


def get_or_create_default_pipeline() -> str:
	pipeline = frappe.db.exists("CRM Sales Pipeline", DEFAULT_DEAL_PIPELINE)
	if pipeline:
		frappe.db.set_value(
			"CRM Sales Pipeline",
			pipeline,
			{
				"enabled": 1,
				"archived": 0,
				"is_default": 1,
				"position": 1,
			},
			update_modified=False,
		)
		frappe.db.set_value(
			"CRM Sales Pipeline",
			{"name": ("!=", pipeline), "is_default": 1},
			"is_default",
			0,
			update_modified=False,
		)
		return pipeline

	doc = frappe.new_doc("CRM Sales Pipeline")
	doc.pipeline_name = DEFAULT_DEAL_PIPELINE
	doc.enabled = 1
	doc.is_default = 1
	doc.position = 1
	doc.color = "gray"
	doc.insert(ignore_permissions=True)
	return doc.name


def get_default_deal_status(pipeline: str | None = None) -> str | None:
	pipeline = pipeline or get_default_pipeline()

	filters = {"pipeline": pipeline, "type": "Open"}
	if frappe.get_meta("CRM Deal Status").has_field("archived"):
		filters["archived"] = 0
	status = frappe.db.get_value("CRM Deal Status", filters, "name", order_by="position asc, modified asc")
	if status:
		return status

	filters = {"pipeline": pipeline, "type": ["in", ["Ongoing", "On Hold"]]}
	if frappe.get_meta("CRM Deal Status").has_field("archived"):
		filters["archived"] = 0
	status = frappe.db.get_value("CRM Deal Status", filters, "name", order_by="position asc, modified asc")
	if status:
		return status

	filters = {"pipeline": pipeline}
	if frappe.get_meta("CRM Deal Status").has_field("archived"):
		filters["archived"] = 0

	return frappe.db.get_value(
		"CRM Deal Status",
		filters,
		"name",
		order_by="position asc, modified asc",
	)


def resolve_sales_pipeline(
	value: str | None = None,
	external_pipeline_id: str | None = None,
	external_source: str | None = None,
) -> str | None:
	value = clean_import_value(value)
	external_pipeline_id = clean_import_value(external_pipeline_id)
	external_source = clean_import_value(external_source)

	resolved_from_external_id = None
	if external_pipeline_id:
		filters = {"external_pipeline_id": external_pipeline_id}
		if external_source:
			filters["external_source"] = external_source

		resolved_from_external_id = get_single_value(
			"CRM Sales Pipeline",
			filters,
			_("external pipeline ID {0}").format(frappe.bold(external_pipeline_id)),
		)

	resolved_from_value = None
	if value:
		if frappe.db.exists("CRM Sales Pipeline", value):
			resolved_from_value = value
		else:
			resolved_from_value = get_single_value(
				"CRM Sales Pipeline",
				{"pipeline_name": value},
				_("pipeline label {0}").format(frappe.bold(value)),
				throw_if_missing=False,
			)

		if not resolved_from_value:
			frappe.throw(
				_("Could not find sales pipeline for {0}.").format(frappe.bold(value)),
				frappe.LinkValidationError,
			)

	if resolved_from_external_id and resolved_from_value and resolved_from_external_id != resolved_from_value:
		frappe.throw(
			_("Pipeline {0} does not match external pipeline ID {1}.").format(
				frappe.bold(value),
				frappe.bold(external_pipeline_id),
			),
			frappe.ValidationError,
		)

	return resolved_from_value or resolved_from_external_id


def resolve_deal_status(
	value: str | None = None,
	pipeline: str | None = None,
	external_status_id: str | None = None,
	external_source: str | None = None,
) -> str | None:
	value = clean_import_value(value)
	pipeline = clean_import_value(pipeline)
	external_status_id = clean_import_value(external_status_id)
	external_source = clean_import_value(external_source)

	resolved_from_external_id = None
	if external_status_id:
		filters = {"external_status_id": external_status_id}
		if pipeline:
			filters["pipeline"] = pipeline
		if external_source:
			filters["external_source"] = external_source

		resolved_from_external_id = get_single_value(
			"CRM Deal Status",
			filters,
			_("external status ID {0}").format(frappe.bold(external_status_id)),
		)

	resolved_from_value = None
	if value:
		if frappe.db.exists("CRM Deal Status", value):
			status_pipeline = frappe.db.get_value("CRM Deal Status", value, "pipeline")
			if pipeline and status_pipeline != pipeline:
				frappe.throw(
					_("Deal stage {0} does not belong to pipeline {1}.").format(
						frappe.bold(value),
						frappe.bold(pipeline),
					),
					frappe.ValidationError,
				)
			resolved_from_value = value
		else:
			filters = {"deal_status": value}
			if pipeline:
				filters["pipeline"] = pipeline
			if frappe.get_meta("CRM Deal Status").has_field("archived"):
				filters["archived"] = 0
			resolved_from_value = get_single_value(
				"CRM Deal Status",
				filters,
				_("deal stage label {0}").format(frappe.bold(value)),
				throw_if_missing=False,
			)
			if not resolved_from_value:
				context = _(" in pipeline {0}").format(frappe.bold(pipeline)) if pipeline else ""
				frappe.throw(
					_("Could not find deal stage {0}{1}.").format(frappe.bold(value), context),
					frappe.LinkValidationError,
				)

	if resolved_from_external_id and resolved_from_value and resolved_from_external_id != resolved_from_value:
		frappe.throw(
			_("Deal stage {0} does not match external status ID {1}.").format(
				frappe.bold(value),
				frappe.bold(external_status_id),
			),
			frappe.ValidationError,
		)

	return resolved_from_value or resolved_from_external_id


def get_single_value(
	doctype: str,
	filters: dict,
	label: str,
	throw_if_missing: bool = True,
) -> str | None:
	matches = frappe.get_all(doctype, filters=filters, pluck="name", order_by="modified asc")
	if len(matches) == 1:
		return matches[0]

	if len(matches) > 1:
		frappe.throw(
			_("{0} matches multiple {1} records. Provide a sales pipeline or a technical ID.").format(
				label,
				_(doctype),
			),
			frappe.ValidationError,
		)

	if throw_if_missing:
		frappe.throw(
			_("Could not find {0}.").format(label),
			frappe.LinkValidationError,
		)

	return None


def clean_import_value(value) -> str | None:
	if value is None:
		return None

	value = frappe.utils.cstr(value).strip()
	return value or None


def on_doctype_update():
	frappe.db.add_index("CRM Sales Pipeline", ["enabled", "archived", "is_default"])
	frappe.db.add_index("CRM Sales Pipeline", ["position"])
	frappe.db.add_index("CRM Sales Pipeline", ["external_source", "external_pipeline_id"])
