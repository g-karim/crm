# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.api.sales_pipeline import duplicate_pipeline, get_pipeline_settings


class TestCRMSalesPipeline(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_only_one_default_pipeline_remains(self):
		first = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Default One {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"is_default": 1,
				"position": 98,
			}
		).insert()
		second = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Default Two {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"is_default": 1,
				"position": 99,
			}
		).insert()

		first.reload()
		second.reload()

		self.assertFalse(first.is_default)
		self.assertTrue(second.is_default)

	def test_default_pipeline_cannot_be_archived(self):
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Archived Default {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"is_default": 1,
				"archived": 1,
			}
		)

		with self.assertRaises(frappe.exceptions.ValidationError):
			pipeline.insert()

	def test_pipeline_with_stages_cannot_be_deleted(self):
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Pipeline With Stage {frappe.generate_hash(length=8)}",
				"enabled": 1,
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"Pipeline Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"type": "Open",
				"probability": 10,
				"position": 1,
			}
		).insert()

		with self.assertRaises(frappe.exceptions.ValidationError):
			pipeline.delete()

	def test_pipeline_settings_excludes_archived_records_by_default(self):
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Archived Settings Pipeline {frappe.generate_hash(length=8)}",
				"enabled": 0,
				"archived": 1,
				"position": 199,
			}
		).insert()
		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"Archived Settings Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"type": "Open",
				"position": 1,
				"archived": 1,
			}
		).insert()

		active_settings = get_pipeline_settings(show_archived=0)
		self.assertNotIn(pipeline.name, [row.name for row in active_settings["pipelines"]])
		self.assertNotIn(stage.name, [row.name for row in active_settings["stages"]])

		archived_settings = get_pipeline_settings(show_archived=1)
		self.assertIn(pipeline.name, [row.name for row in archived_settings["pipelines"]])
		self.assertIn(stage.name, [row.name for row in archived_settings["stages"]])

	def test_duplicate_pipeline_copies_active_stages(self):
		source = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Duplicate Source {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"position": 199,
			}
		).insert()
		active_stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"Active Duplicate Stage {frappe.generate_hash(length=8)}",
				"pipeline": source.name,
				"type": "Open",
				"position": 1,
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"Archived Duplicate Stage {frappe.generate_hash(length=8)}",
				"pipeline": source.name,
				"type": "Open",
				"position": 2,
				"archived": 1,
			}
		).insert()

		duplicate = duplicate_pipeline(
			source.name,
			f"Duplicate Target {frappe.generate_hash(length=8)}",
		)
		duplicate_stages = frappe.get_all(
			"CRM Deal Status",
			filters={"pipeline": duplicate.name},
			fields=["deal_status", "archived"],
		)

		self.assertEqual(len(duplicate_stages), 1)
		self.assertEqual(duplicate_stages[0].deal_status, active_stage.deal_status)
		self.assertFalse(duplicate_stages[0].archived)
