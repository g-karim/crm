# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_default_pipeline


class TestCRMDealStatus(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_duplicate_stage_label_is_blocked_within_pipeline(self):
		pipeline = get_default_pipeline()
		stage_label = f"Duplicate Stage {frappe.generate_hash(length=8)}"

		frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": stage_label,
				"pipeline": pipeline,
				"type": "Open",
				"position": 99,
			}
		).insert()

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": stage_label,
					"pipeline": pipeline,
					"type": "Open",
					"position": 100,
				}
			).insert()

	def test_duplicate_stage_label_is_allowed_across_pipelines(self):
		stage_label = f"Shared Stage {frappe.generate_hash(length=8)}"
		first_pipeline = get_default_pipeline()
		second_pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Second Pipeline {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"position": 99,
			}
		).insert()

		first_stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": stage_label,
				"pipeline": first_pipeline,
				"type": "Open",
				"position": 99,
			}
		).insert()
		second_stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": stage_label,
				"pipeline": second_pipeline.name,
				"type": "Open",
				"position": 99,
			}
		).insert()

		self.assertNotEqual(first_stage.name, second_stage.name)

	def test_duplicate_external_status_id_is_blocked_within_pipeline(self):
		pipeline = get_default_pipeline()
		external_status_id = f"external-status-{frappe.generate_hash(length=8)}"

		frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Stage One {frappe.generate_hash(length=8)}",
				"pipeline": pipeline,
				"external_source": "bitrix24",
				"external_status_id": external_status_id,
				"type": "Open",
				"position": 99,
			}
		).insert()

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": f"External Stage Two {frappe.generate_hash(length=8)}",
					"pipeline": pipeline,
					"external_source": "bitrix24",
					"external_status_id": external_status_id,
					"type": "Open",
					"position": 100,
				}
			).insert()

	def test_external_pipeline_id_is_inherited_from_pipeline(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Pipeline {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()

		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Pipeline Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"type": "Open",
				"position": 99,
			}
		).insert()

		self.assertEqual(stage.external_source, "bitrix24")
		self.assertEqual(stage.external_pipeline_id, external_pipeline_id)
