# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form.assign_to import _add as assign
from frappe.model.document import Document

from crm.api.exchange_rate import get_exchange_rate
from crm.fcrm.doctype.crm_service_level_agreement.utils import get_sla
from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import (
	get_default_deal_status,
	get_default_pipeline,
	resolve_deal_status,
	resolve_sales_pipeline,
)
from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import add_status_change_log
from crm.fcrm.doctype.utils import add_or_remove_lost_reason_section_in_sidepanel


class CRMDeal(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from crm.fcrm.doctype.crm_contacts.crm_contacts import CRMContacts
		from crm.fcrm.doctype.crm_products.crm_products import CRMProducts
		from crm.fcrm.doctype.crm_rolling_response_time.crm_rolling_response_time import (
			CRMRollingResponseTime,
		)
		from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import CRMStatusChangeLog

		annual_revenue: DF.Currency
		external_source: DF.Data | None
		external_record_id: DF.Data | None
		external_pipeline_id: DF.Data | None
		external_status_id: DF.Data | None
		closed_date: DF.Date | None
		communication_status: DF.Link | None
		contact: DF.Link | None
		contacts: DF.Table[CRMContacts]
		currency: DF.Link | None
		deal_name: DF.Data | None
		deal_owner: DF.Link | None
		deal_value: DF.Currency
		email: DF.Data | None
		exchange_rate: DF.Float
		expected_closure_date: DF.Date | None
		expected_deal_value: DF.Currency
		first_name: DF.Data | None
		first_responded_on: DF.Datetime | None
		first_response_time: DF.Duration | None
		gender: DF.Link | None
		industry: DF.Link | None
		job_title: DF.Data | None
		last_name: DF.Data | None
		last_responded_on: DF.Datetime | None
		last_response_time: DF.Duration | None
		lead: DF.Link | None
		lead_name: DF.Data | None
		lost_notes: DF.Text | None
		lost_reason: DF.Link | None
		mobile_no: DF.Data | None
		naming_series: DF.Literal["CRM-DEAL-.YYYY.-"]
		net_total: DF.Currency
		next_step: DF.Data | None
		no_of_employees: DF.Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
		organization: DF.Link | None
		organization_name: DF.Data | None
		phone: DF.Data | None
		pipeline: DF.Link
		pipeline_label: DF.Data | None
		probability: DF.Percent
		products: DF.Table[CRMProducts]
		response_by: DF.Datetime | None
		rolling_responses: DF.Table[CRMRollingResponseTime]
		salutation: DF.Link | None
		sla: DF.Link | None
		sla_creation: DF.Datetime | None
		sla_status: DF.Literal["", "First Response Due", "Rolling Response Due", "Failed", "Fulfilled"]
		source: DF.Link | None
		status: DF.Link
		status_change_log: DF.Table[CRMStatusChangeLog]
		status_label: DF.Data | None
		territory: DF.Link | None
		total: DF.Currency
		website: DF.Data | None
	# end: auto-generated types

	def before_validate(self):
		self.validate_external_source_required()
		self.normalize_import_fields()
		self.set_sla()

	def validate(self):
		self.validate_pipeline()
		self.validate_status()
		self.validate_status_pipeline()
		self.validate_external_record_id()
		self.set_primary_contact()
		self.set_primary_email_mobile_no()
		if not self.is_new() and self.has_value_changed("deal_owner") and self.deal_owner:
			self.share_with_agent(self.deal_owner)
			self.assign_agent(self.deal_owner)
		if self.has_value_changed("status"):
			add_status_change_log(self)
			if frappe.db.get_value("CRM Deal Status", self.status, "type") == "Won":
				self.closed_date = frappe.utils.nowdate()
		self.validate_forecasting_fields()
		self.validate_lost_reason()
		self.emit_pipeline_rule_warnings()
		self.update_exchange_rate()

	def after_insert(self):
		if self.deal_owner:
			if self.deal_owner != frappe.session.user:
				self.share_with_agent(self.deal_owner)
			self.assign_agent(self.deal_owner)

	def before_save(self):
		self.apply_sla()

	def normalize_import_fields(self):
		resolved_pipeline = resolve_sales_pipeline(
			self.pipeline_label,
			self.external_pipeline_id,
			self.external_source,
		)
		if resolved_pipeline:
			if self.pipeline and self.pipeline != resolved_pipeline:
				frappe.throw(
					_("Pipeline {0} does not match imported pipeline {1}.").format(
						frappe.bold(self.pipeline),
						frappe.bold(resolved_pipeline),
					),
					frappe.ValidationError,
				)
			self.pipeline = resolved_pipeline

		resolved_status = resolve_deal_status(
			self.status_label,
			self.pipeline,
			self.external_status_id,
			self.external_source,
		)
		if resolved_status:
			if self.status and self.status != resolved_status:
				frappe.throw(
					_("Deal stage {0} does not match imported stage {1}.").format(
						frappe.bold(self.status),
						frappe.bold(resolved_status),
					),
					frappe.ValidationError,
				)
			self.status = resolved_status

		if self.status and not self.pipeline:
			self.pipeline = frappe.db.get_value("CRM Deal Status", self.status, "pipeline")

	def validate_status(self):
		if self.status and self.pipeline and self.has_value_changed("pipeline") and not self.has_value_changed("status"):
			status_pipeline = frappe.db.get_value("CRM Deal Status", self.status, "pipeline")
			if status_pipeline and status_pipeline != self.pipeline:
				self.status = None

		if not self.status:
			self.status = get_default_deal_status(self.pipeline)

		if not self.status:
			frappe.throw(
				_("Please add at least one open stage in pipeline {0}.").format(frappe.bold(self.pipeline)),
				frappe.ValidationError,
			)

	def validate_pipeline(self):
		if not self.pipeline and self.status:
			self.pipeline = frappe.db.get_value("CRM Deal Status", self.status, "pipeline")

		if not self.pipeline:
			self.pipeline = get_default_pipeline()

		if frappe.db.get_value("CRM Sales Pipeline", self.pipeline, "archived"):
			frappe.throw(_("Cannot use archived pipeline {0}.").format(frappe.bold(self.pipeline)))

	def validate_status_pipeline(self):
		if not self.status or not self.pipeline:
			return

		status_pipeline = frappe.db.get_value("CRM Deal Status", self.status, "pipeline")
		if not status_pipeline:
			frappe.throw(
				_("Deal stage {0} is not assigned to a sales pipeline.").format(frappe.bold(self.status)),
				frappe.ValidationError,
			)

		if status_pipeline != self.pipeline:
			frappe.throw(
				_("Deal stage {0} does not belong to pipeline {1}.").format(
					frappe.bold(self.status),
					frappe.bold(self.pipeline),
				),
				frappe.ValidationError,
			)

	def validate_external_source_required(self):
		external_fields = [
			"external_record_id",
			"external_pipeline_id",
			"external_status_id",
		]
		if not self.external_source and any(self.get(field) for field in external_fields):
			frappe.throw(
				_("External source is required when using external import IDs."),
				frappe.ValidationError,
			)

	def validate_external_record_id(self):
		if not self.external_record_id:
			return

		filters = {
			"name": ["!=", self.name],
			"external_record_id": self.external_record_id,
		}
		if self.external_source:
			filters["external_source"] = self.external_source

		existing = frappe.db.exists("CRM Deal", filters)
		if existing:
			frappe.throw(
				_("External record ID {0} is already linked to deal {1}.").format(
					frappe.bold(self.external_record_id),
					frappe.bold(existing),
				),
				frappe.DuplicateEntryError,
			)

	def get_pipeline_stage_order(self):
		return frappe.get_all(
			"CRM Deal Status",
			filters={"pipeline": self.pipeline},
			fields=["name", "deal_status", "position", "type"],
			order_by="position asc, modified asc",
		)

	def emit_pipeline_rule_warnings(self):
		warnings = self.get_pipeline_rule_warnings()
		self._pipeline_rule_warnings = warnings

		if warnings:
			frappe.msgprint(
				warnings,
				title=_("Pipeline Warnings"),
				as_list=True,
				indicator="orange",
				alert=True,
			)

	def get_pipeline_rule_warnings(self) -> list[str]:
		if self.is_new() or not self.has_value_changed("status") or not self.pipeline or not self.status:
			return []

		previous = self.get_doc_before_save()
		if not previous or not previous.status or previous.status == self.status:
			return []

		rules = frappe.db.get_value(
			"CRM Sales Pipeline",
			self.pipeline,
			[
				"warn_on_stage_skip",
				"warn_on_stage_backwards",
				"warn_on_closing_without_required_fields",
				"required_fields_before_closing",
			],
			as_dict=True,
		)
		if not rules or not any(
			[
				rules.warn_on_stage_skip,
				rules.warn_on_stage_backwards,
				rules.warn_on_closing_without_required_fields,
			]
		):
			return []

		stages = self.get_pipeline_stage_order()
		stage_map = {stage.name: stage for stage in stages}
		previous_stage = stage_map.get(previous.status)
		current_stage = stage_map.get(self.status)
		if not previous_stage or not current_stage:
			return []

		warnings = []
		stage_index = {stage.name: index for index, stage in enumerate(stages)}
		previous_position = stage_index[previous_stage.name]
		current_position = stage_index[current_stage.name]

		if rules.warn_on_stage_skip and current_position > previous_position + 1:
			warnings.append(
				_("Deal moved from {0} to {1}, skipping intermediate stages.").format(
					frappe.bold(previous_stage.deal_status),
					frappe.bold(current_stage.deal_status),
				)
			)

		if rules.warn_on_stage_backwards and current_position < previous_position:
			warnings.append(
				_("Deal moved backwards from {0} to {1}.").format(
					frappe.bold(previous_stage.deal_status),
					frappe.bold(current_stage.deal_status),
				)
			)

		if (
			rules.warn_on_closing_without_required_fields
			and current_stage.type in ["Won", "Lost"]
			and rules.required_fields_before_closing
		):
			missing_fields = self.get_missing_pipeline_rule_fields(rules.required_fields_before_closing)
			if missing_fields:
				warnings.append(
					_("Deal was closed without these fields: {0}.").format(
						", ".join(frappe.bold(field) for field in missing_fields),
					)
				)

		return warnings

	def get_missing_pipeline_rule_fields(self, required_fields: str) -> list[str]:
		fieldnames = []
		for row in required_fields.replace(",", "\n").splitlines():
			fieldname = row.strip()
			if fieldname and fieldname not in fieldnames:
				fieldnames.append(fieldname)

		missing_fields = []
		for fieldname in fieldnames:
			if self.has_pipeline_rule_field_value(fieldname):
				continue

			df = self.meta.get_field(fieldname)
			missing_fields.append(df.label if df and df.label else fieldname)

		return missing_fields

	def has_pipeline_rule_field_value(self, fieldname: str) -> bool:
		value = self.get(fieldname)
		if isinstance(value, str):
			return bool(value.strip())
		if isinstance(value, list):
			return bool(value)
		return value not in [None, ""]

	def set_primary_contact(self, contact=None):
		if not self.contacts:
			return

		if not contact and len(self.contacts) == 1:
			self.contacts[0].is_primary = 1
		elif contact:
			for d in self.contacts:
				if d.contact == contact:
					d.is_primary = 1
				else:
					d.is_primary = 0

	def set_primary_email_mobile_no(self):
		if not self.contacts:
			self.email = ""
			self.mobile_no = ""
			self.phone = ""
			return

		if len([contact for contact in self.contacts if contact.is_primary]) > 1:
			frappe.throw(_("Only one {0} can be set as primary.").format(frappe.bold("Contact")))

		primary_contact_exists = False
		for d in self.contacts:
			if d.is_primary == 1:
				primary_contact_exists = True
				self.email = d.email.strip() if d.email else ""
				self.mobile_no = d.mobile_no.strip() if d.mobile_no else ""
				self.phone = d.phone.strip() if d.phone else ""
				break

		if not primary_contact_exists:
			self.email = ""
			self.mobile_no = ""
			self.phone = ""

	def assign_agent(self, agent):
		if not agent:
			return

		assignees = self.get_assigned_users()
		if assignees:
			for assignee in assignees:
				if agent == assignee:
					# the agent is already set as an assignee
					return

		assign({"assign_to": [agent], "doctype": "CRM Deal", "name": self.name}, ignore_permissions=True)

	def share_with_agent(self, agent):
		if not agent:
			return

		docshares = frappe.get_all(
			"DocShare",
			filters={"share_name": self.name, "share_doctype": self.doctype},
			fields=["name", "user"],
		)

		shared_with = [d.user for d in docshares] + [agent]

		for user in shared_with:
			if user == agent and not frappe.db.exists(
				"DocShare",
				{"user": agent, "share_name": self.name, "share_doctype": self.doctype},
			):
				frappe.share.add_docshare(
					self.doctype,
					self.name,
					agent,
					write=1,
					flags={"ignore_share_permission": True},
				)
			elif user != agent:
				frappe.share.remove(
					self.doctype,
					self.name,
					user,
					flags={"ignore_share_permission": True, "ignore_permissions": True},
				)

	def set_sla(self):
		"""
		Find an SLA to apply to the deal.
		"""
		if self.sla:
			return

		sla = get_sla(self)
		if not sla:
			self.first_responded_on = None
			self.first_response_time = None
			return
		self.sla = sla.name

	def apply_sla(self):
		"""
		Apply SLA if set.
		"""
		if not self.sla:
			return
		sla = frappe.get_last_doc("CRM Service Level Agreement", {"name": self.sla})
		if sla:
			sla.apply(self)

	def update_closed_date(self):
		"""
		Update the closed date based on the "Won" status.
		"""
		if (
			self.status
			and frappe.get_cached_value("CRM Deal Status", self.status, "type") == "Won"
			and not self.closed_date
		):
			self.closed_date = frappe.utils.nowdate()

	def update_default_probability(self):
		"""
		Update the default probability based on the status.
		"""
		if not self.probability or self.probability == 0:
			self.probability = frappe.db.get_value("CRM Deal Status", self.status, "probability") or 0

	def update_expected_deal_value(self):
		"""
		Update the expected deal value based on the net total or total.
		"""
		if (
			frappe.db.get_single_value("FCRM Settings", "auto_update_expected_deal_value")
			and (self.net_total or self.total)
			and self.expected_deal_value
		):
			self.expected_deal_value = self.net_total or self.total

	def validate_forecasting_fields(self):
		self.update_closed_date()
		self.update_default_probability()
		self.update_expected_deal_value()
		if frappe.db.get_single_value("FCRM Settings", "enable_forecasting"):
			if not self.expected_deal_value or self.expected_deal_value == 0:
				frappe.throw(_("Expected deal value is required."), frappe.MandatoryError)
			if not self.expected_closure_date:
				frappe.throw(_("Expected closure date is required."), frappe.MandatoryError)

	def validate_lost_reason(self):
		"""
		Validate the lost reason if the status is set to "Lost".
		"""
		if self.status and frappe.get_cached_value("CRM Deal Status", self.status, "type") == "Lost":
			if not self.lost_reason:
				frappe.throw(_("Please specify a reason for losing the deal."), frappe.ValidationError)
			elif self.lost_reason == "Other" and not self.lost_notes:
				frappe.throw(_("Please specify the reason for losing the deal."), frappe.ValidationError)
		if self.has_value_changed("status"):
			add_or_remove_lost_reason_section_in_sidepanel(self)

	def update_exchange_rate(self):
		if self.has_value_changed("currency") or not self.exchange_rate:
			system_currency = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
			exchange_rate = 1
			if self.currency and self.currency != system_currency:
				exchange_rate = get_exchange_rate(self.currency, system_currency)

			self.db_set("exchange_rate", exchange_rate)

	@staticmethod
	def default_list_data():
		columns = [
			{
				"label": "Deal Name",
				"type": "Data",
				"key": "deal_name",
				"width": "14rem",
			},
			{
				"label": "Organization",
				"type": "Link",
				"key": "organization",
				"options": "CRM Organization",
				"width": "11rem",
			},
			{
				"label": "Annual Revenue",
				"type": "Currency",
				"key": "annual_revenue",
				"align": "right",
				"width": "9rem",
			},
			{
				"label": "Status",
				"type": "Link",
				"options": "CRM Deal Status",
				"key": "status",
				"width": "10rem",
			},
			{
				"label": "Email",
				"type": "Data",
				"key": "email",
				"width": "12rem",
			},
			{
				"label": "Mobile No.",
				"type": "Data",
				"key": "mobile_no",
				"width": "11rem",
			},
			{
				"label": "Assigned To",
				"type": "Text",
				"key": "_assign",
				"width": "10rem",
			},
			{
				"label": "Last Modified",
				"type": "Datetime",
				"key": "modified",
				"width": "8rem",
			},
		]
		rows = [
			"name",
			"deal_name",
			"organization",
			"annual_revenue",
			"status",
			"email",
			"currency",
			"mobile_no",
			"deal_owner",
			"sla_status",
			"response_by",
			"first_response_time",
			"first_responded_on",
			"modified",
			"_assign",
		]
		return {"columns": columns, "rows": rows}

	@staticmethod
	def default_kanban_settings():
		return {
			"column_field": "status",
			"title_field": "deal_name",
			"kanban_fields": '["organization", "annual_revenue", "email", "mobile_no", "_assign", "modified"]',
		}


@frappe.whitelist()
def add_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to add contact to Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.append("contacts", {"contact": contact})
	deal.save()
	return True


@frappe.whitelist()
def remove_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to remove contact from Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.contacts = [d for d in deal.contacts if d.contact != contact]
	deal.save()
	return True


@frappe.whitelist()
def set_primary_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to set primary contact for Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.set_primary_contact(contact)
	deal.save()
	return True


def create_organization(doc):
	if not doc.get("organization_name"):
		return

	existing_organization = frappe.db.exists(
		"CRM Organization", {"organization_name": doc.get("organization_name")}
	)
	if existing_organization:
		return existing_organization

	organization = frappe.new_doc("CRM Organization")
	organization.update(
		{
			"organization_name": doc.get("organization_name"),
			"website": doc.get("website"),
			"territory": doc.get("territory"),
			"industry": doc.get("industry"),
			"annual_revenue": doc.get("annual_revenue"),
		}
	)
	organization.insert(ignore_permissions=True)
	return organization.name


def contact_exists(doc):
	email_exist = frappe.db.exists("Contact Email", {"email_id": doc.get("email")})
	mobile_exist = frappe.db.exists("Contact Phone", {"phone": doc.get("mobile_no")})

	doctype = "Contact Email" if email_exist else "Contact Phone"
	name = email_exist or mobile_exist

	if name:
		return frappe.db.get_value(doctype, name, "parent")

	return False


def create_contact(doc):
	existing_contact = contact_exists(doc)
	if existing_contact:
		return existing_contact

	contact = frappe.new_doc("Contact")
	contact.update(
		{
			"first_name": doc.get("first_name"),
			"last_name": doc.get("last_name"),
			"salutation": doc.get("salutation"),
			"company_name": doc.get("organization") or doc.get("organization_name"),
			"gender": doc.get("gender"),
		}
	)

	if doc.get("email"):
		contact.append("email_ids", {"email_id": doc.get("email"), "is_primary": 1})

	if doc.get("mobile_no"):
		contact.append("phone_nos", {"phone": doc.get("mobile_no"), "is_primary_mobile_no": 1})

	contact.insert(ignore_permissions=True)
	contact.reload()  # load changes by hooks on contact

	return contact.name


@frappe.whitelist()
def create_deal(doc: dict):
	deal = frappe.new_doc("CRM Deal")

	contact = doc.get("contact")
	if not contact and (
		doc.get("first_name") or doc.get("last_name") or doc.get("email") or doc.get("mobile_no")
	):
		contact = create_contact(doc)

	deal.update(
		{
			"organization": doc.get("organization") or create_organization(doc),
			"contacts": [{"contact": contact, "is_primary": 1}] if contact else [],
		}
	)

	doc.pop("organization", None)

	deal.update(doc)

	deal.insert(ignore_permissions=True)
	return deal.name


def on_doctype_update():
	frappe.db.add_index("CRM Deal", ["external_source", "external_record_id"])
	frappe.db.add_index("CRM Deal", ["external_source", "external_pipeline_id", "external_status_id"])
