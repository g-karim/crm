# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings import get_deal_quotations


class TestERPNextCRMSettings(UnitTestCase):
	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.get_list")
	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.get_single")
	def test_quotations_are_hidden_when_integration_is_disabled(self, get_single, get_list):
		get_single.return_value = frappe._dict(enabled=0)
		self.assertEqual(get_deal_quotations("DEAL-1"), [])
		get_list.assert_not_called()

	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.has_permission")
	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.get_single")
	def test_quotations_require_deal_read_access(self, get_single, has_permission):
		get_single.return_value = frappe._dict(enabled=1, is_erpnext_in_different_site=0)
		has_permission.return_value = False
		with self.assertRaises(frappe.PermissionError):
			get_deal_quotations("DEAL-1")
		has_permission.assert_called_once_with("CRM Deal", doc="DEAL-1")

	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.get_list")
	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.has_permission")
	@patch("crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.frappe.get_single")
	def test_quotations_require_local_quotation_read_access(self, get_single, has_permission, get_list):
		get_single.return_value = frappe._dict(enabled=1, is_erpnext_in_different_site=0)
		has_permission.side_effect = [True, False]
		self.assertEqual(get_deal_quotations("DEAL-1"), [])
		get_list.assert_not_called()
