"""Native callback lifecycle, permissions, pagination and retry safety."""

from datetime import timedelta
from unittest import TestCase
from uuid import uuid4

import frappe
from frappe.utils import add_days, now_datetime, today

from crm.api import call_followups as api
from crm.api import call_work, telephony


class TestCallFollowups(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = "FollowupQA" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		self.other = "other-" + self.user
		for user in (self.user, self.other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": self.tag,
					"user_type": "System User",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			).insert()
		self.lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": self.tag, "status": "New", "lead_owner": self.user}
		).insert()
		self.hidden = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": self.tag + " hidden",
				"status": "New",
				"lead_owner": self.other,
			}
		).insert()
		self.flag = frappe.flags.in_exolve_sync
		frappe.flags.in_exolve_sync = True
		self.call = self.make_call()
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.flags.in_exolve_sync = self.flag
		frappe.set_user("Administrator")

	def make_call(self, lead=None, status="No Answer", direction="Incoming", days=0):
		lead = lead or self.lead
		return frappe.get_doc(
			{
				"doctype": "CRM Call Log",
				"telephony_medium": "Manual",
				"type": direction,
				"status": status,
				"from": "79990000001",
				"to": "79990000002",
				"caller": self.user,
				"receiver": self.user,
				"reference_doctype": "CRM Lead",
				"reference_docname": lead.name,
				"start_time": now_datetime() - timedelta(days=days),
				"duration": 0,
			}
		).insert()

	def save(self, outcome="Agreed", revision=0, mutation=None, callback=None, name=None):
		return api.save_outcome(
			name or self.call.name, outcome, revision, mutation or str(uuid4()), self.user, callback
		)

	def callback(self, days=0, **kwargs):
		return {
			"context_kind": "lead",
			"context_name": self.lead.name,
			"title": "Call customer back",
			"assigned_to": self.user,
			"due_date": add_days(today(), days) + " 12:00:00",
			**kwargs,
		}

	def attention(self):
		return [
			r["name"] for r in telephony.get_calls(search=self.tag, view="attention", period="today")["calls"]
		]

	def test_outcome_is_separate_from_provider_status_and_missed_history(self):
		self.assertIn(self.call.name, self.attention())
		before = frappe.db.count("CRM Task")
		self.save("Wrong number")
		self.assertNotIn(self.call.name, self.attention())
		self.assertEqual(frappe.db.get_value("CRM Call Log", self.call.name, "status"), "No Answer")
		self.assertIn(
			self.call.name, [r["name"] for r in telephony.get_calls(search=self.tag, view="missed")["calls"]]
		)
		self.assertEqual(frappe.db.count("CRM Task"), before)

	def test_atomic_callback_exact_retry_creates_one_native_task(self):
		mutation = str(uuid4())
		first = self.save("Callback", mutation=mutation, callback=self.callback())
		replay = self.save("Callback", mutation=mutation, callback=self.callback())
		self.assertTrue(replay["replayed"])
		task = first["review"]["callback_task"]
		self.assertEqual(task, replay["review"]["callback_task"])
		self.assertEqual(frappe.db.count("CRM Task", {"reference_docname": self.lead.name}), 1)
		native = frappe.get_doc("CRM Task", task)
		self.assertEqual(native.assigned_to, self.user)
		self.assertEqual(native.reference_docname, self.lead.name)
		self.assertTrue(frappe.get_doc("CRM Call Log", self.call.name).has_link("CRM Task", task))
		self.assertIn(self.call.name, self.attention())
		with self.assertRaises(frappe.ValidationError):
			self.save("Agreed", revision=1)

	def test_completion_uses_native_task_and_removes_attention_only(self):
		result = self.save("Callback", callback=self.callback())
		task = result["tasks"][0]
		mutation = str(uuid4())
		api.complete_task(self.call.name, task["name"], task["modified"], mutation, self.user)
		api.complete_task(self.call.name, task["name"], task["modified"], mutation, self.user)
		self.assertEqual(frappe.db.get_value("CRM Task", task["name"], "status"), "Done")
		self.assertNotIn(self.call.name, self.attention())
		self.assertTrue(frappe.db.exists("CRM Call Log", self.call.name))

	def test_future_callback_is_not_due_and_old_calls_remain_actionable(self):
		old = self.make_call(days=60)
		self.save("Callback", callback=self.callback(1), name=old.name)
		self.assertNotIn(old.name, self.attention())
		older = self.make_call(days=90)
		self.save("Callback", callback=self.callback(-1), name=older.name)
		self.assertIn(older.name, self.attention())
		row = next(
			r
			for r in telephony.get_calls(search=self.tag, view="attention")["calls"]
			if r["name"] == older.name
		)
		self.assertEqual(row["overdue_tasks"], 1)

	def test_invalid_assignee_and_context_create_nothing(self):
		before = frappe.db.count("CRM Task")
		with self.assertRaises(frappe.PermissionError):
			self.save("Callback", callback=self.callback(assigned_to=self.other))
		self.assertFalse(frappe.db.exists(api.DOCTYPE, self.call.name))
		with self.assertRaises(frappe.PermissionError):
			self.save("Callback", callback=self.callback(context_name=self.hidden.name))
		self.assertEqual(frappe.db.count("CRM Task"), before)

	def test_revision_conflict_and_changed_retry_cannot_overwrite(self):
		mutation = str(uuid4())
		self.save("Agreed", mutation=mutation)
		with self.assertRaises(frappe.TimestampMismatchError):
			self.save("Wrong number")
		with self.assertRaises(frappe.ValidationError):
			self.save("Wrong number", mutation=mutation)
		self.assertEqual(api.get_workspace(self.call.name)["review"]["outcome"], "Agreed")

	def test_foreign_call_task_and_user_are_denied(self):
		foreign = self.make_call(self.hidden)
		with self.assertRaises(frappe.PermissionError):
			api.get_workspace(foreign.name)
		with self.assertRaises(frappe.PermissionError):
			api.save_outcome(self.call.name, "Agreed", 0, str(uuid4()), self.other)
		result = self.save("Callback", callback=self.callback())
		other_call = self.make_call()
		with self.assertRaises(frappe.PermissionError):
			api.complete_task(
				other_call.name,
				result["tasks"][0]["name"],
				result["tasks"][0]["modified"],
				str(uuid4()),
				self.user,
			)
		self.assertFalse(frappe.has_permission(api.DOCTYPE, "read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": api.DOCTYPE, "name": "fake", "call_log": self.call.name}).insert(
				ignore_permissions=True
			)

	def test_filters_and_permission_filtering_before_pagination(self):
		self.save("Not interested")
		self.make_call(self.hidden)
		self.assertEqual(
			[
				r["name"]
				for r in telephony.get_calls(search=self.tag, outcome="Not interested", page_length=1)[
					"calls"
				]
			],
			[self.call.name],
		)
		self.assertEqual(telephony.get_calls(search=self.tag, line="unknown")["calls"], [])
		self.assertEqual(telephony.get_calls(search=self.tag, employee=self.other)["calls"], [])
		page = telephony.get_calls(search=self.tag, view="attention", page_length=1)
		self.assertEqual(page["calls"], [])
		self.assertFalse(page["has_more"])

	def test_canonical_materials_are_permission_checked_and_private_drafts_excluded(self):
		note = call_work.save_note(
			{
				"title": "Saved note",
				"text": "Actual canonical text",
				"context_kind": "lead",
				"context_name": self.lead.name,
			},
			str(uuid4()),
			self.user,
		)["note"]
		doc = frappe.get_doc("CRM Call Log", self.call.name)
		doc.link_with_reference_doc("FCRM Note", note["name"])
		doc.save()
		result = api.get_workspace(self.call.name)
		self.assertEqual([n["text"] for n in result["notes"]], ["Actual canonical text"])
		self.assertNotIn("draft", result)

	def test_cancel_preserves_callback_history_and_allows_explicit_new_task(self):
		first = self.save("Callback", callback=self.callback())
		task = first["tasks"][0]
		api.complete_task(self.call.name, task["name"], task["modified"], str(uuid4()), self.user, "Canceled")
		second = self.save("Callback", revision=1, callback=self.callback(1))
		self.assertNotEqual(first["review"]["callback_task"], second["review"]["callback_task"])
		self.assertEqual(len(second["tasks"]), 2)

	def test_callback_operation_identity_is_bound_to_its_call(self):
		mutation = str(uuid4())
		other = self.make_call()
		one = self.save("Callback", mutation=mutation, callback=self.callback())
		two = self.save("Callback", mutation=mutation, callback=self.callback(), name=other.name)
		self.assertNotEqual(one["review"]["callback_task"], two["review"]["callback_task"])

	def test_material_customer_is_offered_without_retargeting_primary_call(self):
		customer = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": self.tag + " material customer",
				"status": "New",
				"lead_owner": self.user,
			}
		).insert()
		note = call_work.save_note(
			{
				"title": "Explicit note",
				"text": "Different chosen customer",
				"context_kind": "lead",
				"context_name": customer.name,
			},
			str(uuid4()),
			self.user,
		)["note"]
		doc = frappe.get_doc("CRM Call Log", self.call.name)
		doc.link_with_reference_doc("FCRM Note", note["name"])
		doc.save()
		workspace = api.get_workspace(self.call.name)
		self.assertEqual({r["name"] for r in workspace["references"]}, {self.lead.name, customer.name})
		self.assertEqual(
			frappe.db.get_value("CRM Call Log", self.call.name, "reference_docname"), self.lead.name
		)

	def test_hidden_customer_lines_and_outcomes_are_not_in_filter_options(self):
		private = self.make_call(self.hidden)
		frappe.db.set_value("CRM Call Log", private.name, "to", "79990000999")
		directory = telephony.get_filter_options()
		self.assertNotIn("79990000999", directory["lines"])
		with self.assertRaises(frappe.PermissionError):
			self.save("Agreed", name=private.name)

	def test_attention_employee_filter_uses_callback_assignee(self):
		frappe.set_user("Administrator")
		frappe.share.add("CRM Lead", self.lead.name, self.other, read=1)
		frappe.set_user(self.user)
		self.save("Callback", callback=self.callback(assigned_to=self.other))
		mine = telephony.get_calls(search=self.tag, view="attention", employee=self.user)["calls"]
		other = telephony.get_calls(search=self.tag, view="attention", employee=self.other)["calls"]
		self.assertNotIn(self.call.name, [r["name"] for r in mine])
		self.assertIn(self.call.name, [r["name"] for r in other])

	def test_revoked_callback_customer_hides_review_and_materials_on_still_visible_call(self):
		result = self.save("Callback", callback=self.callback())
		frappe.set_user("Administrator")
		frappe.db.set_value(
			"CRM Call Log", self.call.name, {"reference_doctype": "", "reference_docname": ""}
		)
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", self.other)
		frappe.db.set_value(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
			"status",
			"Cancelled",
		)
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.clear_cache(user=self.user)
		frappe.set_user(self.user)
		workspace = api.get_workspace(self.call.name)
		self.assertIsNone(workspace["review"])
		self.assertFalse(workspace["can_manage"])
		self.assertEqual(workspace["tasks"], [])
		self.assertNotIn(result["review"]["callback_task"], frappe.as_json(workspace))
		with self.assertRaises(frappe.PermissionError):
			self.save("Wrong number", revision=1)
