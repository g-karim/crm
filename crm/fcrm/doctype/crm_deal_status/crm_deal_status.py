# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.model.document import Document

from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_default_pipeline


class CRMDealStatus(Document):
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
		deal_status: DF.Data
		pipeline: DF.Link
		position: DF.Int
		probability: DF.Percent
		type: DF.Literal["Open", "Ongoing", "On Hold", "Won", "Lost"]
	# end: auto-generated types

	def before_naming(self):
		if self.name and not self.name.startswith("new-"):
			self._explicit_name = self.name

	def autoname(self):
		self.name = getattr(self, "_explicit_name", None) or make_autoname(
			"CRM-DEAL-STAGE-.#####",
			doc=self,
		)

	def before_validate(self):
		if not self.deal_status and self.name and not self.name.startswith("new-"):
			self.deal_status = self.name

		if not self.pipeline:
			self.pipeline = get_default_pipeline()

	def validate(self):
		self.validate_unique_status_in_pipeline()

	def validate_unique_status_in_pipeline(self):
		if not self.pipeline or not self.deal_status:
			return

		existing = frappe.db.exists(
			"CRM Deal Status",
			{
				"name": ["!=", self.name],
				"pipeline": self.pipeline,
				"deal_status": self.deal_status,
			},
		)
		if existing:
			frappe.throw(
				_("Deal stage {0} already exists in pipeline {1}.").format(
					frappe.bold(self.deal_status),
					frappe.bold(self.pipeline),
				),
				frappe.DuplicateEntryError,
			)


def on_doctype_update():
	frappe.db.add_index("CRM Deal Status", ["pipeline", "archived", "position"])
	frappe.db.add_index("CRM Deal Status", ["pipeline", "position"])
	frappe.db.add_index("CRM Deal Status", ["pipeline", "deal_status"])
