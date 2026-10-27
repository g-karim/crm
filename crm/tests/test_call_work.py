"""Native local in-call work without provider traffic or committed fixtures."""
from unittest import TestCase
from uuid import uuid4

import frappe

from crm.api import call_work


class TestCallWork(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = "CallWork" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		self.other = "other-" + self.user
		for email in (self.user, self.other):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": self.tag,
				"user_type": "System User", "send_welcome_email": 0,
				"roles": [{"role": "Sales User"}]}).insert()
		self.lead = frappe.get_doc({"doctype": "CRM Lead", "first_name": self.tag,
			"status": "New", "lead_owner": self.user, "mobile_no": "+70000000101"}).insert()
		self.hidden = frappe.get_doc({"doctype": "CRM Lead", "first_name": self.tag + " Private",
			"status": "New", "lead_owner": "Administrator"}).insert()
		self.deal = frappe.get_doc({"doctype": "CRM Deal", "deal_name": self.tag + " Deal",
			"currency": frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
			"status": frappe.db.get_value("CRM Deal Status", {"type": "Open"}, "name"),
			"deal_owner": self.user}).insert(ignore_mandatory=True)
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.set_user("Administrator")

	def note(self, **kwargs):
		values = {"title": self.tag + " Note", "text": "First line\nSecond line", "context_kind": "lead", "context_name": self.lead.name}
		values.update(kwargs.pop("values", {}))
		return call_work.save_note(values, kwargs.pop("mutation_id", str(uuid4())), self.user, **kwargs)

	def task(self, **kwargs):
		values = {"title": self.tag + " Task", "description": "Follow up", "assigned_to": self.user,
			"priority": "High", "status": "Todo", "due_date": "2026-12-01 12:30:00",
			"context_kind": "lead", "context_name": self.lead.name}
		values.update(kwargs.pop("values", {}))
		return call_work.save_task(values, kwargs.pop("mutation_id", str(uuid4())), self.user, **kwargs)

	def test_note_saves_directly_to_lead_before_call_log_exists(self):
		before = frappe.db.count("CRM Call Log")
		row = self.note()["note"]
		doc = frappe.get_doc("FCRM Note", row["name"])
		self.assertEqual((doc.reference_doctype, doc.reference_docname), ("CRM Lead", self.lead.name))
		self.assertEqual(row["text"], "First line\nSecond line")
		self.assertEqual(frappe.db.count("CRM Call Log"), before)
		from crm.api.activities import get_linked_notes
		self.assertIn(doc.name, [item.name for item in get_linked_notes(self.lead.name)])

	def test_note_retry_replays_same_record_and_rejects_changed_payload(self):
		operation = str(uuid4())
		first = self.note(mutation_id=operation)
		second = self.note(mutation_id=operation)
		self.assertTrue(second["replayed"])
		self.assertEqual(first["note"]["name"], second["note"]["name"])
		with self.assertRaises(frappe.ValidationError): self.note(mutation_id=operation, values={"text": "Different"})

	def test_note_update_requires_revision_and_cannot_move_context(self):
		first = self.note()["note"]
		updated = self.note(name=first["name"], expected_modified=first["modified"], values={"text": "Updated"})["note"]
		self.assertEqual(updated["name"], first["name"])
		with self.assertRaises(frappe.TimestampMismatchError):
			self.note(name=first["name"], expected_modified=first["modified"])
		with self.assertRaises(frappe.ValidationError):
			self.note(name=first["name"], expected_modified=updated["modified"], values={"context_kind":"deal", "context_name":self.deal.name})

	def test_note_text_is_escaped(self):
		text = '<script>alert("x")</script> & <img src=x onerror=alert(1)>\n\nNext paragraph'
		row = self.note(values={"text":text})["note"]
		content = frappe.db.get_value("FCRM Note", row["name"], "content")
		self.assertNotIn("<script>", content)
		self.assertIn("&lt;script&gt;", content)
		self.assertEqual(row["text"], text)

	def test_task_description_round_trips_blank_lines(self):
		row = self.task(values={"description":"First paragraph\n\nSecond paragraph"})["task"]
		self.assertEqual(row["description_text"], "First paragraph\n\nSecond paragraph")

	def test_tasks_use_native_assignment_and_distinct_records(self):
		operation = str(uuid4())
		first = self.task(mutation_id=operation)
		second = self.task(mutation_id=operation)
		third = self.task(values={"title":self.tag + " Next task"})
		self.assertEqual(first["task"]["name"], second["task"]["name"])
		self.assertNotEqual(first["task"]["name"], third["task"]["name"])
		doc = frappe.get_doc("CRM Task", first["task"]["name"])
		self.assertEqual((doc.reference_doctype, doc.reference_docname), ("CRM Lead", self.lead.name))
		self.assertEqual(frappe.db.count("ToDo", {"reference_type":"CRM Task", "reference_name":doc.name, "allocated_to":self.user, "status":"Open"}), 1)
		self.assertTrue(second["replayed"])

	def test_deal_note_and_task_are_visible_in_native_context(self):
		values = {"context_kind":"deal", "context_name":self.deal.name}
		note = self.note(values=values)["note"]
		task = self.task(values=values)["task"]
		self.assertEqual(note["reference_doctype"], "CRM Deal")
		self.assertEqual(task["context"]["name"], self.deal.name)
		from crm.api.activities import get_linked_tasks
		self.assertIn(task["name"], [str(item.name) for item in get_linked_tasks(self.deal.name)])

	def test_closed_context_and_wrong_viewer_cannot_save(self):
		with self.assertRaises(frappe.PermissionError): self.note(values={"context_name":self.hidden.name})
		with self.assertRaises(frappe.PermissionError): self.task(values={"context_name":self.hidden.name})
		with self.assertRaises(frappe.PermissionError):
			call_work.save_note({}, str(uuid4()), "Administrator")
		with self.assertRaises(frappe.ValidationError): self.note(values={"context_name":""})

	def test_assignee_needs_access_to_selected_customer(self):
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead.name, user=self.other))
		with self.assertRaises(frappe.PermissionError): self.task(values={"assigned_to":self.other})

	def test_context_search_and_explicit_resolution_apply_permissions(self):
		rows = call_work.search_contexts(query=self.tag)
		self.assertIn(self.lead.name, [item["name"] for item in rows])
		self.assertNotIn(self.hidden.name, [item["name"] for item in rows])
		rows = call_work.resolve_context([{"doctype":"CRM Lead", "name":self.lead.name}, {"doctype":"CRM Deal", "name":self.deal.name}])
		self.assertEqual(len(rows["contexts"]), 2)
		with self.assertRaises(frappe.PermissionError): call_work.resolve_context({"doctype":"CRM Lead", "name":self.hidden.name})
		self.assertEqual(call_work.resolve_context()["contexts"], [])

	def test_revocation_blocks_note_edit_read_and_replay(self):
		operation = str(uuid4()); row = self.note(mutation_id=operation)["note"]
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator", update_modified=False)
		frappe.db.set_value("ToDo", {"reference_type":"CRM Lead", "reference_name":self.lead.name, "allocated_to":self.user}, "status", "Cancelled", update_modified=False)
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError): self.note(mutation_id=operation)
		with self.assertRaises(frappe.PermissionError): self.note(name=row["name"], expected_modified=row["modified"])
		with self.assertRaises(frappe.PermissionError): call_work.get_item("note", row["name"], "lead", self.lead.name)

	def test_private_note_receipts_have_no_client_crud(self):
		note = self.note()["note"]["name"]
		self.assertFalse(frappe.has_permission("CRM Note Operation", "read"))
		self.assertFalse(frappe.has_permission("CRM Note Operation", "create"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype":"CRM Note Operation", "name":uuid4().hex, "user":self.user, "request_hash":"fake", "note":note}).insert(ignore_permissions=True)

	def test_guest_cannot_use_call_work(self):
		frappe.set_user("Guest")
		for action in (lambda:call_work.resolve_context(), lambda:call_work.search_contexts(), lambda:call_work.options("lead", self.lead.name), lambda:self.note(), lambda:self.task()):
			with self.assertRaises(frappe.PermissionError): action()

	def test_null_viewer_is_not_an_account_check_bypass(self):
		with self.assertRaises(frappe.PermissionError):
			call_work.save_note({}, str(uuid4()), None)

	def test_native_crud_and_lists_hide_managed_work_in_a_closed_context(self):
		note = self.note()["note"]; task = self.task()["task"]
		frappe.set_user(self.other)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead.name))
		from frappe.client import get
		for doctype, name in (("FCRM Note", note["name"]), ("CRM Task", task["name"])):
			self.assertFalse(frappe.has_permission(doctype, "read", frappe.get_doc(doctype, name)))
			self.assertEqual(frappe.get_list(doctype, filters={"name":name}, fields=["name"]), [])
			with self.assertRaises(frappe.PermissionError): get(doctype, name)

	def test_legacy_unlinked_work_keeps_native_access(self):
		note = frappe.get_doc({"doctype":"FCRM Note", "title":self.tag, "content":"Legacy"}).insert()
		task = frappe.get_doc({"doctype":"CRM Task", "title":self.tag, "status":"Todo", "priority":"Medium"}).insert()
		frappe.set_user(self.other)
		for doctype, name in (("FCRM Note", note.name), ("CRM Task", task.name)):
			self.assertTrue(frappe.has_permission(doctype, "read", frappe.get_doc(doctype, name)))
			self.assertEqual(len(frappe.get_list(doctype, filters={"name":name}, fields=["name"])), 1)

	def test_native_work_access_follows_customer_revocation_despite_assignment(self):
		note = self.note()["note"]; task = self.task()["task"]
		rows = (("FCRM Note", note["name"]), ("CRM Task", task["name"]))
		for doctype, name in rows:
			self.assertTrue(frappe.has_permission(doctype, "read", name))
			self.assertEqual(len(frappe.get_list(doctype, filters={"name":name})), 1)
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator", update_modified=False)
		frappe.db.set_value("ToDo", {"reference_type":"CRM Lead", "reference_name":self.lead.name,
			"allocated_to":self.user}, "status", "Cancelled", update_modified=False)
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.set_user(self.user)
		self.assertTrue(frappe.db.exists("ToDo", {"reference_type":"CRM Task", "reference_name":task["name"],
			"allocated_to":self.user, "status":"Open"}))
		for doctype, name in rows:
			self.assertFalse(frappe.has_permission(doctype, "read", name))
			self.assertEqual(frappe.get_list(doctype, filters={"name":name}), [])

	def test_work_cannot_edit_another_authors_note(self):
		row = self.note()["note"]
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			call_work.get_item("note", row["name"], "lead", self.lead.name)

	def test_task_update_checks_revision_and_context(self):
		row = self.task()["task"]
		changed = self.task(name=row["name"], expected_modified=row["modified"], values={"status":"Done"})["task"]
		self.assertEqual(changed["name"], row["name"])
		self.assertEqual(changed["status"], "Done")
		with self.assertRaises(frappe.TimestampMismatchError):
			self.task(name=row["name"], expected_modified=row["modified"])
		with self.assertRaises(frappe.PermissionError):
			self.task(name=row["name"], expected_modified=changed["modified"], values={"context_kind":"deal", "context_name":self.deal.name})

	def test_contact_with_two_deals_returns_both_without_phone_guessing(self):
		frappe.set_user("Administrator")
		contact = frappe.get_doc({"doctype":"Contact", "first_name":self.tag + " Contact"}).insert()
		names = []
		for suffix in ("One", "Two"):
			doc = frappe.get_doc({"doctype":"CRM Deal", "deal_name":self.tag + suffix, "deal_owner":self.user,
				"currency":frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
				"status":frappe.db.get_value("CRM Deal Status", {"type":"Open"}, "name"),
				"contacts":[{"contact":contact.name, "is_primary":1}]}).insert(ignore_mandatory=True)
			names.append(doc.name)
		frappe.set_user(self.user)
		result = call_work.resolve_context({"doctype":"Contact", "name":contact.name})["contexts"]
		self.assertEqual({row["name"] for row in result}, set(names))
