# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from crm.api.sales_pipeline import (
	archive_pipeline,
	duplicate_pipeline,
	get_default_stage_templates,
	get_pipeline_settings,
	save_pipeline,
)
from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import (
	get_default_deal_stage_label,
	get_default_deal_stage_templates,
	get_default_pipeline_label,
	resolve_sales_pipeline,
)
from crm.fcrm.doctype.crm_external_reference.crm_external_reference import find_external_reference


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

	def test_external_pipeline_id_must_be_unique(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Pipeline One {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 98,
			}
		).insert()

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(
				{
					"doctype": "CRM Sales Pipeline",
					"pipeline_name": f"External Pipeline Two {frappe.generate_hash(length=8)}",
					"external_source": "bitrix24",
					"external_pipeline_id": external_pipeline_id,
					"enabled": 1,
					"position": 99,
				}
				).insert()

	def test_external_pipeline_id_requires_external_source(self):
		with self.assertRaises(frappe.exceptions.ValidationError):
			frappe.get_doc(
				{
					"doctype": "CRM Sales Pipeline",
					"pipeline_name": f"External Source Required {frappe.generate_hash(length=8)}",
					"external_pipeline_id": f"external-pipeline-{frappe.generate_hash(length=8)}",
					"enabled": 1,
					"position": 98,
				}
			).insert()

	def test_external_pipeline_id_can_repeat_across_sources(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
		first = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Source One {frappe.generate_hash(length=8)}",
				"external_source": "amocrm",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 98,
			}
		).insert()
		second = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"External Source Two {frappe.generate_hash(length=8)}",
				"external_source": "bitrix24",
				"external_pipeline_id": external_pipeline_id,
				"enabled": 1,
				"position": 99,
			}
		).insert()

		self.assertNotEqual(first.name, second.name)

	def test_external_pipeline_id_writes_external_reference(self):
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

		reference = find_external_reference(
			"bitrix24",
			external_pipeline_id,
			"CRM Sales Pipeline",
		)

		self.assertEqual(reference.reference_doctype, "CRM Sales Pipeline")
		self.assertEqual(reference.reference_name, pipeline.name)

	def test_resolve_pipeline_reads_external_reference_before_legacy_fields(self):
		external_pipeline_id = f"external-pipeline-{frappe.generate_hash(length=8)}"
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
		frappe.db.set_value(
			"CRM Sales Pipeline",
			pipeline.name,
			"external_pipeline_id",
			None,
			update_modified=False,
		)

		resolved = resolve_sales_pipeline(
			external_pipeline_id=external_pipeline_id,
			external_source="bitrix24",
		)

		self.assertEqual(resolved, pipeline.name)

	def test_default_pipeline_seed_labels_stay_canonical(self):
		previous_lang = frappe.db.get_default("lang")
		try:
			frappe.db.set_default("lang", "ru")
			self.assertEqual(get_default_pipeline_label(), "Default Deal Pipeline")
			self.assertEqual(get_default_deal_stage_label("Qualification"), "Qualification")
			self.assertEqual(get_default_deal_stage_label("Won"), "Won")
			self.assertEqual(
				[stage["deal_status"] for stage in get_default_deal_stage_templates()],
				[
					"Qualification",
					"Demo/Making",
					"Proposal/Quotation",
					"Negotiation",
					"Ready to Close",
					"Won",
					"Lost",
				],
			)
		finally:
			frappe.db.set_default("lang", previous_lang or "en")

	def test_default_stage_templates_api_returns_standard_stage_config(self):
		templates = get_default_stage_templates()

		self.assertEqual(len(templates), 7)
		self.assertEqual(templates[0]["deal_status"], "Qualification")
		self.assertEqual(templates[0]["type"], "Open")
		self.assertEqual(templates[0]["position"], 1)
		self.assertEqual(templates[-1]["deal_status"], "Lost")
		self.assertEqual(templates[-1]["type"], "Lost")

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

	def test_default_pipeline_cannot_be_archived_from_api(self):
		default_pipeline = frappe.db.get_value(
			"CRM Sales Pipeline",
			{"is_default": 1, "enabled": 1, "archived": 0},
			"name",
		)

		with self.assertRaises(frappe.exceptions.ValidationError):
			archive_pipeline(default_pipeline, 1)

	def test_last_active_pipeline_cannot_be_archived(self):
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Only Active Pipeline {frappe.generate_hash(length=8)}",
				"enabled": 1,
				"position": 199,
			}
		).insert()
		frappe.db.set_value(
			"CRM Sales Pipeline",
			{"name": ["!=", pipeline.name]},
			{
				"enabled": 0,
				"archived": 1,
				"is_default": 0,
			},
			update_modified=False,
		)

		with self.assertRaises(frappe.exceptions.ValidationError):
			archive_pipeline(pipeline.name, 1)

	def test_restoring_pipeline_enables_it(self):
		pipeline = frappe.get_doc(
			{
				"doctype": "CRM Sales Pipeline",
				"pipeline_name": f"Restore Pipeline {frappe.generate_hash(length=8)}",
				"enabled": 0,
				"archived": 1,
				"position": 199,
			}
		).insert()

		restored = archive_pipeline(pipeline.name, 0)

		self.assertFalse(restored.archived)
		self.assertTrue(restored.enabled)

	def test_pipeline_with_active_deals_requires_force_to_archive(self):
		pipeline = create_pipeline("Active Deals Pipeline")
		stage = create_stage(pipeline.name, "Ongoing")
		create_deal(pipeline.name, stage.name)

		with self.assertRaises(frappe.exceptions.ValidationError):
			archive_pipeline(pipeline.name, 1)

		archived = archive_pipeline(pipeline.name, 1, force=1)

		self.assertTrue(archived.archived)
		self.assertFalse(archived.enabled)

	def test_sales_manager_cannot_force_archive_pipeline_with_active_deals(self):
		pipeline = create_pipeline("Manager Force Pipeline")
		stage = create_stage(pipeline.name, "Ongoing")
		create_deal(pipeline.name, stage.name)
		user = create_user_with_roles(
			f"pipeline-manager-{frappe.generate_hash(length=8)}@example.com",
			["Sales Manager"],
		)

		try:
			frappe.set_user(user.name)
			with self.assertRaises(frappe.PermissionError):
				archive_pipeline(pipeline.name, 1, force=1)
		finally:
			frappe.set_user("Administrator")

	def test_pipeline_settings_returns_active_deal_counts(self):
		pipeline = create_pipeline("Active Count Pipeline")
		active_stage = create_stage(pipeline.name, "On Hold")
		won_stage = create_stage(pipeline.name, "Won", position=2)
		create_deal(pipeline.name, active_stage.name)
		create_deal(pipeline.name, won_stage.name)

		settings = get_pipeline_settings(show_archived=1)

		self.assertEqual(settings["active_deal_counts"].get(pipeline.name), 1)
		self.assertTrue(settings["can_force_archive"])

	def test_pipeline_settings_returns_freeze_effect_flag(self):
		pipeline = create_pipeline("Freeze Flag Pipeline", enable_kanban_freeze_effect=0)

		settings = get_pipeline_settings(show_archived=1)
		row = next(item for item in settings["pipelines"] if item.name == pipeline.name)

		self.assertEqual(row.enable_kanban_freeze_effect, 0)

	def test_save_pipeline_updates_freeze_effect_flag(self):
		pipeline = create_pipeline("Save Freeze Flag Pipeline")

		saved = save_pipeline(
			{
				"name": pipeline.name,
				"pipeline_name": pipeline.pipeline_name,
				"enable_kanban_freeze_effect": 0,
			}
		)

		self.assertEqual(saved.enable_kanban_freeze_effect, 0)
		self.assertEqual(
			frappe.db.get_value(
				"CRM Sales Pipeline",
				pipeline.name,
				"enable_kanban_freeze_effect",
			),
			0,
		)

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
				"stage_skip_rule": "Warn",
				"stage_backwards_rule": "Block",
				"closing_fields_rule": "Warn",
				"required_fields_before_closing": "contact, expected_closure_date",
				"enable_kanban_freeze_effect": 0,
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
		self.assertEqual(duplicate.stage_skip_rule, "Warn")
		self.assertEqual(duplicate.stage_backwards_rule, "Block")
		self.assertEqual(duplicate.closing_fields_rule, "Warn")
		self.assertEqual(duplicate.required_fields_before_closing, "contact, expected_closure_date")
		self.assertEqual(duplicate.enable_kanban_freeze_effect, 0)


def create_pipeline(title, **kwargs):
	data = {
		"doctype": "CRM Sales Pipeline",
		"pipeline_name": f"{title} {frappe.generate_hash(length=8)}",
		"enabled": 1,
		"position": 199,
	}
	data.update(kwargs)
	return frappe.get_doc(data).insert()


def create_stage(pipeline, stage_type="Open", **kwargs):
	data = {
		"doctype": "CRM Deal Status",
		"deal_status": f"{stage_type} Stage {frappe.generate_hash(length=8)}",
		"pipeline": pipeline,
		"type": stage_type,
		"position": 1,
		"probability": 10,
	}
	data.update(kwargs)
	return frappe.get_doc(data).insert()


def create_deal(pipeline, status):
	return frappe.get_doc(
		{
			"doctype": "CRM Deal",
			"deal_name": f"Pipeline Deal {frappe.generate_hash(length=8)}",
			"pipeline": pipeline,
			"status": status,
		}
	).insert()


def create_user_with_roles(email, roles):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Pipeline",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	existing_roles = {role.role for role in user.roles}
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return user
