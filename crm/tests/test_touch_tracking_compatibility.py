import csv
import io
import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime
from openpyxl import load_workbook

from crm import touch_tracking as touch
from crm import touch_tracking_export as export
from crm import touch_tracking_ui as ui
from crm.tests import test_touch_tracking_ui as ui_cases


class TestTouchTrackingCompatibility(unittest.TestCase):
	setUp = ui_cases.TestTouchTrackingUI.setUp
	tearDown = ui_cases.TestTouchTrackingUI.tearDown
	create = ui_cases.TestTouchTrackingUI.create
	listing = ui_cases.TestTouchTrackingUI.listing
	employee = ui_cases.TestTouchTrackingUI.employee

	def records(self, doctype="CRM Lead"):
		records = [self.create(doctype) for _ in range(3)]
		for doc, created, date in zip(
			records,
			["2026-03-01", "2026-02-01", "2026-01-01"],
			[None, "2026-04-01", "2026-04-01"],
			strict=True,
		):
			frappe.db.set_value(
				doctype, doc.name, {"creation": created, touch.FIELD: date}, update_modified=False
			)
		return records

	def download(self, doctype="CRM Lead", **values):
		params = dict(
			doctype=doctype,
			fields=json.dumps(["name", touch.FIELD]),
			filters="{}",
			order_by=ui.DEFAULT_ORDER,
			file_format_type="CSV",
			title="Touch export",
			page_length="0",
			start="0",
			view="Report",
		)
		params.update(values)
		with (
			patch.object(frappe.local, "form_dict", frappe._dict(params)),
			patch.object(frappe.local, "response", frappe._dict()),
			patch.object(frappe, "in_test", True),
		):
			export.export_query()
			return dict(frappe.response)

	def csv_rows(self, **kwargs):
		content = self.download(**kwargs)["filecontent"]
		return list(
			csv.reader(io.StringIO(content.decode("utf-8-sig") if isinstance(content, bytes) else content))
		)

	def test_csv_and_excel_match_visible_order_fallback_and_permissions(self):
		for dt in touch.TARGETS:
			one, two, three = self.records(dt)
			names = [one.name, two.name, three.name]
			filters = json.dumps({"name": ["in", names]})
			visible = self.listing(dt, filters=json.loads(filters))["data"]
			rows = self.csv_rows(doctype=dt, filters=filters)
			self.assertEqual([row[1] for row in rows[1:]], [row.name for row in visible])
			self.assertEqual(get_datetime(rows[-1][2]), get_datetime("2026-03-01"))
			file = self.download(dt, file_format_type="Excel", filters=filters)
			book = load_workbook(io.BytesIO(file["filecontent"]))
			values = list(book.active.values)
			self.assertEqual([row[1] for row in values[1:]], [two.name, three.name, one.name])
			self.assertEqual(get_datetime(values[-1][2]), get_datetime("2026-03-01"))
			self.assertGreater(frappe.db.count("Access Log", {"export_from": dt}), 0)

	def test_selection_intersects_filters_and_export_pagination_uses_fallback(self):
		one, two, three = self.records()
		rows = self.csv_rows(
			filters=json.dumps({"name": ["in", [one.name, two.name]]}),
			selected_items=json.dumps([two.name, three.name]),
		)
		self.assertEqual([row[1] for row in rows[1:]], [two.name])
		rows = self.csv_rows(
			start="1", page_length="1", filters=json.dumps({"name": ["in", [one.name, two.name, three.name]]})
		)
		self.assertEqual([row[1] for row in rows[1:]], [three.name])

	def test_export_reuses_crm_phone_suffix_normalization(self):
		one, two = self.create(), self.create()
		frappe.db.set_value(one.doctype, one.name, "mobile_no", "+7 (903) 123-45-67")
		frappe.db.set_value(two.doctype, two.name, "mobile_no", "+7 999 123 00 00")
		rows = self.csv_rows(filters=json.dumps({"mobile_no": ["like", "%4567%"]}))
		self.assertEqual([row[1] for row in rows[1:]], [one.name])

	def test_group_by_and_kanban_fallback_and_manual_order_remain_consistent(self):
		for dt in touch.TARGETS:
			one, two, three = self.records(dt)
			filters = {"name": ["in", [one.name, two.name, three.name]]}
			group = self.listing(
				dt,
				filters=filters,
				view={"view_type": "group_by", "group_by_field": "status", "default_sort": True},
			)
			self.assertEqual([row.name for row in group["data"]], [two.name, three.name, one.name])
			self.assertEqual(group["group_by_field"]["fieldname"], "status")
			columns = [{"name": one.status}]
			params = dict(
				filters=filters,
				view={"view_type": "kanban", "default_sort": True},
				rows=["name"],
				column_field="status",
				title_field="name",
				kanban_fields=[touch.FIELD],
			)
			kanban = self.listing(dt, **params, kanban_columns=columns)
			self.assertEqual(
				[row.name for row in kanban["data"][0]["data"]], [two.name, three.name, one.name]
			)
			manual = [one.name, three.name, two.name]
			kanban = self.listing(dt, **params, kanban_columns=[{"name": one.status, "order": manual}])
			self.assertEqual([row.name for row in kanban["data"][0]["data"]], manual)

	def test_group_kanban_export_enforce_actual_employee_record_access(self):
		user = self.employee()
		for dt in touch.TARGETS:
			visible, hidden = self.create(dt), self.create(dt)
			owner_field = "lead_owner" if dt == "CRM Lead" else "deal_owner"
			frappe.db.set_value(dt, visible.name, owner_field, user)
			frappe.set_user(user)
			filters = {"name": ["in", [visible.name, hidden.name]]}
			group = self.listing(
				dt,
				filters=filters,
				view={"view_type": "group_by", "group_by_field": "status", "default_sort": True},
			)
			self.assertEqual([row.name for row in group["data"]], [visible.name])
			kanban = self.listing(
				dt,
				filters=filters,
				view={"view_type": "kanban", "default_sort": True},
				rows=["name"],
				column_field="status",
				title_field="name",
				kanban_fields=[touch.FIELD],
				kanban_columns=[{"name": visible.status, "order": [hidden.name, visible.name]}],
			)
			self.assertEqual([row.name for row in kanban["data"][0]["data"]], [visible.name])
			rows = self.csv_rows(doctype=dt, filters=json.dumps(filters))
			self.assertEqual([row[1] for row in rows[1:]], [visible.name])
			with patch("frappe.permissions.can_export", return_value=False):
				with self.assertRaises(frappe.PermissionError):
					self.download(dt)
			frappe.set_user("Administrator")

	def test_owner_only_export_cannot_export_another_owners_readable_record(self):
		parent = self.create()
		user = self.employee()
		frappe.db.set_value(parent.doctype, parent.name, "lead_owner", user)
		frappe.set_user(user)
		with patch("frappe.permissions.can_export", side_effect=lambda dt, is_owner=False: is_owner):
			with self.assertRaises(frappe.PermissionError):
				self.download(filters=json.dumps({"name": parent.name}))
			frappe.set_user("Administrator")
			frappe.db.set_value(parent.doctype, parent.name, "owner", user, update_modified=False)
			frappe.set_user(user)
			self.assertEqual(self.csv_rows(filters=json.dumps({"name": parent.name}))[1][1], parent.name)

	def test_other_doctypes_and_explicit_sort_keep_the_framework_export(self):
		self.settings.enabled = 0
		self.settings.save()
		for dt, order in (
			("CRM Lead", "creation desc"),
			("CRM Deal", "modified desc"),
			("CRM Contact", "modified desc"),
		):
			with patch.object(export.reportview, "export_query") as native:
				self.download(dt, fields='["name"]', order_by=order)
				native.assert_called_once()

	def test_sql_fields_unsupported_parameters_and_private_sort_are_rejected(self):
		for params in (
			{"fields": '["name", "count(name)"]'},
			{"order_by": "last_touch_at desc; select 1"},
			{"or_filters": '{"name":"x"}'},
			{"export_in_background": "1"},
		):
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError, frappe.DataError)):
				self.download(**params)
		with patch.object(ui, "get_permitted_fields", return_value=["name", "creation"]):
			with self.assertRaises(frappe.PermissionError):
				self.download()
