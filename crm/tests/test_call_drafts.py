"""Native local draft isolation, revisions, canonical links and revocation."""

import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from uuid import uuid4

import frappe

from crm.api import call_drafts, call_work
from crm.integrations.exolve import api
from crm.integrations.exolve.utils import log_name


class TestCallDrafts(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = "DraftQA" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		self.other = "other-" + self.user
		for email in [self.user, self.other]:
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
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
				"first_name": self.tag + " Private",
				"status": "New",
				"lead_owner": self.other,
			}
		).insert()
		frappe.set_user(self.user)
		self.data = {
			"id": str(uuid4()),
			"number": "79990000111",
			"created": datetime.now(timezone.utc).isoformat(),
			"started": True,
			"ended": True,
			"incoming": False,
			"context": {"kind": "lead", "name": self.lead.name},
			"note": {
				"key": str(uuid4()),
				"kind": "note",
				"values": {"title": "Conversation", "text": "Personal unsaved text"},
				"name": None,
				"modified": None,
				"snapshot": "{}",
				"pending": None,
				"backup": None,
			},
			"tasks": [],
		}

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.set_user("Administrator")

	def save(self, revision=0, mutation=None):
		return call_drafts.save_draft(self.data, revision, mutation or str(uuid4()), self.user)

	def call(self, peer="79990000111", user=None):
		now = datetime.now(timezone.utc)
		values = {
			"id": log_name("draft-test", self.tag + uuid4().hex),
			"exolve_application_id": "draft-test",
			"exolve_call_id": self.tag + peer,
			"telephony_medium": "Exolve",
			"type": "Outgoing",
			"from": "79990000999",
			"to": peer,
			"status": "Completed",
			"duration": 20,
			"start_time": now - timedelta(seconds=25),
			"end_time": now,
			"recording_url": "",
			"exolve_recording_state": "unavailable",
		}
		if user:
			frappe.set_user(user)
		name = api._save_call(values)["name"]
		frappe.set_user(self.user)
		return name

	def test_draft_does_not_create_customer_note_or_task(self):
		before = (frappe.db.count("FCRM Note"), frappe.db.count("CRM Task"))
		self.save()
		row = call_drafts.get_draft(self.data["id"])["draft"]
		self.assertEqual(row["snapshot"]["note"]["values"]["text"], "Personal unsaved text")
		self.assertEqual(before, (frappe.db.count("FCRM Note"), frappe.db.count("CRM Task")))

	def test_private_drafts_cannot_be_read_by_another_user_or_native_crud(self):
		self.save()
		name = call_drafts._id(self.data["id"])
		self.assertFalse(frappe.has_permission("CRM Call Work", "read"))
		frappe.set_user(self.other)
		self.assertEqual(call_drafts.list_drafts()["drafts"], [])
		with self.assertRaises(frappe.DoesNotExistError):
			call_drafts.get_draft(self.data["id"])
		self.assertFalse(frappe.has_permission("CRM Call Work", "read", name))

	def test_revision_compare_and_exact_request_replay(self):
		mutation = str(uuid4())
		first = self.save(mutation=mutation)
		replay = self.save(mutation=mutation)
		self.assertEqual(first["revision"], replay["revision"])
		self.assertTrue(replay["replayed"])
		self.data["note"]["values"]["text"] = "Second tab"
		with self.assertRaises(frappe.ValidationError):
			self.save(mutation=mutation)
		with self.assertRaises(frappe.TimestampMismatchError):
			self.save(0)
		self.save(1)
		self.assertEqual(call_drafts.get_draft(self.data["id"])["draft"]["revision"], 2)

	def test_account_mismatch_and_invalid_payload_rejected(self):
		with self.assertRaises(frappe.PermissionError):
			call_drafts.save_draft(self.data, 0, str(uuid4()), self.other)
		self.data["note"]["values"]["text"] = "x" * 100001
		with self.assertRaises(frappe.ValidationError):
			self.save()

	def test_revoked_customer_access_hides_old_draft_content(self):
		self.save()
		frappe.set_user("Administrator")
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
		with self.assertRaises(frappe.PermissionError):
			call_drafts.get_draft(self.data["id"])
		self.assertEqual(call_drafts.list_drafts()["drafts"], [])

	def test_foreign_native_item_cannot_be_embedded_in_draft(self):
		row = call_work.save_note(
			{"title": "Note", "text": "saved", "context_kind": "lead", "context_name": self.lead.name},
			str(uuid4()),
			self.user,
		)["note"]
		self.data["note"].update({"name": row["name"], "modified": row["modified"]})
		self.data["context"] = {"kind": "lead", "name": self.hidden.name}
		with self.assertRaises(frappe.PermissionError):
			self.save()

	def test_explicit_link_uses_existing_canonical_note_and_task_ids(self):
		note = call_work.save_note(
			{"title": "Note", "text": "saved", "context_kind": "lead", "context_name": self.lead.name},
			str(uuid4()),
			self.user,
		)["note"]
		self.data["note"].update({"name": note["name"], "modified": note["modified"]})
		self.save()
		name = self.call()
		before = frappe.db.count("FCRM Note")
		result = call_drafts.link_call(self.data["id"], name, 1, self.user)
		self.assertEqual(result["draft"]["call_log"], name)
		call_drafts.link_call(self.data["id"], name, 1, self.user)
		doc = frappe.get_doc("CRM Call Log", name)
		self.assertEqual(
			len([r for r in doc.links if r.link_doctype == "FCRM Note" and r.link_name == note["name"]]), 1
		)
		self.assertEqual(frappe.db.count("FCRM Note"), before)
		task = call_work.save_task(
			{
				"title": "Task",
				"description": "Work",
				"assigned_to": self.user,
				"priority": "Medium",
				"status": "Todo",
				"due_date": "",
				"context_kind": "lead",
				"context_name": self.lead.name,
			},
			str(uuid4()),
			self.user,
		)["task"]
		self.data["tasks"] = [
			{
				"key": str(uuid4()),
				"kind": "task",
				"values": {
					"title": "Task",
					"description": "Work",
					"assigned_to": self.user,
					"priority": "Medium",
					"status": "Todo",
					"due_date": "",
				},
				"name": task["name"],
				"modified": task["modified"],
				"snapshot": "{}",
				"pending": None,
				"backup": None,
			}
		]
		self.save(1)
		doc.reload()
		self.assertTrue(doc.has_link("CRM Task", task["name"]))

	def test_link_requires_same_number_participant_and_one_conversation(self):
		self.save()
		wrong = self.call(peer="79990000222")
		with self.assertRaises(frappe.ValidationError):
			call_drafts.link_call(self.data["id"], wrong, 1, self.user)
		foreign = self.call(user=self.other)
		with self.assertRaises(frappe.PermissionError):
			call_drafts.link_call(self.data["id"], foreign, 1, self.user)
		name = self.call()
		call_drafts.link_call(self.data["id"], name, 1, self.user)
		self.data["id"] = str(uuid4())
		self.save()
		with self.assertRaises(frappe.ValidationError):
			call_drafts.link_call(self.data["id"], name, 1, self.user)

	def test_background_refresh_preserves_historical_employee_and_permissions(self):
		name = self.call()
		doc = frappe.get_doc("CRM Call Log", name)
		before = (doc.caller, doc.receiver, doc.owner, doc.get("from"), doc.start_time, doc.end_time)
		from zoneinfo import ZoneInfo

		values = {
			key: doc.get(key)
			for key in [
				"id",
				"exolve_application_id",
				"exolve_call_id",
				"type",
				"telephony_medium",
				"status",
				"duration",
				"from",
				"to",
				"recording_url",
			]
		}
		for key in ["start_time", "end_time"]:
			values[key] = (
				doc.get(key)
				.replace(tzinfo=ZoneInfo(frappe.utils.get_system_timezone()))
				.astimezone(timezone.utc)
			)
		values["exolve_recording_state"] = "pending"
		values["start_time"] += timedelta(hours=3)
		values["end_time"] += timedelta(hours=3)
		frappe.set_user(self.other)
		with self.assertRaises(frappe.PermissionError):
			api._save_call(values)
		api._save_call(values, preserve_participant=True)
		doc.reload()
		self.assertEqual(
			before, (doc.caller, doc.receiver, doc.owner, doc.get("from"), doc.start_time, doc.end_time)
		)

	def test_context_cannot_move_after_canonical_save(self):
		note = call_work.save_note(
			{"title": "Note", "text": "saved", "context_kind": "lead", "context_name": self.lead.name},
			str(uuid4()),
			self.user,
		)["note"]
		self.data["note"].update({"name": note["name"], "modified": note["modified"]})
		self.save()
		self.data["context"] = None
		self.data["note"].update({"name": None, "modified": None})
		with self.assertRaises(frappe.PermissionError):
			self.save(1)
