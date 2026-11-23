"""Native comment lifecycle, current audience and per-channel deduplication."""

from unittest.mock import patch
from uuid import uuid4

import frappe
from exp_theme.notifications import policy
from exp_theme.notifications.push import transport
from raven.tests.common_push_fixtures import CommonPushFixture

import crm.tests.test_notification_rules as baseline
from crm.notification_rules import api, discussions, preview
from crm.notification_source import CRMNotifications


class TestCRMDiscussions(CommonPushFixture):
	def test_deal_comment_uses_current_pipeline_and_exact_comment_route(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_owner": self.user}).insert()
		self.save(self.rule(object="CRM Deal", record_ids=[deal.name], pipelines=[deal.pipeline]))
		doc = self.comment(True, reference_doctype="CRM Deal", reference_name=deal.name)
		self.assertEqual(
			CRMNotifications().get(self.notice.name, self.user)["route"], f"/crm/deals/{deal.name}#{doc.name}"
		)

	def test_a_mention_cannot_grant_access_to_private_record(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Other private lead", "lead_owner": "Administrator"}
		).insert()
		self.comment(True, reference_name=lead.name)
		self.assertIsNone(self.notice)

	def setUp(self):
		super().setUp()
		self.initial_rule = self.rule()
		self.save(self.initial_rule)

	save = baseline.TestCRMNotificationRules.save
	deliver_bot = baseline.TestCRMNotificationRules.deliver_bot

	def rule(self, **values):
		return {
			"id": uuid4().hex,
			"name": "Local discussions",
			"enabled": True,
			"object": "CRM Lead",
			"event": "comment_added",
			"scope": "selected",
			"record_ids": [self.lead.name],
			"channels": {"crm_push": True, "one_message": True, "one_push": True},
			**values,
		}

	def content(self, mentioned=False):
		return (
			"<p>Local comment "
			+ (
				f'<span data-type="mention" data-id="{self.user}" data-label="Viewer">Viewer</span>'
				if mentioned
				else "text"
			)
			+ "</p>"
		)

	def comment(self, mentioned=False, **values):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		doc = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"content": self.content(mentioned),
				**values,
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.notice = frappe.db.get_value(
			"CRM Notification",
			{"notification_type_doctype": "Comment", "notification_type_doc": doc.name, "to_user": self.user},
			"*",
			as_dict=True,
		)
		return doc

	def edit(self, doc, content):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		current = frappe.get_doc("Comment", doc.name)
		current.content = content
		current.save()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		return current

	def test_comment_has_one_history_one_bot_and_two_pushes_with_exact_anchor(self):
		doc = self.comment()
		message = self.deliver_bot()
		with patch.object(transport, "send", wraps=transport.send) as send:
			self.drain()
			self.assertEqual(send.call_count, 2)
			self.assertEqual(
				{c.args[1]["url"] for c in send.call_args_list},
				{f"/crm/leads/{self.lead.name}#{doc.name}", f"/one/dm-channel/{message.channel_id}"},
			)
			self.assertEqual(len({c.args[1]["tag"] for c in send.call_args_list}), 2)

	def test_mention_and_comment_rules_union_channels_without_duplicate(self):
		self.save(self.rule(event="record_mentioned"))
		doc = self.comment(True)
		self.deliver_bot()
		self.drain()
		self.assertEqual(frappe.db.count("CRM Notification", {"notification_type_doc": doc.name}), 1)
		self.assertEqual(len(self.rows()), 2)

	def test_mention_does_not_match_an_unmentioned_user(self):
		api.delete_rule(
			api.get_settings()["configuration"]["rules"][0]["id"],
			api.get_settings()["revision"],
			uuid4().hex,
			self.user,
		)
		self.save(self.rule(event="record_mentioned"))
		self.comment()
		self.assertIsNone(self.notice)

	def test_duplicate_mention_spans_still_have_one_delivery(self):
		self.comment(content=self.content(True) * 3)
		self.deliver_bot()
		self.drain()
		self.assertEqual(len(self.rows()), 2)

	def test_replayed_hook_and_ordinary_edit_do_not_repeat(self):
		doc = self.comment(True)
		self.deliver_bot()
		self.drain()
		discussions.changed(doc)
		self.edit(doc, self.content(True) + "<p>Edited</p>")
		self.assertEqual(len(self.rows()), 2)

	def test_adding_a_mention_on_edit_can_notify_a_new_recipient_once(self):
		api.delete_rule(
			api.get_settings()["configuration"]["rules"][0]["id"],
			api.get_settings()["revision"],
			uuid4().hex,
			self.user,
		)
		self.save(self.rule(event="record_mentioned"))
		doc = self.comment()
		self.assertIsNone(self.notice)
		self.edit(doc, self.content(True))
		self.assertEqual(frappe.db.count("CRM Notification", {"notification_type_doc": doc.name}), 1)

	def test_removing_mention_cancels_pending_channels(self):
		doc = self.comment(True)
		self.edit(doc, self.content())
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_deleted_comment_hides_history_and_cancels_delivery(self):
		doc = self.comment()
		frappe.db.delete("Comment", {"name": doc.name})
		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_one_push_rechecks_comment_after_message_exists(self):
		doc = self.comment(True)
		self.deliver_bot()
		self.edit(doc, self.content())
		self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_current_parent_status_is_rechecked(self):
		self.save({**self.initial_rule, "statuses": [self.lead.status]})
		self.comment()
		frappe.db.set_value("CRM Lead", self.lead.name, "status", "Not current")
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def test_mute_wins_over_both_categories(self):
		self.save(self.rule(event="record_mentioned"))
		api.set_record(
			"CRM Lead", self.lead.name, False, True, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.comment(True)
		self.assertIsNone(self.notice)

	def test_followed_rule_requires_follow(self):
		value = self.initial_rule.copy()
		self.save({**value, "scope": "followed", "record_ids": []})
		self.comment()
		self.assertIsNone(self.notice)
		api.set_record(
			"CRM Lead", self.lead.name, True, False, api.get_settings()["revision"], uuid4().hex, self.user
		)
		self.comment()
		self.assertIsNotNone(self.notice)

	def test_technical_comment_types_are_silent(self):
		for kind in ["Info", "Assigned", "Like", "Edit"]:
			self.comment(True, comment_type=kind)
			self.assertIsNone(self.notice)

	def test_self_comments_silent_unless_explicit_rule_allows(self):
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		from crm.api.comment import add_comment

		doc = add_comment("CRM Lead", self.lead.name, self.content(True))
		self.assertFalse(frappe.db.exists("CRM Notification", {"notification_type_doc": doc.name}))
		self.save(self.rule(include_self=True))
		doc = add_comment("CRM Lead", self.lead.name, self.content(True))
		self.assertTrue(frappe.db.exists("CRM Notification", {"notification_type_doc": doc.name}))

	def test_revoked_parent_access_cancels_and_hides(self):
		self.comment(True)
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "_assign", "[]")
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.clear_cache(user=self.user)
		self.assertIsNone(CRMNotifications().get(self.notice.name, self.user))
		self.assertIsNone(self.deliver_bot())
		self.drain()

	def test_disabled_rule_has_no_new_comment_notification(self):
		value = self.initial_rule.copy()
		self.save({**value, "enabled": False})
		self.comment(True)
		self.assertIsNone(self.notice)

	def test_legacy_mention_keeps_native_history_without_implicit_external_delivery(self):
		frappe.db.delete(policy.DOCTYPE, {"user": self.user, "source": "crm"})
		self.comment(True)
		self.assertIsNotNone(self.notice)
		self.assertIsNone(self.deliver_bot())
		self.assertEqual(self.rows(), [])

	def test_preview_is_hypothetical_without_history_or_delivery(self):
		before = frappe.db.count("CRM Notification")
		value = preview.preview_rule(self.rule(event="record_mentioned"), self.user)
		self.assertEqual([item["id"] for item in value["items"]], [self.lead.name])
		self.assertEqual(frappe.db.count("CRM Notification"), before)

	def test_source_history_and_outboxes_rollback_together(self):
		frappe.db.savepoint("discussion_rollback")
		doc = self.comment()
		frappe.db.rollback(save_point="discussion_rollback")
		self.assertFalse(frappe.db.exists("Comment", doc.name))
		self.assertEqual(self.rows(), [])

	def test_unknown_result_is_never_resent_by_comment_replay(self):
		doc = self.comment()
		frappe.db.set_value("EXP Push Delivery", self.rows()[0].name, "status", "Unknown")
		discussions.changed(doc)
		with patch.object(transport, "send") as send:
			self.drain()
			send.assert_not_called()
