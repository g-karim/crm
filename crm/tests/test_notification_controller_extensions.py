"""Real native controllers, unchanged CRM list metadata and cooperative extensions."""

import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.contacts.doctype.contact.contact import Contact
from frappe.email.doctype.email_template.email_template import EmailTemplate
from frappe.model.base_document import get_controller

from crm.overrides.contact import ContactListMixin, CustomContact
from crm.overrides.email_template import CustomEmailTemplate, EmailTemplateListMixin


class OtherListExtension:
	@classmethod
	def default_list_data(cls):
		return {**super().default_list_data(), "other_extension": True}


class TestNotificationControllerExtensions(unittest.TestCase):
	def setUp(self):
		self.assertEqual(frappe.local.site, "notifications.localhost")
		self.assertTrue(frappe.flags.exp_notification_rollback_tests)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		for doctype in ["Contact", "Email Template"]:
			frappe.controllers.setdefault(frappe.local.site, {}).pop(doctype, None)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.db.after_rollback.reset()
		for doctype in ["Contact", "Email Template"]:
			frappe.controllers.setdefault(frappe.local.site, {}).pop(doctype, None)

	def test_contact_keeps_native_validation_and_crm_list_metadata(self):
		controller = get_controller("Contact")
		self.assertTrue(issubclass(controller, Contact))
		self.assertTrue(issubclass(controller, ContactListMixin))
		self.assertIs(controller.validate, Contact.validate)
		contact = frappe.get_doc({"doctype": "Contact", "first_name": "Local", "last_name": uuid4().hex})
		contact.append("email_ids", {"email_id": "local-contact@example.invalid", "is_primary": 1})
		contact.insert()
		self.assertEqual(contact.email_id, "local-contact@example.invalid")
		self.assertEqual(contact.full_name, f"Local {contact.last_name}")
		self.assertEqual(
			[c["key"] for c in controller.default_list_data()["columns"]],
			["full_name", "email_id", "mobile_no", "company_name", "modified"],
		)
		self.assertEqual(CustomContact.default_list_data(), controller.default_list_data())

	def test_contact_still_rejects_two_primary_addresses(self):
		contact = frappe.get_doc({"doctype": "Contact", "first_name": "Local invalid primary"})
		for address in ["one@example.invalid", "two@example.invalid"]:
			contact.append("email_ids", {"email_id": address, "is_primary": 1})
		with self.assertRaises(frappe.ValidationError):
			contact.insert()

	def test_email_template_keeps_native_jinja_validation_and_rendering(self):
		controller = get_controller("Email Template")
		self.assertTrue(issubclass(controller, EmailTemplate))
		self.assertTrue(issubclass(controller, EmailTemplateListMixin))
		self.assertIs(controller.validate, EmailTemplate.validate)
		template = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": "Local " + uuid4().hex,
				"subject": "Hello {{ name }}",
				"response": "<p>{{ name }}</p>",
			}
		).insert()
		self.assertEqual(
			template.get_formatted_email({"name": "Fixture"}),
			{
				"subject": "Hello Fixture",
				"message": "<p>Fixture</p>",
			},
		)
		self.assertEqual(CustomEmailTemplate.default_list_data(), controller.default_list_data())
		template.subject = "{% if %}"
		with self.assertRaises(frappe.ValidationError):
			template.save()

	def test_another_extension_composes_with_crm_and_native_controller(self):
		original = frappe.get_hooks
		extensions = original("extend_doctype_class", {})

		def hooks(key=None, *args, **kwargs):
			if key == "extend_doctype_class":
				return {
					**extensions,
					"Contact": [
						*extensions["Contact"],
						"crm.tests.test_notification_controller_extensions.OtherListExtension",
					],
				}
			return original(key, *args, **kwargs)

		with patch("frappe.get_hooks", side_effect=hooks):
			controller = get_controller("Contact")
			self.assertTrue(controller.default_list_data()["other_extension"])
			self.assertTrue(issubclass(controller, ContactListMixin))
			self.assertIs(controller.validate, Contact.validate)
