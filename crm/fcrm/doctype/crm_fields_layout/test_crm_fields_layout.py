# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase

from crm.patches.v1_0.reorganize_deal_data_layouts import execute


class TestCRMFieldsLayout(IntegrationTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_reorganize_deal_layout_creates_missing_data_layout(self):
		if frappe.db.exists("CRM Fields Layout", "CRM Deal-Data Fields"):
			frappe.delete_doc("CRM Fields Layout", "CRM Deal-Data Fields", ignore_permissions=True)

		execute()

		layout = json.loads(frappe.db.get_value("CRM Fields Layout", "CRM Deal-Data Fields", "layout"))
		fields = get_layout_fields(layout)

		self.assertEqual(layout[0].get("name"), "overview_tab")
		self.assertIn("deal_name", fields)
		self.assertIn("pipeline", fields)

	def test_reorganize_deal_layout_preserves_custom_layout(self):
		custom_layout = [
			{
				"label": "Custom",
				"name": "custom_section",
				"columns": [
					{
						"name": "custom_column",
						"fields": ["organization", "custom_marker"],
					}
				],
			}
		]
		upsert_fields_layout("CRM Deal-Data Fields", "Data Fields", custom_layout)

		execute()

		layout = json.loads(frappe.db.get_value("CRM Fields Layout", "CRM Deal-Data Fields", "layout"))
		fields = get_layout_fields(layout)

		self.assertEqual(layout[0].get("name"), "custom_section")
		self.assertIn("custom_marker", fields)
		self.assertIn("deal_name", fields)
		self.assertIn("pipeline", fields)
		self.assertIn("status", fields)


def upsert_fields_layout(name, layout_type, layout):
	if frappe.db.exists("CRM Fields Layout", name):
		doc = frappe.get_doc("CRM Fields Layout", name)
	else:
		doc = frappe.new_doc("CRM Fields Layout")
		doc.name = name
		doc.dt = "CRM Deal"
		doc.type = layout_type

	doc.layout = json.dumps(layout)
	doc.save(ignore_permissions=True)


def get_layout_fields(layout):
	return [
		field
		for section in iter_layout_sections(layout)
		for column in section.get("columns") or []
		for field in column.get("fields") or []
	]


def iter_layout_sections(layout):
	for item in layout:
		if item.get("sections"):
			for section in item.get("sections") or []:
				yield section
		else:
			yield item
