# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.fcrm.doctype.crm_external_reference.crm_external_reference import find_external_reference
from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_default_pipeline, resolve_deal_status


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

	def test_external_status_id_requires_external_source(self):
		pipeline = get_default_pipeline()

		with self.assertRaises(frappe.exceptions.ValidationError):
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": f"External Source Required Stage {frappe.generate_hash(length=8)}",
					"pipeline": pipeline,
					"external_status_id": f"external-status-{frappe.generate_hash(length=8)}",
					"type": "Open",
					"position": 99,
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

	def test_external_pipeline_id_is_inherited_from_pipeline_reference(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Reference Pipeline {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()
		frappe.db.set_value(
			"CRM Sales Pipeline",
			pipeline.name,
			{
				"external_source": None,
				"external_pipeline_id": None,
			},
			update_modified=False,
		)

		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Reference Inherited Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"type": "Open",
				"position": 99,
			}
		).insert()

		self.assertEqual(stage.external_source, "bitrix24")
		self.assertEqual(stage.external_pipeline_id, external_pipeline_id)

	def test_external_status_id_writes_external_reference(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		external_status_id = f"external-status-{frappe.generate_hash(length=8)}"
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Reference Pipeline {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()
		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Reference Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"external_status_id": external_status_id,
				"type": "Open",
				"position": 99,
			}
		).insert()

		reference = find_external_reference(
			"bitrix24",
			external_status_id,
			"CRM Deal Status",
			external_pipeline_id,
		)

		self.assertEqual(reference.reference_doctype, "CRM Deal Status")
		self.assertEqual(reference.reference_name, stage.name)
		self.assertEqual(reference.external_parent_id, external_pipeline_id)

	def test_resolve_status_reads_external_reference_before_legacy_fields(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		external_status_id = f"external-status-{frappe.generate_hash(length=8)}"
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Resolve Pipeline {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()
		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Resolve Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"external_status_id": external_status_id,
				"type": "Open",
				"position": 99,
			}
		).insert()
		frappe.db.set_value(
			"CRM Deal Status",
			stage.name,
			"external_status_id",
			None,
			update_modified=False,
		)

		resolved = resolve_deal_status(
			pipeline=pipeline.name,
			external_status_id=external_status_id,
			external_source="bitrix24",
		)

		self.assertEqual(resolved, stage.name)

	def test_external_reference_blocks_duplicate_status_after_legacy_field_cleared(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		external_status_id = f"external-status-{frappe.generate_hash(length=8)}"
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Reference Duplicate Pipeline {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()
		first = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": f"External Reference Unique Stage {frappe.generate_hash(length=8)}",
				"pipeline": pipeline.name,
				"external_status_id": external_status_id,
				"type": "Open",
				"position": 99,
			}
		).insert()
		frappe.db.set_value(
			"CRM Deal Status",
			first.name,
			"external_status_id",
			None,
			update_modified=False,
		)

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": f"External Reference Duplicate Stage {frappe.generate_hash(length=8)}",
					"pipeline": pipeline.name,
					"external_status_id": external_status_id,
					"type": "Open",
					"position": 100,
				}
			).insert()
