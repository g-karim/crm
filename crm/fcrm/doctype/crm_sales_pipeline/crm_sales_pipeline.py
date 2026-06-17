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
		if self.archived:
			self.enabled = 0

		if self.is_default and (self.archived or not self.enabled):
			frappe.throw(_("Default pipeline must be enabled and not archived."))

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


def on_doctype_update():
	frappe.db.add_index("CRM Sales Pipeline", ["enabled", "archived", "is_default"])
	frappe.db.add_index("CRM Sales Pipeline", ["position"])
