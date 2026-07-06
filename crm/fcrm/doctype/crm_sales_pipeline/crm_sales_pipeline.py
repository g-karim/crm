# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from crm.fcrm.doctype.crm_external_reference.crm_external_reference import (
	PIPELINE_EXTERNAL_DOCTYPE,
	STAGE_EXTERNAL_DOCTYPE,
	find_external_reference,
	get_external_reference,
	set_external_reference,
)


DEFAULT_DEAL_PIPELINE = "Default Deal Pipeline"
DEFAULT_DEAL_STAGE_TEMPLATES = [
	{
		"deal_status": "Qualification",
		"color": "gray",
		"type": "Open",
		"probability": 10,
		"position": 1,
	},
	{
		"deal_status": "Demo/Making",
		"color": "orange",
		"type": "Ongoing",
		"probability": 25,
		"position": 2,
	},
	{
		"deal_status": "Proposal/Quotation",
		"color": "blue",
		"type": "Ongoing",
		"probability": 50,
		"position": 3,
	},
	{
		"deal_status": "Negotiation",
		"color": "yellow",
		"type": "Ongoing",
		"probability": 70,
		"position": 4,
	},
	{
		"deal_status": "Ready to Close",
		"color": "purple",
		"type": "Ongoing",
		"probability": 90,
		"position": 5,
	},
	{
		"deal_status": "Won",
		"color": "green",
		"type": "Won",
		"probability": 100,
		"position": 6,
	},
	{
		"deal_status": "Lost",
		"color": "red",
		"type": "Lost",
		"probability": 0,
		"position": 7,
	},
]


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
		enable_kanban_freeze_effect: DF.Check
		enabled: DF.Check
		icon: DF.Data | None
		is_default: DF.Check
		pipeline_name: DF.Data
		position: DF.Int
		closing_fields_rule: DF.Literal["Allow", "Warn", "Block"]
		required_fields_before_closing: DF.SmallText | None
		stage_backwards_rule: DF.Literal["Allow", "Warn", "Block"]
		stage_skip_rule: DF.Literal["Allow", "Warn", "Block"]
		warn_on_closing_without_required_fields: DF.Check
		warn_on_stage_backwards: DF.Check
		warn_on_stage_skip: DF.Check
	# end: auto-generated types

	def validate(self):
		self.validate_external_source_required()
		self.validate_external_pipeline_id()

		if self.archived:
			self.enabled = 0

		if self.is_default and (self.archived or not self.enabled):
			frappe.throw(_("Default pipeline must be enabled and not archived."))

		if (self.archived or not self.enabled) and not self.is_new():
			active_pipeline_exists = frappe.db.exists(
				"CRM Sales Pipeline",
				{
					"name": ["!=", self.name],
					"enabled": 1,
					"archived": 0,
				},
			)
			if not active_pipeline_exists:
				frappe.throw(_("At least one sales pipeline must stay active."))

	def validate_external_source_required(self):
		if self.external_pipeline_id and not self.external_source:
			frappe.throw(
				_("External source is required when using external import IDs."),
				frappe.ValidationError,
			)

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
		self.sync_external_reference()

	def after_insert(self):
		self.sync_external_reference()

	def sync_external_reference(self):
		if not self.external_source or not self.external_pipeline_id:
			return

		set_external_reference(
			"CRM Sales Pipeline",
			self.name,
			self.external_source,
			self.external_pipeline_id,
			PIPELINE_EXTERNAL_DOCTYPE,
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
	pipeline_label = get_default_pipeline_label()
	pipeline = frappe.db.exists("CRM Sales Pipeline", pipeline_label) or frappe.db.exists(
		"CRM Sales Pipeline", DEFAULT_DEAL_PIPELINE
	)
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
	doc.pipeline_name = pipeline_label
	doc.enabled = 1
	doc.is_default = 1
	doc.position = 1
	doc.color = "gray"
	doc.insert(ignore_permissions=True)
	return doc.name


def get_default_pipeline_label() -> str:
	return DEFAULT_DEAL_PIPELINE


def get_default_deal_stage_label(label: str) -> str:
	return label


def get_default_deal_stage_templates() -> list[dict]:
	return [
		{
			**stage,
			"deal_status": get_default_deal_stage_label(stage["deal_status"]),
		}
		for stage in DEFAULT_DEAL_STAGE_TEMPLATES
	]


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
		if not external_source:
			frappe.throw(
				_("External source is required when using external pipeline ID {0}.").format(
					frappe.bold(external_pipeline_id),
				),
				frappe.ValidationError,
			)

		external_reference = find_external_reference(
			external_source,
			external_pipeline_id,
			PIPELINE_EXTERNAL_DOCTYPE,
		)
		if external_reference:
			resolved_from_external_id = external_reference.reference_name

		filters = {"external_pipeline_id": external_pipeline_id}
		filters["external_source"] = external_source

		if not resolved_from_external_id:
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
		if not external_source:
			frappe.throw(
				_("External source is required when using external status ID {0}.").format(
					frappe.bold(external_status_id),
				),
				frappe.ValidationError,
			)
		external_parent_id = get_reference_external_id(
			"CRM Sales Pipeline",
			pipeline,
			external_source,
			PIPELINE_EXTERNAL_DOCTYPE,
		)
		external_reference = find_external_reference(
			external_source,
			external_status_id,
			STAGE_EXTERNAL_DOCTYPE,
			external_parent_id,
		)
		if external_reference:
			resolved_from_external_id = external_reference.reference_name

		filters = {"external_status_id": external_status_id}
		if pipeline:
			filters["pipeline"] = pipeline
		filters["external_source"] = external_source

		if not resolved_from_external_id:
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


def get_reference_external_id(
	reference_doctype: str,
	reference_name: str | None,
	external_source: str | None,
	external_doctype: str,
) -> str | None:
	if not reference_name or not external_source:
		return None

	external_reference = get_external_reference(
		reference_doctype,
		reference_name,
		external_source,
		external_doctype,
	)
	if external_reference:
		return external_reference.external_id

	if reference_doctype == "CRM Sales Pipeline":
		return frappe.db.get_value("CRM Sales Pipeline", reference_name, "external_pipeline_id")

	return None


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
