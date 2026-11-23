"""Real owner/stage lifecycle events and customer-facing control boundaries."""

from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications import policy
from exp_theme.notifications.push import delivery, transport
from frappe.utils import now_datetime
from raven.tests.common_push_fixtures import CommonPushFixture

import crm.tests.test_notification_rules as baseline
from crm.notification_rules import api, controls, engine, events, preview


class TestNotificationExpansion(CommonPushFixture):
	def test_stage_choices_identify_pipeline_when_stage_names_repeat(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		for name in ["First local pipeline", "Second local pipeline"]:
			pipeline = frappe.get_doc(
				{"doctype": "CRM Sales Pipeline", "pipeline_name": name + uuid4().hex[:8], "enabled": 1}
			).insert()
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": "Same stage",
					"pipeline": pipeline.name,
					"type": "Open",
				}
			).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		choices = controls.metadata(self.user)["status_options"]["CRM Deal"]
		labels = [row.label for row in choices if row.label.startswith("Same stage · ")]
		self.assertEqual(len(labels), 2)
		self.assertEqual(len(set(labels)), 2)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		self.qualified = "Full qualified " + uuid4().hex[:8]
		frappe.get_doc(
			{"doctype": "CRM Lead Status", "lead_status": self.qualified, "type": "Ongoing"}
		).insert()
		self.initial_status = self.lead.status
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser

	rule = baseline.TestCRMNotificationRules.rule
	save = baseline.TestCRMNotificationRules.save
	transition = baseline.TestCRMNotificationRules.transition
	deliver_bot = baseline.TestCRMNotificationRules.deliver_bot

	def owner(self, doctype, name, user, actor="Administrator"):
		frappe.set_user(actor)  # nosemgrep: frappe-setuser
		doc = frappe.get_doc(doctype, name)
		doc.set("lead_owner" if doctype == "CRM Lead" else "deal_owner", user)
		doc.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		return doc

	def notice_for(self, doctype, name, kind="Assignment"):
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"to_user": self.user, "reference_doctype": doctype, "reference_name": name, "type": kind},
			"*",
			as_dict=True,
			order_by="creation desc",
		)
		return self.notice

	def test_lead_assignment_todo_and_owner_hook_share_one_event_and_two_pushes(self):
		self.owner("CRM Lead", self.lead.name, "Administrator")
		self.save(self.rule(event="lead_assigned", to_statuses=[]))
		frappe.db.delete(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
		)
		doc = self.owner("CRM Lead", self.lead.name, self.user)
		self.notice_for("CRM Lead", doc.name)
		message = self.deliver_bot()
		from crm.api.todo import notify_assigned_user

		todo = frappe.get_doc(
			"ToDo", {"reference_type": "CRM Lead", "reference_name": doc.name, "allocated_to": self.user}
		)
		notify_assigned_user(todo)
		events.lead_changed(doc)
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(send.call_count, 2)
			self.assertEqual(
				{c.args[1]["url"] for c in send.call_args_list},
				{f"/crm/leads/{doc.name}", f"/one/dm-channel/{message.channel_id}"},
			)
		self.assertEqual(
			frappe.db.count("CRM Notification", {"to_user": self.user, "reference_name": doc.name}), 1
		)

	def test_return_to_owner_with_existing_todo_is_a_new_single_event(self):
		todo = frappe.db.get_value(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
			"name",
		)
		self.owner("CRM Lead", self.lead.name, "Administrator")
		self.save(self.rule(event="lead_assigned", to_statuses=[]))
		self.owner("CRM Lead", self.lead.name, self.user)
		self.notice_for("CRM Lead", self.lead.name)
		self.assertIsNotNone(self.notice)
		self.assertEqual(
			frappe.db.get_value(
				"ToDo",
				{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
				"name",
			),
			todo,
		)
		self.assertEqual(len(self.rows()), 1)

	def test_ordinary_owner_unchanged_edit_does_not_assign_again(self):
		self.save(self.rule(event="lead_assigned", to_statuses=[]))
		doc = frappe.get_doc("CRM Lead", self.lead.name)
		doc.phone = "100200300"
		doc.save()
		self.assertEqual(self.rows(), [])

	def test_deal_owner_assignment_deduplicates_native_todo_and_owner_event(self):
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_owner": self.user}).insert()
		self.owner("CRM Deal", deal.name, "Administrator")
		self.save(self.rule(object="CRM Deal", event="deal_assigned", record_ids=[deal.name], to_statuses=[]))
		frappe.db.delete(
			"ToDo", {"reference_type": "CRM Deal", "reference_name": deal.name, "allocated_to": self.user}
		)
		doc = self.owner("CRM Deal", deal.name, self.user)
		self.notice_for("CRM Deal", doc.name)
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 2)
		self.assertEqual(
			frappe.db.count("CRM Notification", {"to_user": self.user, "reference_name": doc.name}), 1
		)

	def test_deal_stage_transition_has_factual_snapshot_and_two_channels(self):
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_owner": self.user}).insert()
		stage = frappe.db.get_value("CRM Deal Status", {"pipeline": deal.pipeline, "type": "Ongoing"}, "name")
		self.save(
			self.rule(
				object="CRM Deal", event="deal_stage_changed", record_ids=[deal.name], to_statuses=[stage]
			)
		)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		previous = deal.status
		deal.status = stage
		deal.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.notice_for("CRM Deal", deal.name, "Status Change")
		item = (
			__import__("crm.notification_source", fromlist=["CRMNotifications"])
			.CRMNotifications()
			.get(self.notice.name, self.user)
		)
		self.assertEqual(
			(item["_crm_snapshot"]["previous_status"], item["_crm_snapshot"]["status"]), (previous, stage)
		)
		message = self.deliver_bot()
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(
				{c.args[1]["url"] for c in send.call_args_list},
				{f"/crm/deals/{deal.name}", f"/one/dm-channel/{message.channel_id}"},
			)
		events.deal_changed(deal)
		self.assertEqual(len(self.rows()), 2)

	def test_combined_pipeline_and_stage_change_emits_one_transition(self):
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_owner": self.user}).insert()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		pipeline = frappe.get_doc(
			{"doctype": "CRM Sales Pipeline", "pipeline_name": "Full " + uuid4().hex, "enabled": 1}
		).insert()
		stage = frappe.get_doc(
			{
				"doctype": "CRM Deal Status",
				"deal_status": "New pipeline stage",
				"pipeline": pipeline.name,
				"type": "Open",
			}
		).insert()
		self.save(
			self.rule(
				object="CRM Deal",
				event="deal_stage_changed",
				record_ids=[deal.name],
				to_statuses=[stage.name],
				pipelines=[pipeline.name],
			)
		)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		old_pipeline = deal.pipeline
		deal.pipeline = pipeline.name
		deal.status = stage.name
		deal.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.notice_for("CRM Deal", deal.name, "Status Change")
		facts = frappe.parse_json(self.notice.exp_notification_snapshot)
		self.assertEqual((facts["previous_pipeline"], facts["pipeline"]), (old_pipeline, pipeline.name))
		self.assertEqual(
			frappe.db.count(
				"CRM Notification",
				{"to_user": self.user, "reference_name": deal.name, "type": "Status Change"},
			),
			1,
		)
		self.assertEqual(len(self.rows()), 1)

	def test_assignment_does_not_notify_other_followers(self):
		self.save(self.rule(event="lead_assigned", scope="followed", record_ids=[], to_statuses=[]))
		api.set_record("CRM Lead", self.lead.name, True, False, 1, uuid4().hex, self.user)
		self.owner("CRM Lead", self.lead.name, "Administrator")
		self.assertEqual(self.rows(), [])

	def test_self_assignment_is_explicitly_enabled(self):
		self.owner("CRM Lead", self.lead.name, "Administrator")
		self.save(self.rule(event="lead_assigned", to_statuses=[], include_self=True))
		self.owner("CRM Lead", self.lead.name, self.user, actor=self.user)
		self.notice_for("CRM Lead", self.lead.name)
		self.assertIsNotNone(self.notice)
		self.assertEqual(len(self.rows()), 1)

	def test_self_assignment_is_quiet_by_default(self):
		self.owner("CRM Lead", self.lead.name, "Administrator")
		self.save(self.rule(event="lead_assigned", to_statuses=[]))
		self.owner("CRM Lead", self.lead.name, self.user, actor=self.user)
		self.assertEqual(self.rows(), [])

	def test_channel_only_save_preserves_legacy_task_behavior_and_opt_out(self):
		state = api.get_settings()
		result = controls.save_channels(
			False,
			True,
			True,
			self.sender.name,
			state["revision"],
			state["master_revisions"]["crm_push"],
			state["master_revisions"]["one_message"],
			uuid4().hex,
			self.user,
		)
		self.assertTrue(result["legacy"])
		self.assertEqual(result["configuration"]["rules"], [])
		self.task()
		self.deliver_bot()
		self.drain()
		self.assertEqual([r.channel for r in self.rows()], ["one_message_push"])

	def test_follow_without_rule_preserves_legacy_and_does_not_enable_status_push(self):
		api.set_record("CRM Lead", self.lead.name, True, False, 0, uuid4().hex, self.user)
		self.assertTrue(api.get_settings()["legacy"])
		self.transition()
		self.assertEqual(self.rows(), [])
		self.assertFalse(controls.record_state("CRM Lead", self.lead.name)["has_follow_rule"])

	def test_master_mutation_replay_is_atomic_and_does_not_repeat_revisions(self):
		state = api.get_settings()
		args = [
			False,
			False,
			False,
			self.sender.name,
			0,
			state["master_revisions"]["crm_push"],
			state["master_revisions"]["one_message"],
			uuid4().hex,
			self.user,
		]
		first = controls.save_channels(*args)
		second = controls.save_channels(*args)
		self.assertTrue(second["replayed"])
		self.assertEqual(first["master_revisions"], second["master_revisions"])
		self.assertFalse(any(second["masters"].values()))

	def test_stale_master_revision_is_rejected_before_writing_other_channels(self):
		state = api.get_settings()
		self.one(False)
		with self.assertRaises(frappe.TimestampMismatchError):
			controls.save_channels(
				False,
				False,
				False,
				self.sender.name,
				0,
				state["master_revisions"]["crm_push"],
				state["master_revisions"]["one_message"],
				uuid4().hex,
				self.user,
			)
		self.assertTrue(api.get_settings()["masters"]["crm_push"])

	def test_preview_uses_all_rules_and_mute_without_creating_records(self):
		first = self.rule(channels={"crm_push": True, "one_message": False, "one_push": False})
		self.save(first)
		draft = self.rule(channels={"crm_push": False, "one_message": True, "one_push": True})
		before = frappe.db.count("CRM Notification")
		result = preview.preview_rule(draft, self.user)
		self.assertTrue(result["hypothetical"])
		self.assertEqual(len(result["items"]), 1)
		self.assertEqual(set(result["items"][0]["matched_rules"]), {first["id"], draft["id"]})
		self.assertTrue(all(result["items"][0]["effective_channels"][key] for key in ("crm_push", "one_message", "one_push")))
		self.assertFalse(result["items"][0]["effective_channels"]["email"])
		self.assertEqual(frappe.db.count("CRM Notification"), before)
		api.set_record("CRM Lead", self.lead.name, False, True, 1, uuid4().hex, self.user)
		self.assertEqual(preview.preview_rule(draft, self.user)["items"], [])

	def test_preview_rejects_inaccessible_record_without_label_or_count_leak(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		private = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "PRIVATE", "lead_owner": "Administrator"}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		with self.assertRaises(frappe.PermissionError):
			preview.preview_rule(self.rule(record_ids=[private.name]), self.user)

	def test_preview_matches_any_selected_target_status(self):
		result = preview.preview_rule(
			self.rule(statuses=[self.qualified], to_statuses=[self.initial_status, self.qualified]), self.user
		)
		self.assertEqual([item["id"] for item in result["items"]], [self.lead.name])

	def test_choices_and_validator_distinguish_standalone_and_linked_tasks(self):
		task = self.task()
		self.assertNotIn(str(task.name), {r["id"] for r in api.search_records("CRM Task")})
		with self.assertRaises(frappe.ValidationError):
			self.save(
				self.rule(
					object="CRM Task", event="task_assigned", record_ids=[str(task.name)], to_statuses=[]
				)
			)

	def test_status_snapshot_remains_factual_after_later_record_change(self):
		self.save(self.rule())
		self.transition()
		original = self.notice
		self.transition(status=self.initial_status)
		self.notice = original
		self.deliver_bot()
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Test Accepted"})

	def test_deleted_record_cancels_pending_source_and_bot_delivery(self):
		self.save(self.rule())
		self.transition()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.db.delete("CRM Lead", {"name": self.lead.name})
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_all_five_events_are_available_but_unsupported_events_are_rejected(self):
		self.assertTrue(all(v["available"] for v in api.options()["events"].values()))
		with self.assertRaises(frappe.ValidationError):
			self.save(self.rule(event="execute_python"))

	def test_shared_settings_expose_only_permission_filtered_crm_link(self):
		from exp_theme.notifications import settings

		self.assertEqual(settings.state(self.user)["crm_rules_url"], "/crm/notification-rules")
