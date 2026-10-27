"""CRM -> Home -> optional One, on an isolated site with outbound delivery off."""
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe import client
from frappe.tests import IntegrationTestCase

from crm.api import notifications as crm_api
from crm.api.todo import notify_assigned_user
from crm.notification_source import CRMNotifications
from exp_theme.notifications import api, delivery


class TestSharedNotifications(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		if not frappe.conf.mute_emails or not frappe.conf.disable_push_notifications:
			raise RuntimeError("Use an isolated notification test site")
		frappe.set_user("Administrator")
		self.user = f"crm-notification-{uuid4().hex}@example.invalid"
		frappe.get_doc({"doctype": "User", "email": self.user, "first_name": "CRM fixture",
			"user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": "Sales User"}, {"role": "Raven User"}]}).insert()
		frappe.db.set_value("Notification Settings", self.user, "enable_email_notifications", 0)
		frappe.set_user(self.user)
		self.lead = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Private CRM fixture", "lead_owner": self.user}).insert()
		frappe.set_user("Administrator")
		bot = frappe.get_doc({"doctype": "Raven Bot", "bot_name": f"CRM fixture {uuid4().hex}", "is_ai_bot": 0}).insert()
		self.sender = frappe.get_doc({"doctype": "EXP Notification Sender", "name": uuid4().hex,
			"label": "CRM fixture", "bot": bot.name, "shared": 1, "enabled": 1}).insert()
		self.bot_user = bot.raven_user
		self.adapter = CRMNotifications()
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.set_user("Administrator")
		super().tearDown()

	def task(self):
		frappe.set_user("Administrator")
		task = frappe.get_doc({"doctype": "CRM Task", "title": "Confidential task title", "assigned_to": self.user,
			"reference_doctype": "CRM Lead", "reference_docname": self.lead.name}).insert()
		frappe.set_user(self.user)
		return task

	def notice(self, task):
		return frappe.db.get_value("CRM Notification", {"to_user": self.user, "notification_type_doctype": "CRM Task",
			"notification_type_doc": task.name}, "*", as_dict=True)

	def enable(self):
		api.save_settings("crm", True, self.sender.name, "None", 0, uuid4().hex)

	def revoke(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator", update_modified=False)
		frappe.db.set_value("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name,
			"allocated_to": self.user}, "status", "Cancelled", update_modified=False)
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", doc=frappe.get_doc("CRM Lead", self.lead.name)))

	def test_real_task_uses_native_notice_once_in_both_panels(self):
		task = self.task()
		notice = self.notice(task)
		self.assertTrue(notice)
		crm = crm_api.get_notifications()
		home = api.list_notifications(source="crm")
		self.assertIn(notice.name, {row["name"] for row in crm["notifications"]})
		self.assertEqual([row["id"] for row in home["items"]], [f"crm:{notice.name}"])
		self.assertFalse(any(row["id"].startswith("platform:") and "Confidential" in row["title"] for row in api.list_notifications()["items"]))
		self.assertEqual(frappe.db.count(delivery.DOCTYPE, {"user": self.user}), 0)

	def test_one_is_optional_for_native_history(self):
		self.task()
		frappe.db.set_value("Raven User", {"user": self.user}, "enabled", 0)
		self.assertFalse(api.get_settings()["one_available"])
		self.assertTrue(crm_api.get_notifications()["notifications"])
		self.assertEqual(api.list_notifications(source="crm")["unread_count"], 1)

	def test_task_preview_uses_allowed_source_fields_without_read_or_task_changes(self):
		task = self.task()
		frappe.db.set_value("CRM Task", task.name, "description", "<p>Estimate and proposal</p>")
		item = api.list_notifications(source="crm")["items"][0]
		value = api.get_notification(item["id"], item["head"])["item"]
		self.assertEqual(value["presentation"]["subject"], task.title)
		self.assertEqual(value["presentation"]["preview"], "Estimate and proposal")
		self.assertFalse(self.notice(task).read)
		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "status"), task.status)
		self.revoke()
		self.assertIsNone(api.get_notification(item["id"], item["head"])["item"])

	def test_preview_respects_field_permissions_on_private_description(self):
		task = self.task()
		frappe.db.set_value("CRM Task", task.name, "description", "Hidden description")
		from frappe.model.document import Document
		original = Document.apply_fieldlevel_read_permissions
		def limited(document):
			original(document)
			if document.doctype == "CRM Task":
				document.description = None
		with patch.object(Document, "apply_fieldlevel_read_permissions", limited):
			value = api.list_notifications(source="crm")["items"][0]
		self.assertEqual(value["presentation"]["preview"], "")

	def test_bot_delivery_is_idempotent_and_contains_no_private_title(self):
		self.enable()
		task = self.task()
		notice = self.notice(task)
		frappe.set_user("Administrator")
		todo = frappe.get_doc("ToDo", {"reference_type": "CRM Task", "reference_name": task.name, "allocated_to": self.user})
		notify_assigned_user(todo)
		frappe.set_user(self.user)
		delivery.publish("crm", notice.name, self.user)
		self.assertEqual(frappe.db.count("CRM Notification", {"last_event_id": notice.last_event_id, "to_user": self.user}), 1)
		self.assertEqual(frappe.db.count(delivery.DOCTYPE, {"user": self.user}), 1)
		name = frappe.db.get_value(delivery.DOCTYPE, {"user": self.user}, "name")
		delivery.claim_and_enqueue(name)
		token = frappe.db.get_value(delivery.DOCTYPE, name, "lease_token")
		delivery.send_claimed(name, token)
		delivery.send_claimed(name, token)
		message = frappe.get_doc("Raven Message", frappe.db.get_value(delivery.DOCTYPE, name, "message_id"))
		self.assertNotIn(task.title, message.text)
		self.assertIn("/crm/leads/", message.text)
		self.assertEqual(message.owner, self.bot_user)
		self.assertFalse(self.notice(task).read)

	def test_home_and_crm_read_the_same_native_record(self):
		task = self.task()
		notice = self.notice(task)
		item = self.adapter.get(notice.name, self.user)
		api.mark_read(item["id"], item["head"])
		self.assertEqual(crm_api.get_notifications()["unread_count"], 0)
		self.assertTrue(self.notice(task).read)

	def test_source_read_is_reflected_in_home(self):
		task = self.task()
		notice = self.notice(task)
		crm_api.mark_as_read(notice.name, self.adapter.get(notice.name, self.user)["head"])
		self.assertEqual(api.list_notifications(source="crm")["unread_count"], 0)

	def test_generic_notification_write_cannot_bypass_read_head(self):
		doc = self.aggregate()
		with self.assertRaises(frappe.PermissionError):
			client.set_value("CRM Notification", doc.name, "read", 1)
		self.assertFalse(frappe.db.get_value("CRM Notification", doc.name, "read"))

	def test_revocation_hides_all_reads_and_cancels_pending_delivery(self):
		self.enable()
		task = self.task()
		notice = self.notice(task)
		item = self.adapter.get(notice.name, self.user)
		self.revoke()
		self.assertEqual(crm_api.get_notifications()["unread_count"], 0)
		self.assertFalse(api.list_notifications(source="crm")["items"])
		self.assertFalse(api.mark_read(item["id"], item["head"])["marked"])
		self.assertFalse(frappe.get_list("CRM Notification", filters={"name": notice.name}, pluck="name"))
		with self.assertRaises(frappe.PermissionError):
			client.get("CRM Notification", notice.name)
		name = frappe.db.get_value(delivery.DOCTYPE, {"user": self.user}, "name")
		delivery.claim_and_enqueue(name)
		delivery.send_claimed(name, frappe.db.get_value(delivery.DOCTYPE, name, "lease_token"))
		self.assertEqual(frappe.db.get_value(delivery.DOCTYPE, name, "status"), "Cancelled")

	def aggregate(self):
		frappe.set_user("Administrator")
		doc = frappe.get_doc({"doctype": "CRM Notification", "to_user": self.user, "from_user": "Administrator",
			"type": "Messenger", "reference_doctype": "CRM Lead", "reference_name": self.lead.name,
			"event_count": 3, "last_event_id": "event-first", "aggregation_key": uuid4().hex,
			"notification_text": "Three fictional messages"}).insert()
		frappe.set_user(self.user)
		return doc

	def test_aggregate_weight_and_stale_heads_are_preserved(self):
		doc = self.aggregate()
		item = self.adapter.get(doc.name, self.user)
		self.assertEqual(api.list_notifications(source="crm")["unread_count"], 3)
		self.assertEqual(crm_api.get_notifications()["unread_count"], 3)
		frappe.db.set_value("CRM Notification", doc.name, {"last_event_id": "event-second", "event_count": 4})
		self.assertFalse(api.mark_read(item["id"], item["head"])["marked"])
		self.assertTrue(crm_api.mark_as_read(doc.name, item["head"])["stale"])
		self.assertTrue(crm_api.mark_as_read(doc.name)["stale"])
		fresh = self.adapter.get(doc.name, self.user)
		self.assertTrue(api.mark_read(fresh["id"], fresh["head"])["marked"])
		self.assertFalse(frappe.db.get_value("CRM Notification", doc.name, "aggregation_key"))

	def test_bounded_mark_all_snapshot_does_not_consume_later_events(self):
		self.task()
		aggregate = self.aggregate()
		snapshot = crm_api.get_notifications()["snapshot_token"]
		later = self.task()
		frappe.db.set_value("CRM Notification", aggregate.name, {"last_event_id": "new-head", "event_count": 4})
		result = crm_api.mark_all_as_read(limit=1, snapshot_token=snapshot)
		self.assertTrue(result["has_more"])
		result = crm_api.mark_all_as_read(limit=1, snapshot_token=snapshot, cursor=result["cursor"])
		self.assertFalse(result["has_more"])
		self.assertFalse(self.notice(later).read)
		self.assertFalse(frappe.db.get_value("CRM Notification", aggregate.name, "read"))

	def test_foreign_account_cannot_use_snapshot_or_read_id(self):
		task = self.task()
		notice = self.notice(task)
		snapshot = crm_api.get_notifications()["snapshot_token"]
		frappe.set_user("Administrator")
		self.assertEqual(crm_api.mark_as_read(notice.name)["marked"], 0)
		with self.assertRaises(frappe.ValidationError):
			crm_api.mark_all_as_read(snapshot_token=snapshot)
		with self.assertRaises(frappe.AuthenticationError):
			crm_api.mark_as_read(notice.name, expected_viewer=self.user)

	def test_disabling_delivery_preserves_both_panels(self):
		self.enable()
		task = self.task()
		api.save_settings("crm", False, self.sender.name, "None", 1, uuid4().hex)
		self.assertTrue(self.adapter.get(self.notice(task).name, self.user))
		self.assertEqual(crm_api.get_notifications()["unread_count"], 1)

	def test_native_task_transaction_rolls_back_notification_and_outbox(self):
		self.enable()
		frappe.db.savepoint("crm_assignment")
		task = self.task()
		notice = self.notice(task)
		self.assertTrue(notice)
		frappe.db.rollback(save_point="crm_assignment")
		self.assertFalse(frappe.db.exists("CRM Task", task.name))
		self.assertFalse(frappe.db.exists("CRM Notification", notice.name))
		self.assertFalse(frappe.db.count(delivery.DOCTYPE, {"user": self.user}))

	def test_without_theme_hook_keeps_native_crm_save(self):
		from crm.notification_source import publish

		with patch("frappe.get_installed_apps", return_value=["frappe", "crm"]):
			publish(frappe._dict(type="Assignment"))

	def test_role_revocation_hides_even_legacy_unlinked_notice(self):
		frappe.set_user("Administrator")
		frappe.get_doc({"doctype": "CRM Notification", "to_user": self.user,
			"type": "Mention", "notification_text": "Legacy private CRM notice"}).insert()
		frappe.get_doc("User", self.user).remove_roles("Sales User")
		frappe.clear_cache(user=self.user)
		frappe.set_user(self.user)
		self.assertFalse(api.list_notifications(source="crm")["items"])
		with self.assertRaises(frappe.PermissionError):
			crm_api.get_notifications()
