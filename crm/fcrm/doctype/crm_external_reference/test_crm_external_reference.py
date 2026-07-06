# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.patches.v1_0.backfill_crm_external_references import execute as backfill_external_references
from crm.fcrm.doctype.crm_external_reference.crm_external_reference import (
	find_external_reference,
	get_external_reference,
	set_external_reference,
)


class TestCRMExternalReference(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_set_external_reference_creates_mapping(self):
		deal = create_test_deal()

		reference = set_external_reference(
			"CRM Deal",
			deal.name,
			"amocrm",
			"amo-deal-1",
			"deal",
			external_parent_id="pipeline-1",
		)

		self.assertEqual(reference.reference_doctype, "CRM Deal")
		self.assertEqual(reference.reference_name, deal.name)
		self.assertEqual(reference.external_source, "amocrm")
		self.assertEqual(reference.external_doctype, "deal")
		self.assertEqual(reference.external_id, "amo-deal-1")
		self.assertEqual(reference.external_parent_id, "pipeline-1")

	def test_set_external_reference_updates_existing_reference(self):
		deal = create_test_deal()
		first = set_external_reference("CRM Deal", deal.name, "amocrm", "amo-deal-1", "deal")

		second = set_external_reference(
			"CRM Deal",
			deal.name,
			"amocrm",
			"amo-deal-2",
			"deal",
			external_parent_id="pipeline-2",
		)

		self.assertEqual(first.name, second.name)
		self.assertEqual(second.external_id, "amo-deal-2")
		self.assertEqual(second.external_parent_id, "pipeline-2")
		self.assertFalse(
			frappe.db.exists(
				"CRM External Reference",
				{
					"external_source": "amocrm",
					"external_doctype": "deal",
					"external_id": "amo-deal-1",
				},
			)
		)

	def test_find_external_reference_returns_local_target(self):
		deal = create_test_deal()
		set_external_reference("CRM Deal", deal.name, "amocrm", "amo-deal-find", "deal")

		reference = find_external_reference("amocrm", "amo-deal-find", "deal")

		self.assertEqual(reference.reference_doctype, "CRM Deal")
		self.assertEqual(reference.reference_name, deal.name)

	def test_get_external_reference_returns_external_target(self):
		deal = create_test_deal()
		set_external_reference("CRM Deal", deal.name, "amocrm", "amo-deal-get", "deal")

		reference = get_external_reference("CRM Deal", deal.name, "amocrm", "deal")

		self.assertEqual(reference.external_id, "amo-deal-get")

	def test_external_id_must_be_unique_per_source_and_type(self):
		first = create_test_deal("External Unique First")
		second = create_test_deal("External Unique Second")
		set_external_reference("CRM Deal", first.name, "amocrm", "same-id", "deal")

		with self.assertRaises(frappe.DuplicateEntryError):
			set_external_reference("CRM Deal", second.name, "amocrm", "same-id", "deal")

	def test_external_id_can_repeat_across_sources_and_types(self):
		deal = create_test_deal()
		source_reference = set_external_reference("CRM Deal", deal.name, "amocrm", "shared-id", "deal")
		type_reference = set_external_reference(
			"CRM Deal",
			deal.name,
			"bitrix24",
			"shared-id",
			"lead",
		)

		self.assertNotEqual(source_reference.name, type_reference.name)

	def test_external_id_can_repeat_across_external_parents(self):
		first = create_test_deal("External Parent First")
		second = create_test_deal("External Parent Second")

		first_reference = set_external_reference(
			"CRM Deal",
			first.name,
			"amocrm",
			"parent-scoped-id",
			"stage",
			external_parent_id="pipeline-a",
		)
		second_reference = set_external_reference(
			"CRM Deal",
			second.name,
			"amocrm",
			"parent-scoped-id",
			"stage",
			external_parent_id="pipeline-b",
		)

		self.assertNotEqual(first_reference.name, second_reference.name)

	def test_backfill_external_references_from_legacy_fields(self):
		external_pipeline_id = f"legacy-pipeline-{frappe.generate_hash(length=8)}"
		external_status_id = f"legacy-status-{frappe.generate_hash(length=8)}"
		external_record_id = f"legacy-deal-{frappe.generate_hash(length=8)}"
		pipeline = create_test_pipeline(external_pipeline_id)
		stage = create_test_stage(pipeline.name, external_status_id)
		deal = create_test_deal("External Backfill Deal")
		deal.external_source = "amocrm"
		deal.external_record_id = external_record_id
		deal.save()
		clear_reference("CRM Sales Pipeline", pipeline.name)
		clear_reference("CRM Deal Status", stage.name)
		clear_reference("CRM Deal", deal.name)

		stats = backfill_external_references()

		pipeline_reference = find_external_reference(
			"amocrm",
			external_pipeline_id,
			"CRM Sales Pipeline",
		)
		stage_reference = find_external_reference(
			"amocrm",
			external_status_id,
			"CRM Deal Status",
			external_pipeline_id,
		)
		deal_reference = find_external_reference("amocrm", external_record_id, "CRM Deal")

		self.assertGreaterEqual(stats["created"], 3)
		self.assertEqual(pipeline_reference.reference_name, pipeline.name)
		self.assertEqual(stage_reference.reference_name, stage.name)
		self.assertEqual(stage_reference.external_parent_id, external_pipeline_id)
		self.assertEqual(deal_reference.reference_name, deal.name)

	def test_backfill_does_not_overwrite_conflicting_existing_reference(self):
		existing_external_id = f"existing-external-{frappe.generate_hash(length=8)}"
		legacy_external_id = f"legacy-external-{frappe.generate_hash(length=8)}"
		deal = create_test_deal("External Backfill Conflict")
		set_external_reference("CRM Deal", deal.name, "amocrm", existing_external_id, "CRM Deal")
		frappe.db.set_value(
			"CRM Deal",
			deal.name,
			{
				"external_source": "amocrm",
				"external_record_id": legacy_external_id,
			},
			update_modified=False,
		)

		stats = backfill_external_references()

		reference = get_external_reference("CRM Deal", deal.name, "amocrm", "CRM Deal")
		legacy_reference = find_external_reference("amocrm", legacy_external_id, "CRM Deal")

		self.assertEqual(reference.external_id, existing_external_id)
		self.assertIsNone(legacy_reference)
		self.assertGreaterEqual(stats["skipped"], 1)


def create_test_deal(organization_name="External Reference Org"):
	org = frappe.get_doc(
		{
			"doctype": "CRM Organization",
			"organization_name": f"{organization_name} {frappe.generate_hash(length=8)}",
		}
	).insert()
	return frappe.get_doc(
		{
			"doctype": "CRM Deal",
			"organization": org.name,
		}
	).insert()


def create_test_pipeline(external_pipeline_id):
	return frappe.get_doc(
		{
			"doctype": "CRM Sales Pipeline",
			"pipeline_name": f"External Reference Pipeline {frappe.generate_hash(length=8)}",
			"external_source": "amocrm",
			"external_pipeline_id": external_pipeline_id,
			"enabled": 1,
			"position": 99,
		}
	).insert()


def create_test_stage(pipeline, external_status_id):
	return frappe.get_doc(
		{
			"doctype": "CRM Deal Status",
			"deal_status": f"External Reference Stage {frappe.generate_hash(length=8)}",
			"pipeline": pipeline,
			"external_status_id": external_status_id,
			"type": "Open",
			"position": 99,
		}
	).insert()


def clear_reference(reference_doctype, reference_name):
	frappe.db.delete(
		"CRM External Reference",
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		},
	)
