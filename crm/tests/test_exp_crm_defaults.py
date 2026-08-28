import frappe
from frappe.tests import IntegrationTestCase

from crm.branding import APP_FAVICON_URL, APP_LOGO_URL, APP_NAME, ensure_crm_branding_defaults
from crm.cleanup import cleanup_exp_theme_crm_state
from crm.desk import hide_legacy_erpnext_crm
from crm.dropdown import ensure_crm_dropdown_items


class TestEXPCRMDefaults(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_branding_defaults_replace_only_legacy_values(self):
		settings = frappe.get_single("FCRM Settings")
		settings.brand_name = "Frappe CRM"
		settings.brand_logo = "/assets/exp_theme/img/exp-favicon.png"
		settings.favicon = "/assets/crm/images/logo.svg"
		settings.save(ignore_permissions=True)

		ensure_crm_branding_defaults()
		settings.reload()

		self.assertEqual(settings.brand_name, APP_NAME)
		self.assertEqual(settings.brand_logo, APP_LOGO_URL)
		self.assertEqual(settings.favicon, APP_FAVICON_URL)

	def test_branding_defaults_preserve_custom_branding(self):
		settings = frappe.get_single("FCRM Settings")
		settings.brand_name = "Customer CRM"
		settings.brand_logo = "/files/customer-logo.png"
		settings.favicon = "/files/customer-favicon.ico"
		settings.save(ignore_permissions=True)

		ensure_crm_branding_defaults()
		settings.reload()

		self.assertEqual(settings.brand_name, "Customer CRM")
		self.assertEqual(settings.brand_logo, "/files/customer-logo.png")
		self.assertEqual(settings.favicon, "/files/customer-favicon.ico")

	def test_hide_legacy_erpnext_crm_desktop_icon_but_not_frappe_crm_app(self):
		self.ensure_desktop_icon(
			"CRM",
			{
				"label": "CRM",
				"app": "erpnext",
				"link_to": "CRM",
				"hidden": 0,
				"standard": 1,
				"icon_type": "Link",
			},
		)
		self.ensure_desktop_icon(
			"Frappe CRM",
			{
				"label": APP_NAME,
				"app": "crm",
				"hidden": 0,
				"standard": 1,
				"icon_type": "App",
				"logo_url": APP_LOGO_URL,
			},
		)

		hide_legacy_erpnext_crm()

		self.assertEqual(frappe.db.get_value("Desktop Icon", "CRM", "hidden"), 1)
		self.assertEqual(frappe.db.get_value("Desktop Icon", "Frappe CRM", "hidden"), 0)

	def test_hide_legacy_erpnext_crm_workspace(self):
		if not frappe.db.table_exists("Workspace"):
			return

		workspace = self.ensure_workspace(
			"CRM",
			{
				"label": "CRM",
				"title": "CRM",
				"module": "CRM",
				"app": "erpnext",
				"public": 1,
				"is_hidden": 0,
			},
		)

		hide_legacy_erpnext_crm()

		self.assertEqual(frappe.db.get_value("Workspace", workspace.name, "is_hidden"), 1)

	def test_cleanup_exp_theme_crm_state_is_idempotent(self):
		cleanup_exp_theme_crm_state()
		cleanup_exp_theme_crm_state()

		self.assertEqual(frappe.db.get_single_value("FCRM Settings", "brand_name"), APP_NAME)
		self.assertFalse(
			frappe.get_all(
				"CRM Dropdown Item",
				filters={"name1": ["in", ["app_selector", "about", "login_to_fc"]]},
				pluck="name",
			)
		)

	def ensure_desktop_icon(self, name, values):
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, values, update_modified=False)
			return frappe.get_doc("Desktop Icon", name)

		doc = frappe.get_doc({"doctype": "Desktop Icon", "name": name, **values})
		doc.insert(ignore_permissions=True)
		return doc

	def ensure_workspace(self, name, values):
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, values, update_modified=False)
			return frappe.get_doc("Workspace", name)

		doc = frappe.get_doc({"doctype": "Workspace", "name": name, **values})
		doc.insert(ignore_permissions=True)
		return doc
