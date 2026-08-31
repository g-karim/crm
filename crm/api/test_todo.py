# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import frappe.share
from frappe.desk.form.assign_to import _add, _remove, add, remove
from frappe.tests import IntegrationTestCase

from crm.api.todo import allow_internal_lead_assignment


class TestLeadAssignmentPermissions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for email in (
			"assignment-writer@example.com",
			"assignment-reader@example.com",
			"assignment-other@example.com",
		):
			make_sales_user(email)
		make_user("assignment-manager@example.com", "System Manager")

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("test_lead_assignment_permissions")
		self.lead = make_lead("assignment-writer@example.com")
		frappe.share.add(
			"CRM Lead",
			self.lead.name,
			"assignment-reader@example.com",
			read=1,
			write=0,
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="test_lead_assignment_permissions")

	def test_read_only_user_cannot_assign_self_or_another_user(self):
		frappe.set_user("assignment-reader@example.com")

		for assignee, ignore_permissions in (
			("assignment-reader@example.com", False),
			("assignment-other@example.com", True),
		):
			with self.assertRaises(frappe.PermissionError):
				assign = _add if ignore_permissions else add
				assign(
					{
						"doctype": "CRM Lead",
						"name": self.lead.name,
						"assign_to": [assignee],
					},
					**({"ignore_permissions": True} if ignore_permissions else {}),
				)

		self.assertFalse(
			frappe.db.exists(
				"ToDo",
				{
					"reference_type": "CRM Lead",
					"reference_name": self.lead.name,
					"allocated_to": "assignment-reader@example.com",
					"status": "Open",
				},
			)
		)

	def test_ignore_permissions_does_not_bypass_direct_todo_validation(self):
		frappe.set_user("assignment-reader@example.com")
		with self.assertRaises(frappe.PermissionError):
			make_todo(self.lead.name, "assignment-reader@example.com")

	def test_read_only_user_cannot_update_or_delete_existing_assignment(self):
		frappe.set_user("Administrator")
		deal = make_deal()
		todo = frappe.get_doc(
			"ToDo",
			frappe.db.get_value(
				"ToDo",
				{
					"reference_type": "CRM Lead",
					"reference_name": self.lead.name,
					"allocated_to": "assignment-writer@example.com",
					"status": "Open",
				},
			),
		)

		frappe.set_user("assignment-reader@example.com")
		with self.assertRaises(frappe.PermissionError):
			_remove(
				"CRM Lead",
				self.lead.name,
				"assignment-writer@example.com",
				ignore_permissions=True,
			)

		todo.status = "Cancelled"
		with self.assertRaises(frappe.PermissionError):
			todo.save(ignore_permissions=True)
		todo.reload()
		self.assertEqual(todo.status, "Open")

		with self.assertRaises(frappe.PermissionError):
			todo.delete(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("ToDo", todo.name))

		todo.reference_type = "CRM Deal"
		todo.reference_name = deal.name
		with self.assertRaises(frappe.PermissionError):
			todo.save(ignore_permissions=True)

	def test_existing_assignee_can_manage_assignments(self):
		frappe.set_user("Administrator")
		make_todo(self.lead.name, "assignment-reader@example.com")

		frappe.set_user("assignment-reader@example.com")
		self.assertTrue(frappe.has_permission("CRM Lead", "write", doc=self.lead))
		add(
			{
				"doctype": "CRM Lead",
				"name": self.lead.name,
				"assign_to": ["assignment-other@example.com"],
			}
		)
		self.assertTrue(
			frappe.db.exists(
				"ToDo",
				{
					"reference_type": "CRM Lead",
					"reference_name": self.lead.name,
					"allocated_to": "assignment-other@example.com",
					"status": "Open",
				},
			)
		)

		remove("CRM Lead", self.lead.name, "assignment-other@example.com")
		self.assertFalse(
			frappe.db.exists(
				"ToDo",
				{
					"reference_type": "CRM Lead",
					"reference_name": self.lead.name,
					"allocated_to": "assignment-other@example.com",
					"status": "Open",
				},
			)
		)

	def test_internal_owner_assignment_remains_available(self):
		frappe.set_user("assignment-reader@example.com")
		lead = make_lead("assignment-writer@example.com")
		self.assertTrue(
			frappe.db.exists(
				"ToDo",
				{
					"reference_type": "CRM Lead",
					"reference_name": lead.name,
					"allocated_to": "assignment-writer@example.com",
					"status": "Open",
				},
			)
		)

	def test_system_manager_can_create_assignment(self):
		frappe.set_user("assignment-manager@example.com")
		todo = make_todo(self.lead.name, "assignment-other@example.com")
		self.assertTrue(todo.name)

	def test_trusted_bypass_is_scoped(self):
		frappe.set_user("assignment-reader@example.com")
		with allow_internal_lead_assignment():
			make_todo(self.lead.name, "assignment-other@example.com")

		with self.assertRaises(frappe.PermissionError):
			make_todo(self.lead.name, "assignment-writer@example.com")


def make_sales_user(email):
	return make_user(email, "Sales User")


def make_user(email, role):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	if role not in frappe.get_roles(email):
		user.add_roles(role)
	return user


def make_lead(owner):
	lead = frappe.get_doc(
		{
			"doctype": "CRM Lead",
			"first_name": "Assignment Permission Test",
			"lead_owner": owner,
		}
	)
	lead.flags.ignore_mandatory = True
	return lead.insert(ignore_permissions=True)


def make_todo(lead_name, allocated_to):
	return frappe.get_doc(
		{
			"doctype": "ToDo",
			"reference_type": "CRM Lead",
			"reference_name": lead_name,
			"allocated_to": allocated_to,
			"status": "Open",
			"description": f"Assignment permission test for {allocated_to}",
		}
	).insert(ignore_permissions=True)


def make_deal():
	deal = frappe.get_doc(
		{
			"doctype": "CRM Deal",
			"organization": "Assignment Permission Test",
		}
	)
	deal.flags.ignore_mandatory = True
	deal.flags.ignore_links = True
	return deal.insert(ignore_permissions=True)
