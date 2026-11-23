from uuid import uuid4

import frappe
from frappe.model.db_query import DatabaseQuery as LegacyQuery
from frappe.tests import IntegrationTestCase

from crm.api import celio_tasks


class TestCelioTasks(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("crm_celio_tasks")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="crm_celio_tasks")

	def test_native_assignment_revision_and_retry(self):
		key = uuid4().hex
		values = {"title": "Adapter task", "assigned_to": "Administrator", "due_date": "2027-03-15"}
		first = celio_tasks.save_task(values, key, expected_viewer="Administrator")
		task = first["task"]
		name = task["name"]
		self.assertFalse(first["replayed"])
		self.assertEqual(task["assignees"], ["Administrator"])
		self.assertTrue(celio_tasks.get_task(name)["task"]["can_write"])
		self.assertIn(name, {row["name"] for row in celio_tasks.my_work()})
		replay = celio_tasks.save_task(values, key, expected_viewer="Administrator")
		self.assertTrue(replay["replayed"])
		self.assertEqual(replay["task"]["name"], name)
		with self.assertRaises(frappe.ValidationError):
			celio_tasks.save_task({"title": "Different payload"}, key, expected_viewer="Administrator")
		with self.assertRaises(frappe.PermissionError):
			celio_tasks.save_task(values, key, expected_viewer="Guest")
		newer = celio_tasks.save_task(
			{"assigned_to": "", "status": "Done"}, uuid4().hex, name, task["modified"], "Administrator"
		)
		self.assertEqual(newer["task"]["state_group"], "completed")
		self.assertFalse(frappe.get_doc("CRM Task", name).get_assigned_users())
		with self.assertRaises(frappe.TimestampMismatchError):
			celio_tasks.save_task({"status": "Todo"}, uuid4().hex, name, task["modified"], "Administrator")
		frappe.delete_doc("CRM Task", name)
		with self.assertRaises(frappe.PermissionError):
			celio_tasks.save_task(values, key, expected_viewer="Administrator")

	def test_parent_permissions_in_list_document_and_adapter(self):
		rep = (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"celio-{uuid4().hex}@example.test",
					"first_name": "Sales",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			)
			.insert()
			.name
		)
		names = []
		for owner in (rep, "Administrator"):
			lead = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Customer", "lead_owner": owner})
			lead.flags.ignore_mandatory = True
			lead.insert()
			result = celio_tasks.save_task(
				{"title": "Follow up", "context_kind": "lead", "context_name": lead.name},
				uuid4().hex,
				expected_viewer="Administrator",
			)
			names.append(result["task"]["name"])
		allowed, hidden = names
		frappe.set_user(rep)
		filters = {"name": ["in", names]}
		self.assertEqual(
			{str(name) for name in frappe.get_list("CRM Task", filters=filters, pluck="name")}, {allowed}
		)
		legacy = LegacyQuery("CRM Task").execute(fields=["name"], filters=filters)
		self.assertEqual({str(row.name) for row in legacy}, {allowed})
		self.assertEqual(celio_tasks.get_task(allowed)["task"]["name"], allowed)
		self.assertFalse(frappe.has_permission("CRM Task", "read", hidden))
		with self.assertRaises(frappe.PermissionError):
			celio_tasks.get_task(hidden)
		with self.assertRaises(frappe.PermissionError):
			celio_tasks.save_task({"title": "Unavailable"}, uuid4().hex, hidden, None, rep)
		self.assertFalse(frappe.has_permission("CRM Task Operation", "read"))
