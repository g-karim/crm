"""Source-to-outbox integration using real CRM permissions, hooks and One messages."""

from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications import delivery as bot_delivery
from exp_theme.notifications import policy
from exp_theme.notifications.push import delivery, transport
from raven.tests.common_push_fixtures import CommonPushFixture

from crm.notification_rules import api, events
from crm.notification_source import CRMNotifications


class TestCRMNotificationRules(CommonPushFixture):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		self.qualified = "Local qualified " + uuid4().hex[:8]
		frappe.get_doc(
			{"doctype": "CRM Lead Status", "lead_status": self.qualified, "type": "Ongoing"}
		).insert()
		self.initial_status = self.lead.status
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser

	def rule(self, **changes):
		return {
			"id": uuid4().hex,
			"name": "Selected local leads",
			"enabled": True,
			"object": "CRM Lead",
			"event": "lead_status_changed",
			"scope": "selected",
			"record_ids": [self.lead.name],
			"to_statuses": [self.qualified],
			"channels": {"crm_push": True, "one_message": True, "one_push": True},
			**changes,
		}

	def save(self, rule, revision=None, mutation=None):
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		if revision is None:
			revision = api.get_settings()["revision"]
		return api.save_rule(rule, revision, mutation or uuid4().hex, self.user)

	def transition(self, lead=None, status=None, actor=None):
		frappe.set_user(actor or "Administrator")  # nosemgrep: frappe-setuser
		doc = frappe.get_doc("CRM Lead", (lead or self.lead).name)
		doc.status = status or self.qualified
		doc.save()
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"to_user": self.user, "reference_name": doc.name, "type": "Status Change"},
			"*",
			as_dict=True,
		)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		return doc

	def deliver_bot(self):
		name = frappe.db.get_value(
			bot_delivery.DOCTYPE, {"user": self.user, "record_id": self.notice.name}, "name"
		)
		if not name:
			return None
		bot_delivery.claim_and_enqueue(name)
		token = frappe.db.get_value(bot_delivery.DOCTYPE, name, "lease_token")
		bot_delivery.send_claimed(name, token)
		bot_delivery.send_claimed(name, token)
		message = frappe.db.get_value(bot_delivery.DOCTYPE, name, "message_id")
		return frappe.get_doc("Raven Message", message) if message else None

	def test_status_event_produces_two_distinct_pushes_and_exact_routes(self):
		self.save(self.rule())
		doc = self.transition()
		message = self.deliver_bot()
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(send.call_count, 2)
			payloads = [call.args[1] for call in send.call_args_list]
			self.assertEqual(
				{p["url"] for p in payloads},
				{f"/crm/leads/{doc.name}", f"/one/dm-channel/{message.channel_id}"},
			)
			self.assertEqual(len({p["tag"] for p in payloads}), 2)
			self.assertEqual({row.status for row in self.rows()}, {"Test Accepted"})
			self.assertTrue(any(text in message.text.lower() for text in ["lead status", "статус лида"]))
			self.assertFalse(frappe.db.get_value("CRM Notification", self.notice.name, "read"))
			self.assertEqual(frappe.db.get_value("CRM Lead", doc.name, "status"), self.qualified)

	def test_unselected_lead_does_not_deliver(self):
		self.save(self.rule())
		other = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Other", "lead_owner": self.user}
		).insert()
		self.transition(other)
		self.assertIsNone(self.notice)
		self.assertEqual(self.rows(), [])

	def test_wrong_target_status_does_not_deliver(self):
		self.save(self.rule(to_statuses=[self.initial_status]))
		self.transition()
		self.assertIsNone(self.notice)
		self.assertEqual(self.rows(), [])

	def test_ordinary_edit_in_selected_status_is_not_transition(self):
		self.save(self.rule())
		doc = self.transition()
		count = frappe.db.count("CRM Notification", {"to_user": self.user})
		doc.phone = "100200"
		doc.save()
		self.assertEqual(frappe.db.count("CRM Notification", {"to_user": self.user}), count)

	def test_same_source_hook_and_outboxes_can_replay_without_duplicates(self):
		self.save(self.rule())
		doc = self.transition()
		message = self.deliver_bot()
		events.lead_changed(doc)
		delivery.publish("crm", self.notice.name, self.user)
		bot_delivery.publish("crm", self.notice.name, self.user)
		self.drain()
		self.assertEqual(len(self.rows()), 2)
		self.assertEqual(
			frappe.db.count("Raven Message", {"channel_id": message.channel_id, "is_bot_message": 1}), 1
		)
		self.assertEqual(frappe.db.count("CRM Notification", {"last_event_id": self.notice.last_event_id}), 1)

	def test_overlapping_rules_union_channels_without_extra_messages(self):
		self.save(self.rule(channels={"crm_push": True, "one_message": False, "one_push": False}))
		self.save(
			self.rule(
				scope="owned",
				record_ids=[],
				channels={"crm_push": True, "one_message": True, "one_push": True},
			)
		)
		self.transition()
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 2)

	def test_one_message_without_push_keeps_primary(self):
		self.save(self.rule(channels={"crm_push": True, "one_message": True, "one_push": False}))
		self.transition()
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.assertEqual([row.channel for row in self.rows()], ["source_push"])

	def test_source_master_off_does_not_disable_one(self):
		self.primary(False)
		self.save(self.rule())
		self.transition()
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.assertEqual([row.channel for row in self.rows()], ["one_message_push"])

	def test_one_master_off_does_not_disable_primary(self):
		self.one(False)
		self.save(self.rule())
		self.transition()
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual([row.channel for row in self.rows()], ["source_push"])

	def test_rule_change_cancels_old_intents_including_one_message_push(self):
		rule = self.rule()
		self.save(rule)
		self.transition()
		self.deliver_bot()
		self.save({**rule, "name": "Revised rule"})
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_disable_enable_does_not_resurrect_pending(self):
		rule = self.rule()
		self.save(rule)
		self.transition()
		self.save({**rule, "enabled": False})
		self.save(rule)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_record_mute_wins_over_all_matching_rules(self):
		self.save(self.rule())
		api.set_record(
			"CRM Lead", self.lead.name, True, True, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.transition()
		self.assertIsNone(self.notice)

	def test_followed_scope_requires_explicit_follow(self):
		self.save(self.rule(scope="followed", record_ids=[]))
		self.transition()
		self.assertIsNone(self.notice)
		self.transition(status=self.initial_status)
		api.set_record(
			"CRM Lead", self.lead.name, True, False, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.transition()
		self.assertIsNotNone(self.notice)

	def test_filters_are_and_between_fields_or_within_values(self):
		rule = self.rule(statuses=[self.initial_status, self.qualified], owners=[self.user])
		self.save(rule)
		self.transition()
		self.assertIsNotNone(self.notice)
		self.transition(status=self.initial_status)
		self.save({**rule, "statuses": [self.initial_status]})
		before = len(self.rows())
		self.transition()
		self.assertEqual(len(self.rows()), before)

	def test_task_assignment_uses_parent_status_snapshot(self):
		self.save(self.rule(event="task_assigned", to_statuses=[], statuses=[self.initial_status]))
		self.task()
		self.assertEqual(len(self.rows()), 1)
		facts = CRMNotifications().get(self.notice.name, self.user)["_crm_snapshot"]
		self.assertEqual(facts["status"], self.initial_status)
		self.assertEqual(facts["task_status"], "Backlog")

	def test_unchanged_legacy_opt_out_is_preserved_on_first_policy_save(self):
		self.primary(False)
		self.one(False)
		state = self.save(self.rule())
		self.assertFalse(any(state["masters"].values()))
		self.transition()
		self.assertEqual(self.rows(), [])
		self.assertIsNone(self.deliver_bot())

	def test_old_assignment_is_not_backfilled_by_new_rule(self):
		self.task()
		rule = self.rule(event="task_assigned", to_statuses=[])
		self.save(rule)
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_stale_revision_rejected_without_changing_policy(self):
		self.save(self.rule(), revision=0)
		with self.assertRaises(frappe.TimestampMismatchError):
			self.save(self.rule(), revision=0)
		self.assertEqual(api.get_settings()["revision"], 1)

	def test_immutable_operation_replay_after_later_save(self):
		rule, mutation = self.rule(), uuid4().hex
		self.save(rule, 0, mutation)
		self.save(self.rule())
		state = self.save(rule, 0, mutation)
		self.assertTrue(state["replayed"])
		self.assertEqual((state["revision"], state["applied_revision"]), (2, 1))
		with self.assertRaises(frappe.ValidationError):
			self.save({**rule, "name": "Different"}, 0, mutation)

	def test_delete_and_disable_are_distinct_and_keep_history(self):
		rule = self.rule()
		self.save(rule)
		self.transition()
		api.delete_rule(rule["id"], 1, uuid4().hex, self.user)
		self.assertEqual(api.get_settings()["configuration"]["rules"], [])
		self.assertTrue(frappe.db.exists("CRM Notification", self.notice.name))

	def test_unknown_is_terminal_across_replay_and_rule_changes(self):
		self.save(self.rule())
		self.transition()
		with patch.object(transport, "send", side_effect=transport.PushOutcomeUnknown()) as send:
			self.drain()
			self.assertEqual(send.call_count, 1)
		self.save(self.rule())
		with patch.object(transport, "send", side_effect=AssertionError("Unknown replayed")):
			self.drain()
			self.assertEqual({row.status for row in self.rows()}, {"Unknown"})

	def test_self_transition_is_silent_by_default_and_explicitly_configurable(self):
		rule = self.rule()
		self.save(rule)
		self.transition(actor=self.user)
		self.assertIsNone(self.notice)
		self.transition(status=self.initial_status, actor=self.user)
		self.save({**rule, "include_self": True})
		self.transition(actor=self.user)
		self.assertIsNotNone(self.notice)
		self.assertEqual(len(self.rows()), 1)

	def test_selected_record_and_follow_cannot_grant_access(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		private = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Private", "lead_owner": "Administrator"}
		).insert()
		with self.assertRaises(frappe.PermissionError):
			self.save(self.rule(record_ids=[private.name]))
		with self.assertRaises(frappe.PermissionError):
			api.set_record("CRM Lead", private.name, True, False, 0, uuid4().hex, self.user)
		self.assertNotIn(private.name, str(api.search_records("CRM Lead")))

	def test_revoked_access_redacts_selection_and_cancels_delivery(self):
		self.save(self.rule())
		self.transition()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator")
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertNotIn(self.lead.name, str(api.get_settings()))
		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.drain()
		self.assertEqual({row.status for row in self.rows()}, {"Cancelled"})

	def test_schema_rejects_code_arbitrary_users_and_unconnected_events(self):
		for extra in [
			{"python": "True"},
			{"recipient": "Administrator"},
			{"event": "not_connected", "object": "CRM Deal"},
		]:
			with self.assertRaises(frappe.ValidationError):
				self.save({**self.rule(), **extra})

	def test_one_push_without_one_message_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.save(self.rule(channels={"crm_push": True, "one_message": False, "one_push": True}))

	def test_explanation_is_hypothetical_and_does_not_send(self):
		self.save(self.rule())
		result = api.explain_record(
			"CRM Lead", self.lead.name, "lead_status_changed", self.initial_status, self.qualified, self.user
		)
		self.assertTrue(result["hypothetical"])
		self.assertTrue(all(result["effective_channels"][key] for key in ("crm_push", "one_message", "one_push")))
		self.assertFalse(result["effective_channels"]["email"])
		self.assertEqual(self.rows(), [])

	def test_explanation_rechecks_disabled_one_sender(self):
		self.save(self.rule())
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.db.set_value("EXP Notification Sender", self.sender.name, "enabled", 0)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		result = api.explain_record(
			"CRM Lead", self.lead.name, "lead_status_changed", self.initial_status, self.qualified, self.user
		)
		self.assertTrue(result["effective_channels"]["crm_push"])
		self.assertFalse(result["effective_channels"]["one_message"])
		self.assertFalse(result["effective_channels"]["one_push"])

	def test_expected_viewer_guards_all_mutations(self):
		with self.assertRaises(frappe.AuthenticationError):
			api.save_rule(self.rule(), 0, uuid4().hex, "Administrator")
		self.assertEqual(policy.load(self.user, "crm").revision, 0)

	def test_deal_task_filters_use_pipeline_source_and_parent_stage(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		source = frappe.get_doc(
			{"doctype": "CRM Lead Source", "source_name": "Local " + uuid4().hex}
		).insert()
		deal = frappe.get_doc(
			{"doctype": "CRM Deal", "deal_owner": self.user, "source": source.name}
		).insert()
		self.save(
			self.rule(
				object="CRM Deal",
				event="task_assigned",
				record_ids=[deal.name],
				to_statuses=[],
				statuses=[deal.status],
				pipelines=[deal.pipeline],
				sources=[source.name],
			)
		)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": "Deal task",
				"assigned_to": self.user,
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertEqual(len(self.rows()), 1)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		other = frappe.get_doc({"doctype": "CRM Lead Source", "source_name": "Other " + uuid4().hex}).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		deal.source = other.name
		deal.save()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": "Other source task",
				"assigned_to": self.user,
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
			}
		).insert()
		self.assertEqual(len(self.rows()), 1)

	def test_standalone_numeric_task_ids_are_supported(self):
		self.save(
			self.rule(
				object="CRM Task",
				event="task_assigned",
				scope="owned",
				record_ids=[],
				to_statuses=[],
				statuses=["Backlog"],
			)
		)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		task = frappe.get_doc(
			{"doctype": "CRM Task", "title": "Standalone", "assigned_to": self.user}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertEqual(len(self.rows()), 1)
		self.assertIn(str(task.name), {row["id"] for row in api.search_records("CRM Task")})

	def test_all_accessible_scope_does_not_include_an_inaccessible_lead(self):
		self.save(self.rule(scope="all_accessible", record_ids=[]))
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		private = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Private all", "lead_owner": "Administrator"}
		).insert()
		self.transition(private)
		self.assertIsNone(self.notice)
		self.assertEqual(self.rows(), [])

	def test_generic_crud_cannot_forge_policy_even_with_internal_flags(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": policy.DOCTYPE,
					"name": uuid4().hex,
					"user": self.user,
					"source": "crm",
					"configuration": "{}",
					"flags": {"internal_write": True},
				}
			).insert()

	def test_user_without_crm_cannot_read_or_save_policy(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		user = "no-crm-" + uuid4().hex + "@example.invalid"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": user,
				"first_name": "No CRM",
				"send_welcome_email": 0,
				"roles": [{"role": "Raven User"}, {"role": "Desk User"}],
			}
		).insert()
		frappe.set_user(user)  # nosemgrep: frappe-setuser
		with self.assertRaises(frappe.PermissionError):
			api.get_settings(user)

	def test_malformed_object_and_event_are_validation_errors(self):
		for changes in [{"object": []}, {"event": []}, {"include_self": "false"}]:
			with self.assertRaises(frappe.ValidationError):
				self.save({**self.rule(), **changes})

	def test_mutation_requires_explicit_viewer(self):
		with self.assertRaises(frappe.AuthenticationError):
			api.save_rule(self.rule(), 0, uuid4().hex)

	def test_explicit_self_task_assignment_uses_the_native_hook(self):
		self.save(self.rule(event="task_assigned", to_statuses=[], include_self=True))
		frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": "My own task",
				"assigned_to": self.user,
				"reference_doctype": "CRM Lead",
				"reference_docname": self.lead.name,
			}
		).insert()
		self.assertEqual(len(self.rows()), 1)

	def test_optional_crm_without_theme_does_not_load_policy_hooks(self):
		with (
			patch("frappe.get_installed_apps", return_value=["frappe", "crm"]),
			patch("frappe.db.table_exists") as tables,
		):
			events.capture_notification(None)
			events.lead_changed(None)
			tables.assert_not_called()
