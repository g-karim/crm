import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from crm import touch_tracking as touch
from crm import touch_tracking_ui as ui
from crm.api.doc import get_data, sort_options
from crm.tests import test_touch_tracking_internal as internal_cases


class TestTouchTrackingUI(unittest.TestCase):
	setUp = internal_cases.TestInternalTouchTracking.setUp
	tearDown = internal_cases.TestInternalTouchTracking.tearDown
	create = internal_cases.TestInternalTouchTracking.create
	events = internal_cases.TestInternalTouchTracking.events
	change_status = internal_cases.TestInternalTouchTracking.change_status
	configure = internal_cases.TestInternalTouchTracking.configure
	child = internal_cases.TestInternalTouchTracking.child
	comment = internal_cases.TestInternalTouchTracking.comment
	flush = internal_cases.TestInternalTouchTracking.flush

	def listing(self, doctype="CRM Lead", **kwargs):
		return get_data(
			doctype=doctype,
			filters=kwargs.pop("filters", {}),
			order_by=kwargs.pop("order_by", "modified desc"),
			view=kwargs.pop("view", {"view_type": "list", "default_sort": True}),
			**kwargs,
		)

	def view(self, **values):
		return frappe.get_doc(
			{
				"doctype": "CRM View Settings",
				"dt": "CRM Lead",
				"type": "list",
				"user": "Administrator",
				"is_standard": 1,
				**values,
			}
		).insert()

	def employee(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "touch-stage4@example.invalid",
				"first_name": "Touch UI",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert()
		return user.name

	def test_settings_save_roundtrip_and_stale_write_rejection(self):
		old = ui.get_settings()
		updated = ui.save_settings(
			{"lead_fields": ["website"], "deal_events": ["task_due_date"]}, old["modified"]
		)
		self.assertEqual(updated["settings"]["lead_fields"], ["website"])
		self.assertEqual(updated["settings"]["deal_events"], ["task_due_date"])
		self.assertEqual(updated["settings"]["lead_events"], [])
		with self.assertRaises(frappe.TimestampMismatchError):
			ui.save_settings({"enabled": 0}, old["modified"])
		self.assertEqual(ui.get_settings()["settings"]["enabled"], 1)

	def test_fresh_singleton_has_a_usable_version_token(self):
		frappe.db.delete("Singles", {"doctype": touch.SETTINGS})
		frappe.clear_cache()
		payload = ui.get_settings()
		self.assertEqual(payload["modified"], "")
		self.assertEqual(ui.save_settings({"enabled": 0}, "")["settings"]["enabled"], 0)

	def test_settings_reject_unknown_fields_channels_and_invalid_rules(self):
		for values in (
			{"policy_revision": "fake"},
			{"lead_mail_received": 1},
			{"lead_fields": ["last_touch_at"]},
			{"lead_events": ["fake"]},
		):
			with self.assertRaises(frappe.ValidationError):
				ui.save_settings(values, ui.get_settings()["modified"])

	def test_employee_cannot_read_or_write_site_settings(self):
		frappe.set_user(self.employee())
		with self.assertRaises(frappe.PermissionError):
			ui.get_settings()
		with self.assertRaises(frappe.PermissionError):
			ui.save_settings({"enabled": 0}, "")

	def test_channels_report_missing_app_and_confirmed_success_rules(self):
		with patch.object(frappe, "get_installed_apps", return_value=["frappe", "crm"]):
			channels = ui.get_settings()["channels"]
		self.assertFalse(channels[0]["installed"])
		self.assertIn("Successfully sent message", [rule["label"] for rule in channels[0]["rules"]])
		self.assertIn("failed sends will not count", channels[2]["description"])

	def test_new_lists_use_stable_touch_sort_and_add_the_column(self):
		for doctype in touch.TARGETS:
			records = [self.create(doctype) for _ in range(4)]
			# A null date falls back to creation; ties use creation then name.
			for doc, created, touched in zip(
				records,
				["2026-01-04", "2026-01-03", "2026-01-02", "2026-01-02"],
				[None, "2026-01-05", "2026-01-05", "2026-01-05"],
				strict=True,
			):
				frappe.db.set_value(
					doctype, doc.name, {"creation": created, touch.FIELD: touched}, update_modified=False
				)
			filters = {"name": ["in", [doc.name for doc in records]]}
			result = self.listing(doctype, filters=filters, page_length=3)
			tied = sorted([doc.name for doc in records[2:]], reverse=True)
			self.assertEqual([row.name for row in result["data"]], [records[1].name, *tied])
			self.assertEqual(result["order_by"], ui.DEFAULT_ORDER)
			self.assertIn(touch.FIELD, [column["key"] for column in result["columns"]])
			self.assertIn("creation", result["rows"])
			self.assertEqual(result["total_count"], 4)
			full = self.listing(doctype, filters=filters, page_length=10)
			self.assertEqual(full["data"][-1].name, records[0].name)

	def test_touch_sort_ascending_and_user_filter_are_honored(self):
		one, two = self.create(), self.create()
		frappe.db.set_value(
			one.doctype, one.name, {touch.FIELD: None, "creation": "2026-01-01"}, update_modified=False
		)
		frappe.db.set_value(two.doctype, two.name, {touch.FIELD: "2026-02-01"}, update_modified=False)
		result = self.listing(
			order_by="last_touch_at asc",
			filters={"name": ["in", [one.name, two.name]]},
			view={"view_type": "list"},
		)
		self.assertEqual([row.name for row in result["data"]], [one.name, two.name])
		self.assertEqual(self.listing(filters={"name": two.name})["data"][0].name, two.name)

	def test_selected_kanban_touch_date_includes_its_creation_fallback(self):
		parent = self.create()
		frappe.db.set_value(parent.doctype, parent.name, touch.FIELD, None, update_modified=False)
		result = self.listing(
			filters={"name": parent.name},
			view={"view_type": "kanban", "default_sort": True},
			rows=["name"],
			column_field="status",
			title_field="name",
			kanban_fields=[touch.FIELD],
			kanban_columns=[{"name": "New"}],
		)
		self.assertIn("creation", result["rows"])
		self.assertEqual(get_datetime(result["data"][0]["data"][0].creation), get_datetime(parent.creation))

	def test_explicit_and_saved_standard_sort_and_columns_are_preserved(self):
		columns = [{"key": "first_name", "label": "Name", "type": "Data", "width": "8rem"}]
		view = self.view(order_by="creation asc", columns=json.dumps(columns), rows='["name", "first_name"]')
		before = frappe.get_doc(view.doctype, view.name).as_dict()
		result = self.listing()
		self.assertEqual(result["order_by"], "creation asc")
		self.assertEqual([column["key"] for column in result["columns"]], ["first_name"])
		self.assertEqual(frappe.get_doc(view.doctype, view.name).as_dict(), before)
		self.assertEqual(
			self.listing(order_by="lead_name asc", view={"view_type": "list"})["order_by"], "lead_name asc"
		)
		# Clear sort is an explicit request to use the site default, even while a saved old choice remains.
		self.assertEqual(self.listing(order_by="")["order_by"], ui.DEFAULT_ORDER)

	def test_custom_view_and_foreign_site_view_choices_are_not_reinterpreted(self):
		view = self.view(is_standard=0, order_by="creation asc")
		self.assertEqual(
			ui.resolve_order(
				"CRM Lead", "modified desc", {"default_sort": True, "custom_view_name": view.name}
			),
			"creation asc",
		)
		self.assertEqual(
			ui.resolve_order(
				"CRM Deal", "modified desc", {"default_sort": True, "custom_view_name": view.name}
			),
			ui.DEFAULT_ORDER,
		)
		frappe.db.set_value(view.doctype, view.name, "user", "unrelated@example.invalid")
		self.assertEqual(
			ui.resolve_order(
				"CRM Lead", "modified desc", {"default_sort": True, "custom_view_name": view.name}
			),
			ui.DEFAULT_ORDER,
		)

	def test_disabled_site_keeps_native_default_and_saved_touch_columns(self):
		self.settings.enabled = 0
		self.settings.save()
		result = self.listing()
		self.assertEqual(result["order_by"], "modified desc")
		self.assertNotIn(touch.FIELD, [column["key"] for column in result["columns"]])
		self.assertNotIn(touch.FIELD, [field["value"] for field in sort_options("CRM Lead")])
		columns = [{"key": touch.FIELD, "label": "Last Touch", "type": "Datetime"}]
		self.assertEqual(self.listing(columns=columns, rows=["name"])["columns"][0]["key"], touch.FIELD)

	def test_invalid_touch_sort_cannot_inject_sql_or_sort_a_private_field(self):
		for order in (
			"last_touch_at desc; SELECT 1",
			"last_touch_at desc, unknown desc",
			"last_touch_at sideways",
		):
			with self.assertRaises(frappe.ValidationError):
				ui.list_records("CRM Lead", fields=["name"], filters={}, order_by=order, page_length=20)
		with patch.object(ui, "get_permitted_fields", return_value=["name", "creation"]):
			with self.assertRaises(frappe.PermissionError):
				ui.list_records(
					"CRM Lead", fields=["name"], filters={}, order_by=ui.DEFAULT_ORDER, page_length=20
				)

	def test_list_and_reason_enforce_real_sales_user_document_permissions(self):
		visible, hidden = self.create(), self.create()
		user = self.employee()
		frappe.db.set_value("CRM Lead", visible.name, "lead_owner", user)
		frappe.set_user(user)
		result = self.listing(filters={"name": ["in", [visible.name, hidden.name]]})
		self.assertEqual([row.name for row in result["data"]], [visible.name])
		self.assertEqual(result["total_count"], 1)
		self.assertEqual(ui.get_reason(visible.doctype, visible.name)["reasons"], ["Record created"])
		with self.assertRaises(frappe.PermissionError):
			ui.get_reason(hidden.doctype, hidden.name)

	def test_reason_uses_record_date_with_permission_checked_source(self):
		parent = self.create()
		self.change_status(parent)
		result = ui.get_reason(parent.doctype, parent.name)
		self.assertEqual(result["reasons"], ["Status changed"])
		self.assertEqual(get_datetime(result["date"]), get_datetime(parent.last_touch_at))
		self.assertIn(parent.name, result["source"]["url"])
		self.assertEqual(set(result), {"date", "reasons", "source"})

	def test_creation_fallback_and_migrated_date_have_no_invented_reason(self):
		parent = self.create()
		frappe.db.set_value(parent.doctype, parent.name, touch.FIELD, None, update_modified=False)
		self.assertIsNone(ui.get_reason(parent.doctype, parent.name)["source"])
		frappe.db.set_value(parent.doctype, parent.name, touch.FIELD, "2026-01-01", update_modified=False)
		self.assertEqual(
			ui.get_reason(parent.doctype, parent.name)["reasons"], ["Initial date; no recorded reason"]
		)

	def test_deleted_or_moved_private_source_is_not_disclosed(self):
		self.configure(events=["task_created"])
		parent, private = self.create(), self.create()
		task = self.child(parent)
		self.flush()
		user = self.employee()
		frappe.db.set_value("CRM Lead", parent.name, "lead_owner", user)
		frappe.db.set_value(task.doctype, task.name, "reference_docname", private.name)
		frappe.set_user(user)
		result = ui.get_reason(parent.doctype, parent.name)
		self.assertEqual(result["reasons"], ["Interaction details are unavailable"])
		self.assertIsNone(result["source"])
		frappe.set_user("Administrator")
		frappe.db.delete(task.doctype, {"name": task.name})
		self.assertIsNone(ui.get_reason(parent.doctype, parent.name)["source"])

	def test_field_reasons_are_filtered_without_leaking_values_or_actor(self):
		self.configure(fields=["website", "first_name"])
		parent = self.create()
		parent.website, parent.first_name = "secret-value.invalid", "Secret user value"
		parent.save()
		with patch.object(ui, "get_permitted_fields", return_value=[touch.FIELD, "website"]):
			result = ui.get_reason(parent.doctype, parent.name)
		self.assertEqual(result["reasons"], ["Field changed: Website"])
		self.assertNotIn("Secret", json.dumps(result, default=str))
		self.assertNotIn("secret-value", json.dumps(result, default=str))
		self.assertNotIn("Administrator", json.dumps(result, default=str))

	def test_reason_does_not_follow_a_later_received_older_event(self):
		parent = self.create()
		self.change_status(parent)
		latest = ui.get_reason(parent.doctype, parent.name)
		older = touch._record_event(
			parent.doctype,
			parent.name,
			"Created",
			parent.doctype,
			parent.name,
			get_datetime("2026-01-01"),
			"Administrator",
			touch._policies()[-1],
			source_revision="old",
		)
		touch._apply_safely(older)
		self.assertEqual(ui.get_reason(parent.doctype, parent.name), latest)
