import json
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime, now_datetime

from crm import touch_tracking as touch
from crm import touch_tracking_internal as internal
from crm.tests import test_touch_tracking as base_cases


class TestInternalTouchOrigins(unittest.TestCase):
	def test_shared_code_before_site_migration_does_not_observe_or_log_changes(self):
		card = SimpleNamespace(flags=frappe._dict(), meta=SimpleNamespace(has_field=lambda name: False))
		with (
			patch.object(frappe.db, "table_exists", return_value=False),
			patch.object(frappe, "get_cached_doc", side_effect=AssertionError("Unmigrated settings queried")),
			patch.object(internal, "_fail") as diagnose,
		):
			internal.remember_card_input(card)
			internal.capture_internal(SimpleNamespace(doctype="CRM Task"))
			self.assertIsNone(internal.current_policy("CRM Lead", now_datetime()))
			self.assertEqual(card.flags.touch_input_fields, [])
			diagnose.assert_not_called()

	def test_authenticated_requests_and_automation_are_distinguished(self):
		fake = SimpleNamespace(
			flags=SimpleNamespace(in_import=False, in_patch=False, in_migrate=False, in_safe_exec=False),
			local=SimpleNamespace(request=SimpleNamespace(headers={}), job=None),
			session=SimpleNamespace(user="Employee"),
		)
		with patch.object(internal, "frappe", fake):
			self.assertEqual(internal.operation_origin(), "User")
			fake.local.request.headers["Authorization"] = "token test"
			self.assertEqual(internal.operation_origin(), "Automation")
			fake.local.request.headers = {}
			fake.local.job = SimpleNamespace(method="import")
			self.assertEqual(internal.operation_origin(), "Automation")
			fake.local.job = None
			fake.flags.in_import = True
			self.assertEqual(internal.operation_origin(), "Automation")
			fake.flags.in_import = False
			fake.flags.in_safe_exec = True
			self.assertEqual(internal.operation_origin(), "Automation")
			fake.flags.in_safe_exec = False
			fake.local.request = None
			self.assertEqual(internal.operation_origin(), "Automation")

	def test_integer_task_source_identity_matches_its_persisted_text_name(self):
		args = ("CRM Lead", "LEAD-1", "Internal Changed", "CRM Task")
		self.assertEqual(touch.event_key(*args, 16, "revision-1"), touch.event_key(*args, "16", "revision-1"))
		self.assertNotEqual(
			touch.event_key(*args, 16, "revision-1"), touch.event_key(*args, 16, "revision-2")
		)


