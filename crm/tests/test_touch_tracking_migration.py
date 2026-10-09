import copy
import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime, now_datetime

from crm import touch_tracking as touch
from crm import touch_tracking_migration as migration
from crm import touch_tracking_ui as ui
from crm.list_settings import STATUS_SORT_FIELD
from crm.tests import test_touch_tracking_ui as ui_cases


class TestTouchTrackingMigration(unittest.TestCase):
	create = ui_cases.TestTouchTrackingUI.create
	change_status = ui_cases.TestTouchTrackingUI.change_status
	view = ui_cases.TestTouchTrackingUI.view
	employee = ui_cases.TestTouchTrackingUI.employee
	comment = ui_cases.TestTouchTrackingUI.comment
	tearDown = ui_cases.TestTouchTrackingUI.tearDown

	def setUp(self):
		ui_cases.TestTouchTrackingUI.setUp(self)
		self.settings.enabled = 0
		self.settings.save()

	def fixture(self, doctype="CRM Lead"):
		if doctype == "CRM Lead" and not frappe.get_meta(doctype).has_field(STATUS_SORT_FIELD):
			self.skipTest("Requires the disposable site's legacy-sort custom-field fixture")
		doc = self.create(doctype)
		values = {"creation": "2026-01-01 10:00:00", "modified": "2026-09-30 10:00:00"}
		if doctype == "CRM Lead":
			values[STATUS_SORT_FIELD] = "2026-02-01 10:00:00"
		frappe.db.set_value(doctype, doc.name, values, update_modified=False)
		return frappe.get_doc(doctype, doc.name)

	def test_seed_dates_preserve_business_history_metadata_and_legacy_order(self):
		lead, deal = self.fixture(), self.fixture("CRM Deal")
		self.change_status(deal)
		rows = frappe.get_all("CRM Status Change Log", filters={"parent": deal.name}, order_by="idx")
		frappe.db.set_value(
			"CRM Status Change Log", rows[-1].name, "creation", "2026-03-01", update_modified=False
		)
		before = migration._source()
		manifest = migration.prepare()
		events = frappe.db.count(touch.EVENT)
		result = migration.apply(manifest)
		self.assertFalse(result["already_applied"])
		self.assertEqual(frappe.db.count(touch.EVENT), events)
		self.assertEqual(
			frappe.db.get_value(lead.doctype, lead.name, touch.FIELD), get_datetime("2026-02-01 10:00:00")
		)
		self.assertEqual(
			frappe.db.get_value(deal.doctype, deal.name, touch.FIELD), get_datetime("2026-03-01")
		)
		after = migration._source()
		self.assertEqual(before["history"], after["history"])
		self.assertEqual(
			before["targets"],
			{dt: [{**row, touch.FIELD: None} for row in values] for dt, values in after["targets"].items()},
		)
		settings = frappe.get_doc(touch.SETTINGS)
		self.assertEqual(settings.legacy_sort_migration_id, manifest["id"])
		for prefix in ("lead", "deal"):
			for suffix in ("fields", "events", "channels"):
				self.assertEqual(settings.get(f"{prefix}_{suffix}"), "[]")
		self.assertEqual(
			ui.get_reason(lead.doctype, lead.name)["reasons"], ["Initial date; no recorded reason"]
		)

	def test_status_chain_counts_final_open_row_and_ignores_broken_transitions(self):
		rows = [
			dict(
				parent="d",
				parenttype="CRM Deal",
				parentfield="status_change_log",
				idx=i,
				creation=f"2026-01-0{i}",
				**values,
			)
			for i, values in enumerate(
				({"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": ""}), 1
			)
		]
		self.assertEqual(
			list(migration.status_dates(rows, "CRM Deal", "d")),
			[get_datetime("2026-01-02"), get_datetime("2026-01-03")],
		)
		rows[1]["to"] = "different"
		self.assertEqual(list(migration.status_dates(rows, "CRM Deal", "d")), [get_datetime("2026-01-02")])
		rows.append(rows[0].copy())
		with self.assertRaises(ValueError):
			list(migration.status_dates(rows, "CRM Deal", "d"))

	def test_deal_without_credible_history_uses_creation_not_modified(self):
		deal = self.fixture("CRM Deal")
		migration.apply(migration.prepare())
		self.assertEqual(
			frappe.db.get_value(deal.doctype, deal.name, touch.FIELD), get_datetime(deal.creation)
		)

	def test_invalid_legacy_date_refuses_cutover(self):
		lead = self.fixture()
		for value in ("2025-12-01", "2099-01-01"):
			frappe.db.set_value(lead.doctype, lead.name, STATUS_SORT_FIELD, value, update_modified=False)
			with self.assertRaises(ValueError):
				migration.prepare()
		self.assertFalse(frappe.get_doc(touch.SETTINGS).enabled)

	def test_view_migration_changes_only_field_keys_and_keeps_manual_kanban_order(self):
		self.fixture()
		old = self.view(
			order_by=f"{STATUS_SORT_FIELD} desc, creation desc, name desc",
			rows=json.dumps(["name", STATUS_SORT_FIELD]),
			columns=json.dumps(
				[{"key": STATUS_SORT_FIELD, "label": "Created or Status Changed", "width": "8rem"}]
			),
			filters=json.dumps({STATUS_SORT_FIELD: [">", "2026-01-01"]}),
			kanban_fields=json.dumps([STATUS_SORT_FIELD]),
			kanban_columns='[{"name":"New","order":["manual-2","manual-1"]}]',
		)
		explicit = self.view(
			is_standard=0, order_by="  modified desc  ", columns='[{"key":"first_name","label":"Custom"}]'
		)
		before = frappe.get_doc(explicit.doctype, explicit.name).as_dict()
		manifest = migration.prepare()
		migration.apply(manifest)
		after = frappe.get_doc(old.doctype, old.name)
		self.assertEqual(after.order_by, ui.DEFAULT_ORDER)
		self.assertEqual(after.kanban_columns, old.kanban_columns)
		self.assertEqual(get_datetime(after.modified), get_datetime(old.modified))
		self.assertEqual(json.loads(after.filters), {touch.FIELD: [">", "2026-01-01"]})
		self.assertEqual(frappe.get_doc(explicit.doctype, explicit.name).as_dict(), before)
		migration.rollback(manifest)
		self.assertEqual(
			json.dumps(frappe.get_doc(old.doctype, old.name).as_dict(), default=str, sort_keys=True),
			json.dumps(old.as_dict(), default=str, sort_keys=True),
		)

	def test_stale_source_and_modified_preferences_require_new_manifest(self):
		lead = self.fixture()
		manifest = migration.prepare()
		frappe.db.set_value(lead.doctype, lead.name, "status", "Contacted", update_modified=False)
		with self.assertRaises(frappe.TimestampMismatchError):
			migration.apply(manifest)
		self.assertIsNone(frappe.db.get_value(lead.doctype, lead.name, touch.FIELD))
		view = self.view(order_by=f"{STATUS_SORT_FIELD} desc")
		manifest = migration.prepare()
		frappe.db.set_value(view.doctype, view.name, "order_by", "creation asc")
		with self.assertRaises(frappe.TimestampMismatchError):
			migration.apply(manifest)

	def test_manifest_integrity_site_and_verified_seeds_are_checked(self):
		self.fixture()
		manifest = migration.prepare()
		for value in (None, [], {**manifest, "site": "other.localhost"}, {**manifest, "id": "invalid"}):
			with self.assertRaises(frappe.ValidationError):
				migration.apply(value)
		bad = copy.deepcopy(manifest)
		bad["seeds"]["CRM Lead"][0]["date"] = "2026-10-01"
		bad["id"] = migration._digest({key: value for key, value in bad.items() if key != "id"})
		with self.assertRaises(frappe.ValidationError):
			migration.apply(bad)

	def test_late_failure_rolls_back_seed_view_and_controls_atomically(self):
		lead = self.fixture()
		view = self.view(order_by=f"{STATUS_SORT_FIELD} desc")
		manifest = migration.prepare()
		from crm.fcrm.doctype.crm_touch_settings.crm_touch_settings import CRMTouchSettings

		with patch.object(CRMTouchSettings, "save", side_effect=frappe.ValidationError("late failure")):
			with self.assertRaises(frappe.ValidationError):
				migration.apply(manifest)
		self.assertIsNone(frappe.db.get_value(lead.doctype, lead.name, touch.FIELD))
		self.assertEqual(frappe.db.get_value(view.doctype, view.name, "order_by"), view.order_by)
		self.assertFalse(frappe.get_doc(touch.SETTINGS).legacy_sort_retired)

	def test_fatal_database_abort_is_not_hidden_or_partially_retried(self):
		self.fixture()
		manifest = migration.prepare()
		with (
			patch.object(migration, "_targets", side_effect=frappe.QueryDeadlockError("abort")),
			patch.object(frappe.db, "rollback") as partial_rollback,
		):
			with self.assertRaises(frappe.QueryDeadlockError):
				migration.apply(manifest)
			partial_rollback.assert_not_called()
		self.assertFalse(frappe.get_doc(touch.SETTINGS).enabled)

	def test_repeated_apply_preserves_newer_touches_and_user_choices(self):
		lead = self.fixture()
		view = self.view(order_by=f"{STATUS_SORT_FIELD} desc")
		manifest = migration.prepare()
		migration.apply(manifest)
		self.change_status(lead.reload())
		frappe.db.set_value(view.doctype, view.name, "order_by", "first_name asc")
		before = migration._source()
		self.assertTrue(migration.apply(manifest)["already_applied"])
		self.assertEqual(migration._source(), before)

	def test_background_date_between_prepare_and_apply_is_not_overwritten(self):
		lead = self.fixture()
		manifest = migration.prepare()
		frappe.db.set_value(lead.doctype, lead.name, touch.FIELD, "2026-08-01", update_modified=False)
		migration.apply(manifest)
		self.assertEqual(
			frappe.db.get_value(lead.doctype, lead.name, touch.FIELD), get_datetime("2026-08-01")
		)

	def test_rollback_keeps_new_business_rows_dates_audit_and_updated_preferences(self):
		lead = self.fixture()
		view = self.view(order_by=f"{STATUS_SORT_FIELD} desc")
		manifest = migration.prepare()
		migration.apply(manifest)
		self.change_status(lead.reload())
		status_at = frappe.db.get_value(lead.doctype, lead.name, touch.FIELD)
		self.assertEqual(get_datetime(lead.get(STATUS_SORT_FIELD)), get_datetime("2026-02-01 10:00:00"))
		self.settings.reload()
		self.settings.lead_events = '["comment_created"]'
		self.settings.save()
		self.comment(lead)
		touch.maintenance()
		new = self.create()
		frappe.db.set_value(view.doctype, view.name, "order_by", "first_name asc")
		before = migration._source()
		events = frappe.db.count(touch.EVENT)
		result = migration.rollback(manifest)
		self.assertEqual(result["new_view_choices_preserved"], [f"{view.name}:order_by"])
		self.assertTrue(frappe.db.exists(new.doctype, new.name))
		self.assertEqual(frappe.db.count(touch.EVENT), events)
		after = migration._source()
		self.assertEqual(before["history"], after["history"])
		for dt in touch.TARGETS:
			for old, current in zip(before["targets"][dt], after["targets"][dt], strict=True):
				self.assertEqual(
					{k: v for k, v in old.items() if k != STATUS_SORT_FIELD},
					{k: v for k, v in current.items() if k != STATUS_SORT_FIELD},
				)
		self.assertEqual(frappe.db.get_value(lead.doctype, lead.name, STATUS_SORT_FIELD), status_at)
		self.assertTrue(migration.rollback(manifest)["already_rolled_back"])
		settings = frappe.get_doc(touch.SETTINGS)
		self.assertFalse(settings.enabled)
		self.assertFalse(settings.legacy_sort_retired)
		new.reload()
		self.change_status(new)
		self.assertEqual(get_datetime(new.get(STATUS_SORT_FIELD)), get_datetime(new.modified))

	def test_disable_after_cutover_keeps_legacy_writer_retired(self):
		lead = self.fixture()
		migration.apply(migration.prepare())
		settings = frappe.get_doc(touch.SETTINGS)
		settings.enabled = 0
		settings.legacy_sort_retired = 0
		settings.legacy_sort_migration_id = "forged"
		settings.save()
		self.assertTrue(settings.legacy_sort_retired)
		self.assertNotEqual(settings.legacy_sort_migration_id, "forged")
		self.change_status(lead.reload())
		self.assertEqual(get_datetime(lead.get(STATUS_SORT_FIELD)), get_datetime("2026-02-01 10:00:00"))

	def test_only_system_manager_can_run_non_public_cutover_operations(self):
		manifest = migration.prepare()
		frappe.set_user(self.employee())
		for operation, args in (
			(migration.prepare, ()),
			(migration.apply, (manifest,)),
			(migration.rollback, (manifest,)),
		):
			with self.assertRaises(frappe.PermissionError):
				operation(*args)
		self.assertNotIn(migration.apply, frappe.whitelisted)
