import re
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from crm.list_settings import (
	STATUS_SORT_FIELD,
	normalize_phone_filters,
	phone_like_pattern,
	phone_search_condition,
	update_lead_sort_date,
)


class TestPhoneFilters(unittest.TestCase):
	def setUp(self):
		self.search_condition = patch(
			"crm.list_settings.phone_search_condition",
			side_effect=lambda dt, field, pattern: [
				["mobile_no", "regex", pattern],
				"or",
				["phone", "regex", pattern],
			],
		)
		self.search_condition.start()
		self.addCleanup(self.search_condition.stop)

	def test_suffix_matches_formatted_numbers(self):
		pattern = phone_like_pattern("%9205%")
		for value in ("+79991239205", "+7 (999) 123-92-05", "8 999 123 92 05"):
			self.assertIsNotNone(re.search(pattern, value))
		self.assertIsNone(re.search(pattern, "+799912392105"))

	def test_both_fields_keep_other_filters_and_do_not_mutate_input(self):
		original = {"mobile_no": ["LIKE", "%9205%"], "status": "New", "converted": 0}
		result = normalize_phone_filters("CRM Lead", original)
		self.assertEqual(result[0][0][:2], ["mobile_no", "regex"])
		self.assertEqual(result[0][2][:2], ["phone", "regex"])
		self.assertEqual(result[1:], [["status", "=", "New"], ["converted", "=", 0]])
		self.assertEqual(original["mobile_no"], ["LIKE", "%9205%"])

	def test_deal_and_kanban_filters(self):
		result = normalize_phone_filters(
			"CRM Deal", [["CRM Deal", "phone", "like", "%1234%"], ["CRM Deal", "status", "=", "Open"]]
		)
		self.assertEqual(result[0][1], "or")
		self.assertEqual(result[1], ["CRM Deal", "status", "=", "Open"])

	def test_exact_and_non_phone_filters_stay_unchanged(self):
		for dt, filters in (
			("CRM Lead", {"phone": ["=", "1234"]}),
			("CRM Lead", {"email": ["like", "%1234%"]}),
			("Contact", {"phone": ["like", "%1234%"]}),
			("CRM Lead", {"phone": ["like", "%x'%"]}),
		):
			self.assertIs(normalize_phone_filters(dt, filters), filters)

	def test_wildcard_anchors_and_invalid_input(self):
		self.assertIsNone(re.search(phone_like_pattern("1234%"), "+79991234"))
		self.assertIsNone(re.search(phone_like_pattern("%1234"), "+799912345"))
		for value in ("%12%34%", "%12_34%", "%()+%", "%abc%", None):
			self.assertIsNone(phone_like_pattern(value))


class TestLeadSortDate(unittest.TestCase):
	def make_doc(self, *, field_exists=True, new=False, status_changed=False):
		doc = MagicMock()
		doc.meta.has_field.return_value = field_exists
		doc.is_new.return_value = new
		doc.has_value_changed.return_value = status_changed
		doc.get.return_value = "2026-10-08 12:00:00"
		return doc

	def test_creation_and_status_change_update_sort_date(self):
		for kwargs in ({"new": True}, {"status_changed": True}):
			doc = self.make_doc(**kwargs)
			update_lead_sort_date(doc)
			doc.set.assert_called_once_with(STATUS_SORT_FIELD, "2026-10-08 12:00:00")

	def test_other_edits_do_not_update_sort_date(self):
		doc = self.make_doc()
		update_lead_sort_date(doc)
		doc.set.assert_not_called()
		doc.has_value_changed.assert_called_once_with("status")

	def test_other_sites_are_unchanged(self):
		doc = self.make_doc(field_exists=False, status_changed=True)
		update_lead_sort_date(doc)
		doc.set.assert_not_called()


class TestPhoneSearchPermissions(unittest.TestCase):
	def test_only_permitted_phone_fields_are_searched(self):
		import frappe
		from pypika import Table

		with (
			patch.object(frappe, "qb", SimpleNamespace(DocType=lambda dt: Table("tab" + dt))),
			patch("frappe.model.get_permitted_fields", return_value=["mobile_no"]),
		):
			condition = phone_search_condition("CRM Lead", "mobile_no", "1[^0-9]*2")
		self.assertIn("REGEXP", condition.get_sql())
		self.assertNotIn(".phone", condition.get_sql())

	def test_requested_field_without_permission_is_rejected(self):
		import frappe

		with (
			patch("frappe.model.get_permitted_fields", return_value=["mobile_no"]),
			patch.object(frappe, "_", side_effect=lambda value: value),
			patch.object(frappe, "throw", side_effect=frappe.PermissionError),
			self.assertRaises(frappe.PermissionError),
		):
			phone_search_condition("CRM Lead", "phone", "1234")