class TestInternalTouchTracking(unittest.TestCase):
	"""Business-path regression tests on a disposable MariaDB site."""

	create = base_cases.TestTouchTrackingDatabase.create
	events = base_cases.TestTouchTrackingDatabase.events
	change_status = base_cases.TestTouchTrackingDatabase.change_status
	tearDown = base_cases.TestTouchTrackingDatabase.tearDown

	def setUp(self):
		base_cases.TestTouchTrackingDatabase.setUp(self)
		mock = patch("crm.touch_tracking_internal.operation_origin", return_value="User")
		mock.start()
		self.addCleanup(mock.stop)

	def configure(self, doctype="CRM Lead", *, fields=(), events=(), automation=0):
		prefix = "lead" if doctype == "CRM Lead" else "deal"
		self.settings.set(f"{prefix}_fields", json.dumps(list(fields)))
		self.settings.set(f"{prefix}_events", json.dumps(list(events)))
		self.settings.set(f"{prefix}_allow_automation", automation)
		self.settings.save()

	def child(self, parent, doctype="CRM Task", **values):
		return frappe.get_doc(
			{
				"doctype": doctype,
				"title": "Stage 3 test",
				"reference_doctype": parent.doctype,
				"reference_docname": parent.name,
				**values,
			}
		).insert()

	def comment(self, parent, **values):
		return frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"content": "Stage 3 test",
				"reference_doctype": parent.doctype,
				"reference_name": parent.name,
				**values,
			}
		).insert()

	def flush(self):
		touch.maintenance()

	def reasons(self, event):
		return internal.selections(event.reasons)

	def test_additional_rules_start_disabled(self):
		for doctype in touch.TARGETS:
			parent = self.create(doctype)
			self.child(parent)
			self.child(parent, "FCRM Note")
			self.comment(parent)
			self.flush()
			self.assertEqual(len(self.events(parent)), 1)

	def test_editable_site_custom_field_is_supported(self):
		fieldname = "custom_touch_stage3_flag"
		if not frappe.get_meta("CRM Lead").has_field(fieldname):
			self.skipTest("Requires the disposable site's Stage 3 custom-field fixture")
		self.configure(fields=(fieldname,))
		parent = self.create()
		parent.set(fieldname, 1)
		parent.save()
		parent.set(fieldname, "1")
		parent.save()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.reasons(self.events(parent)[-1]), [f"field:{fieldname}"])

	def test_derived_values_are_not_counted_as_explicit_field_edits(self):
		self.configure("CRM Deal", fields=("probability",))
		parent = self.create("CRM Deal")
		original = parent.probability
		# Simulate native validation deriving a value from an unselected input.
		from crm.fcrm.doctype.crm_deal.crm_deal import CRMDeal

		validate = CRMDeal.validate

		def derive(doc):
			validate(doc)
			doc.probability = original + 1

		with patch.object(CRMDeal, "validate", derive):
			parent.next_step = "Changed"
			parent.save()
		self.assertEqual(len(self.events(parent)), 1)

	def test_cancelled_assignment_insert_with_no_net_owner_change_does_not_touch(self):
		self.configure(fields=("lead_owner",))
		parent = self.create()
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "Test cancelled assignment",
				"reference_type": parent.doctype,
				"reference_name": parent.name,
				"allocated_to": "Administrator",
				"status": "Cancelled",
			}
		).insert()
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		self.assertFalse(parent.reload().lead_owner)

	def test_source_journal_failure_preserves_business_save_and_is_diagnosed(self):
		from crm.fcrm.doctype.crm_touch_change.crm_touch_change import CRMTouchChange

		self.configure(events=("task_title",))
		parent = self.create()
		task = self.child(parent)
		with (
			patch.object(CRMTouchChange, "validate", side_effect=RuntimeError("source unavailable")),
			patch("crm.touch_tracking._diagnose") as diagnostic,
		):
			task.title = "Saved despite unavailable touch log"
			task.save()
			diagnostic.assert_called()
		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "title"), task.title)
		self.assertEqual(frappe.db.count(internal.CHANGE), 0)

	def test_selected_fields_group_with_status_and_do_not_recover_twice(self):
		for doctype in touch.TARGETS:
			second_field = "mobile_no" if doctype == "CRM Lead" else "next_step"
			self.configure(doctype, fields=("first_name", second_field))
			parent = self.create(doctype)
			parent.first_name = "Changed"
			parent.set(second_field, "+79000001234" if doctype == "CRM Lead" else "Follow up")
			self.change_status(parent)
			events = self.events(parent)
			self.assertEqual(len(events), 2)
			self.assertEqual(
				self.reasons(events[-1]), ["field:first_name", f"field:{second_field}", "status_changed"]
			)
			self.assertEqual(events[-1].event_type, "Status Changed")
			self.assertEqual(touch.recover_missing(), 0)
			parent.save()
			self.assertEqual(len(self.events(parent)), 2)

	def test_repeated_field_edits_and_equivalent_values(self):
		self.configure(fields=("first_name", "annual_revenue", "phone"))
		parent = self.create()
		parent.annual_revenue, parent.phone = "0.000", ""
		parent.save()
		self.assertEqual(len(self.events(parent)), 1)
		for value in ("First edit", "Second edit", "First edit"):
			parent.first_name = value
			parent.save()
		self.assertEqual(len(self.events(parent)), 4)
		self.assertEqual(len({e.source_revision for e in self.events(parent)[1:]}), 3)
		parent.run_method("on_update")  # repeated callback for the same revision
		self.assertEqual(len(self.events(parent)), 4)

	def test_settings_reject_technical_fields_and_unknown_rules(self):
		for name in (
			"modified",
			"status",
			"last_touch_at",
			"lead_name",
			"products",
			"facebook_lead_id",
			"missing_custom",
		):
			with self.subTest(name=name), self.assertRaises(frappe.ValidationError):
				self.configure(fields=(name,))
		self.settings.lead_fields = "[]"
		with self.assertRaises(frappe.ValidationError):
			self.configure(events=("email_sent",))

	def test_canonical_settings_noop_and_independent_types(self):
		self.configure(fields=("first_name", "mobile_no"), events=("task_due_date",))
		revision = self.settings.policy_revision
		self.settings.lead_fields = '["mobile_no", "first_name", "mobile_no"]'
		self.settings.save()
		self.assertEqual(self.settings.policy_revision, revision)
		for doctype in touch.TARGETS:
			parent = self.create(doctype)
			parent.first_name = "Changed"
			parent.save()
			self.assertEqual(len(self.events(parent)), 2 if doctype == "CRM Lead" else 1)

	def test_task_dates_use_action_time_and_card_list_api_paths_agree(self):
		from frappe.client import set_value

		for doctype in touch.TARGETS:
			self.configure(doctype, events=("task_due_date", "task_start_date"))
			parent = self.create(doctype)
			original_modified = get_datetime(parent.modified)
			task = self.child(parent)
			future = now_datetime() + timedelta(days=30)
			task.due_date = future
			task.save()  # document save, as used by a card
			self.assertEqual(
				frappe.db.get_value(parent.doctype, parent.name, touch.FIELD), get_datetime(parent.creation)
			)
			self.flush()
			self.assertEqual(get_datetime(self.events(parent)[-1].occurred_at), get_datetime(task.modified))
			self.assertLess(get_datetime(parent.reload().last_touch_at), future)
			set_value("CRM Task", task.name, "due_date", str(future))  # same API value: no-op
			self.flush()
			self.assertEqual(len(self.events(parent)), 2)
			set_value("CRM Task", task.name, {"due_date": None, "start_date": str(future.date())})
			self.flush()
			self.assertEqual(self.reasons(self.events(parent)[-1]), ["task_due_date", "task_start_date"])
			self.assertEqual(len(self.events(parent)), 3)
			self.assertEqual(get_datetime(parent.reload().modified), original_modified)

	def test_task_completion_other_statuses_and_reopening_are_separate(self):
		self.configure(events=("task_completed",))
		parent = self.create()
		task = self.child(parent)
		for status in ("Todo", "Done", "Done", "Canceled"):
			task.status = status
			task.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.reasons(self.events(parent)[-1]), ["task_completed"])
		self.configure(events=("task_status", "task_completed"))
		task.status = "In Progress"
		task.save()
		task.status = "Done"
		task.save()
		self.flush()
		self.assertEqual(
			[self.reasons(e) for e in self.events(parent)[-2:]], [["task_status"], ["task_completed"]]
		)

	def test_all_other_task_rules_and_creation_grouping(self):
		self.configure(
			events=("task_created", "task_priority", "task_title", "task_description", "task_assigned_to")
		)
		parent = self.create()
		task = self.child(parent)
		task.priority, task.title, task.description, task.assigned_to = (
			"High",
			"Changed",
			"Description",
			"Administrator",
		)
		task.save()
		self.flush()
		self.assertEqual(
			[self.reasons(e) for e in self.events(parent)[1:]],
			[
				["task_created"],
				["task_assigned_to", "task_description", "task_priority", "task_title"],
			],
		)
		task.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 3)

	def test_task_relink_uses_new_target_and_relink_alone_is_not_a_touch(self):
		self.configure(events=("task_title",))
		first, second = self.create(), self.create()
		task = self.child(first)
		task.reference_docname = second.name
		task.save()
		self.flush()
		self.assertEqual(len(self.events(first)), 1)
		self.assertEqual(len(self.events(second)), 1)
		task.title = "Changed"
		task.reference_docname = first.name
		task.save()
		self.flush()
		self.assertEqual(len(self.events(first)), 2)
		self.assertEqual(len(self.events(second)), 1)

	def test_comments_notes_and_task_comments_are_independent(self):
		for doctype in touch.TARGETS:
			self.configure(
				doctype,
				events=("comment_created", "comment_edited", "note_created", "note_edited", "task_comment"),
			)
			parent = self.create(doctype)
			comment = self.comment(parent)
			comment.content = "Edited"
			comment.save()
			comment.save()
			self.comment(parent, comment_type="Info")
			note = self.child(parent, "FCRM Note")
			note.title, note.content = "Changed", "Private content"
			note.save()
			note.save()
			task = self.child(parent)
			task_comment = self.comment(task)
			task_comment.content = "Edited task comment"
			task_comment.save()
			self.flush()
			self.assertEqual(
				[self.reasons(e) for e in self.events(parent)[1:]],
				[
					["comment_created"],
					["comment_edited"],
					["note_created"],
					["note_edited"],
					["task_comment"],
				],
			)
			for event in self.events(parent):
				self.assertNotIn("Private content", json.dumps(dict(event), default=str))
			frappe.delete_doc("FCRM Note", note.name)
			self.flush()
			self.assertEqual(len(self.events(parent)), 6)

	def test_automation_requires_explicit_permission(self):
		self.configure(events=("task_due_date",))
		parent = self.create()
		task = self.child(parent)
		with patch("crm.touch_tracking_internal.operation_origin", return_value="Automation"):
			task.due_date = now_datetime() + timedelta(days=1)
			task.save()
			self.flush()
			self.assertEqual(len(self.events(parent)), 1)
			self.configure(events=("task_due_date",), automation=1)
			task.due_date = None
			task.save()
			self.flush()
			self.assertEqual(self.events(parent)[-1].origin, "Automation")

	def test_missing_event_recovers_all_revisions_with_original_policy_after_disable(self):
		self.configure(events=("task_due_date",))
		parent = self.create()
		task = self.child(parent)
		revision = self.settings.policy_revision
		with patch("crm.touch_tracking._record_event", side_effect=RuntimeError("injected event failure")):
			for days in (1, 2):
				task.due_date = now_datetime() + timedelta(days=days)
				task.save()
		self.settings.enabled = 0
		self.settings.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 3)
		self.assertTrue(
			all(e.policy_revision == revision and e.state == "Applied" for e in self.events(parent)[1:])
		)
		self.assertEqual(touch.recover_missing(), 0)

	def test_grouped_status_and_fields_recovery_preserves_all_reasons(self):
		self.configure(fields=("first_name",))
		parent = self.create()
		with patch("crm.touch_tracking._record_event", side_effect=RuntimeError("injected event failure")):
			parent.first_name = "Changed"
			self.change_status(parent)
		self.assertEqual(touch.recover_missing(), 1)
		self.flush()
		self.assertEqual(self.reasons(self.events(parent)[-1]), ["field:first_name", "status_changed"])
		self.assertEqual(len(self.events(parent)), 2)

	def test_apply_and_queue_failure_do_not_resave_or_fail_business_record(self):
		self.configure(events=("task_due_date",))
		parent = self.create()
		task = self.child(parent)
		task.due_date = now_datetime() + timedelta(days=1)
		task.save()
		modified = get_datetime(task.modified)
		with patch("frappe.enqueue", side_effect=RuntimeError("Redis unavailable")):
			internal._enqueue_safely()
		with patch("crm.touch_tracking._apply_event", side_effect=RuntimeError("apply unavailable")):
			self.flush()
		event = self.events(parent)[-1]
		self.assertEqual(event.state, "Pending")
		frappe.db.set_value(touch.EVENT, event.name, "next_retry_at", None)
		self.flush()
		self.assertEqual(self.events(parent)[-1].state, "Applied")
		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "modified"), modified)

	def test_rollback_and_disabled_history_do_not_leave_or_replay_changes(self):
		parent = self.create()
		task = self.child(parent)
		task.due_date = now_datetime()
		task.save()  # rule still disabled
		self.configure(events=("task_due_date",))
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		frappe.db.savepoint("stage3_rollback")
		task.due_date = None
		task.save()
		frappe.db.rollback(save_point="stage3_rollback")
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		self.assertEqual(frappe.db.count(internal.CHANGE), 0)

	def test_direct_owner_and_native_assignment_each_produce_one_change(self):
		from frappe.desk.form.assign_to import add, remove

		for doctype in touch.TARGETS:
			field = "lead_owner" if doctype == "CRM Lead" else "deal_owner"
			self.configure(doctype, fields=(field,))
			parent = self.create(doctype)
			parent.set(field, "Administrator")
			parent.save()
			self.flush()
			self.assertEqual(len(self.events(parent)), 2)  # nested ToDo did not duplicate parent save
			remove(doctype, parent.name, "Administrator")
			self.flush()
			self.assertEqual(len(self.events(parent)), 3)
			add({"assign_to": ["Administrator"], "doctype": doctype, "name": parent.name})
			self.flush()
			self.assertEqual(len(self.events(parent)), 4)
			self.assertTrue(all(self.reasons(e) == [f"field:{field}"] for e in self.events(parent)[1:]))

	def test_unlinked_sources_and_technical_assignment_do_not_touch(self):
		self.configure(events=internal.INTERNAL_EVENTS)
		parent = self.create()
		task = self.child(parent)
		task.reference_docname = None
		task.title = "Unlinked"
		task.save()
		self.comment(task)
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)  # original task creation only

	def test_source_journal_is_immutable_and_fatal_db_abort_propagates(self):
		self.configure(events=("task_created",))
		parent = self.create()
		task = self.child(parent)
		change = frappe.get_doc(internal.CHANGE, self.events(parent)[-1].name)
		with self.assertRaises(frappe.PermissionError):
			change.save()
		self.configure(events=("task_title",))
		with patch(
			"crm.touch_tracking_internal.materialize_change", side_effect=frappe.QueryDeadlockError("aborted")
		):
			task.title = "Changed"
			with self.assertRaises(frappe.QueryDeadlockError):
				task.save()
