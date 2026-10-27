"""Native transactional inbox acceptance; no provider or mail network requests."""

from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import frappe
from crm_messenger.api import conversations, messages
from frappe.utils import add_to_date, now_datetime

from crm.api import inbox


class TestInbox(TestCase):
	def test_email_transport_is_bound_to_source_account_before_native_queue(self):
		account = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": self.tag.lower() + "-route@example.invalid",
				"email_account_name": self.tag,
				"enable_incoming": 0,
				"enable_outgoing": 0,
			}
		).insert(ignore_permissions=True)
		mail = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "client@example.invalid",
				"recipients": account.email_id,
				"email_account": account.name,
				"subject": "Exact account",
				"content": "Original",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
			}
		).insert(ignore_permissions=True)
		source, rows = inbox._load("email", mail.name)
		with patch.object(type(mail), "send_email", autospec=True) as send:
			result = inbox._make_email(source, rows, "Reply", "Re: Exact account", "", "", "", [], send=True)
			self.assertEqual(send.call_args.args[0].email_account, account.name)
			self.assertEqual(send.call_args.kwargs, {"now": False})
		self.assertEqual(frappe.db.get_value("Communication", result["name"], "email_account"), account.name)

	def test_deal_profile_withholds_private_contact_and_its_copied_phone(self):
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": self.tag,
				"phone_nos": [{"phone": "79990000000", "is_primary_mobile_no": 1}],
			}
		).insert()
		deal = frappe.get_doc(
			{
				"doctype": "CRM Deal",
				"deal_name": self.tag,
				"status": "Qualification",
				"deal_owner": self.user,
				"currency": frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
				"contacts": [{"contact": contact.name, "is_primary": 1}],
			}
		).insert()
		context = {"doctype": "CRM Deal", "name": deal.name}
		self.assertTrue(inbox._customer(context)["contacts"])
		native = frappe.has_permission
		with patch(
			"frappe.has_permission",
			side_effect=lambda dt, *a, **kw: False if dt == "Contact" else native(dt, *a, **kw),
		):
			profile = inbox._customer(context)
			self.assertEqual(profile["contacts"], [])
			self.assertEqual(profile["phone"], "")

	def test_search_and_related_deal_filter_do_not_copy_or_expose_hidden_lead_history(self):
		self.grant()
		deal = frappe.get_doc(
			{
				"doctype": "CRM Deal",
				"deal_name": self.tag,
				"lead": self.lead.name,
				"deal_owner": self.user,
				"currency": frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
				"status": "Qualification",
			}
		).insert()
		result = inbox.list_threads(
			view="all",
			query="searchable inbound",
			reference_doctype="CRM Deal",
			reference_name=deal.name,
			limit=1,
		)
		self.assertEqual(result["total"], 1)
		self.assertEqual(result["items"][0]["name"], self.conversation.name)
		self.assertFalse(result["has_more"])
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", self.other, update_modified=False)
		frappe.db.set_value(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
			"status",
			"Cancelled",
			update_modified=False,
		)
		frappe.set_user("Administrator")
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead.name))
		self.assertTrue(frappe.has_permission("CRM Deal", "read", deal.name))
		self.assertEqual(
			inbox.list_threads(view="all", reference_doctype="CRM Deal", reference_name=deal.name)["items"],
			[],
		)

	def test_subscription_restricted_body_does_not_leak_through_previews_or_search(self):
		self.grant()
		frappe.db.set_value(
			"Messenger Channel",
			self.channel.name,
			{
				"provider": "avito_direct",
				"raw_data": frappe.as_json(
					{"integration": {"response": {"reason": "messenger_subscription_required"}}}
				),
			},
			update_modified=False,
		)
		frappe.db.set_value(
			"Messenger Conversation",
			self.conversation.name,
			"provider",
			"avito_direct",
			update_modified=False,
		)
		self.assertEqual(inbox.list_threads(view="all", query="Secret searchable inbound")["items"], [])
		rows = inbox.list_threads(view="all", query=self.tag)["items"]
		self.assertEqual(len(rows), 1)
		self.assertNotIn("Secret", rows[0]["preview"])

	def setUp(self):
		self.addCleanup(self.cleanup)
		frappe.set_user("Administrator")
		self.tag = "InboxQA" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		self.other = "other-" + self.user
		for email in (self.user, self.other):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": self.tag,
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": "Sales User"}],
				}
			).insert()
		self.lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": self.tag, "status": "New", "lead_owner": self.user}
		).insert()
		self.channel = frappe.get_doc(
			{
				"doctype": "Messenger Channel",
				"name": self.tag,
				"provider": "telegram_bot",
				"platform": "telegram",
				"custom_display_name": self.tag,
				"enabled": 0,
				"state": "unchecked",
			}
		).insert(ignore_permissions=True)
		self.conversation = frappe.get_doc(
			{
				"doctype": "Messenger Conversation",
				"provider": "telegram_bot",
				"provider_chat_key": "local-inbox-demo:" + self.tag,
				"channel": self.channel.name,
				"external_chat_id": self.tag,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"client_name": self.tag,
				"status": "Open",
			}
		).insert(ignore_permissions=True)
		self.message = self.inbound("Secret searchable inbound")
		self.network = patch(
			"requests.sessions.Session.request",
			side_effect=AssertionError("No external requests in inbox tests"),
		)
		self.network.start()
		self.addCleanup(self.network.stop)

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.db.before_commit.reset()
		frappe.local.message_log = []

	def inbound(self, text):
		return frappe.get_doc(
			{
				"doctype": "Messenger Message",
				"conversation": self.conversation.name,
				"channel": self.channel.name,
				"provider": "telegram_bot",
				"platform": "telegram",
				"provider_message_key": self.tag + uuid4().hex,
				"direction": "inbound",
				"message_type": "text",
				"text": text,
				"message_datetime": now_datetime(),
				"status": "received",
			}
		).insert(ignore_permissions=True)

	def grant(self, user=None, send=True):
		frappe.set_user("Administrator")
		inbox.set_account_access("messenger", self.channel.name, user or self.user, 1, int(send))
		frappe.set_user(user or self.user)

	def test_account_denial_precedes_search_counts_and_native_history(self):
		frappe.set_user(self.user)
		result = inbox.list_threads(view="all", query="Secret searchable inbound")
		self.assertEqual(result["items"], [])
		self.assertEqual(result["total"], 0)
		self.assertEqual(result["counts"]["unread"], 0)
		for action in [
			lambda: inbox.get_thread("messenger", self.conversation.name),
			lambda: messages.get_message(self.message.name),
			lambda: messages.get_message_page(conversation=self.conversation.name),
		]:
			with self.assertRaises(frappe.PermissionError):
				action()
		self.assertEqual(
			messages.get_messages(reference_doctype="CRM Lead", reference_name=self.lead.name)["messages"], []
		)
		self.assertEqual(
			messages.get_message_page(reference_doctype="CRM Lead", reference_name=self.lead.name)[
				"messages"
			],
			[],
		)
		self.assertEqual(conversations.get_conversations("CRM Lead", self.lead.name)["conversations"], [])

	def test_granted_account_does_not_override_hidden_customer(self):
		self.grant(self.other)
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.lead.name))
		self.assertFalse(
			any(r["name"] == self.conversation.name for r in inbox.list_threads(view="all")["items"])
		)
		with self.assertRaises(frappe.PermissionError):
			inbox.get_thread("messenger", self.conversation.name)

	def test_read_grant_is_distinct_from_operator_grant(self):
		self.grant(send=False)
		data = inbox.get_thread("messenger", self.conversation.name)
		self.assertEqual(len(data["messages"]), 1)
		self.assertFalse(data["can_send"])
		self.assertFalse(data["can_note"])
		self.assertFalse(data["can_task"])
		with self.assertRaises(frappe.PermissionError):
			inbox.update_work("messenger", self.conversation.name, 0, status="closed")
		with self.assertRaises(frappe.PermissionError):
			messages.send_message(
				conversation=self.conversation.name, text="No", client_request_id=str(uuid4())
			)

	def test_read_cursor_and_draft_are_personal_not_source_read_or_status(self):
		self.grant()
		before = frappe.db.get_value(
			"Messenger Conversation",
			self.conversation.name,
			["unread_count", "status", "local_read_sequence"],
			as_dict=True,
		)
		data = inbox.get_thread("messenger", self.conversation.name)
		stored = inbox.save_private(
			"messenger",
			self.conversation.name,
			0,
			draft={"text": "Private draft"},
			read_cursor=data["read_cursor"],
		)
		self.assertEqual(stored["revision"], 1)
		self.assertEqual(inbox.get_thread("messenger", self.conversation.name)["thread"]["unread"], 0)
		self.assertEqual(
			frappe.db.get_value(
				"Messenger Conversation",
				self.conversation.name,
				["unread_count", "status", "local_read_sequence"],
				as_dict=True,
			),
			before,
		)
		frappe.set_user("Administrator")
		self.assertEqual(inbox._private("messenger", self.conversation.name)["draft"], {})
		self.assertEqual(inbox.get_thread("messenger", self.conversation.name)["thread"]["unread"], 1)

	def test_private_conflict_keeps_winning_text(self):
		self.grant()
		inbox.save_private("messenger", self.conversation.name, 0, draft={"text": "Winner"})
		with self.assertRaises(frappe.TimestampMismatchError):
			inbox.save_private("messenger", self.conversation.name, 0, draft={"text": "Stale"})
		self.assertEqual(inbox._private("messenger", self.conversation.name)["draft"]["text"], "Winner")

	def test_account_switch_cannot_write_the_previous_viewers_draft_or_actions(self):
		self.grant()
		before = {
			dt: frappe.db.count(dt)
			for dt in [
				inbox.STATE,
				inbox.WORK,
				inbox.OP,
				"FCRM Note",
				"CRM Task",
				"Messenger Message",
				"File",
				inbox.ACCESS,
			]
		}
		cases = [
			(
				inbox.save_private,
				dict(
					kind="messenger",
					name=self.conversation.name,
					expected_revision=0,
					draft={"text": "Private previous user"},
				),
			),
			(
				inbox.update_work,
				dict(kind="messenger", name=self.conversation.name, expected_revision=0, status="closed"),
			),
			(
				inbox.add_note,
				dict(
					kind="messenger",
					name=self.conversation.name,
					text="Previous user note",
					mutation_id=str(uuid4()),
					context_doctype="CRM Lead",
					context_name=self.lead.name,
				),
			),
			(
				inbox.add_task,
				dict(kind="messenger", name=self.conversation.name, values={}, mutation_id=str(uuid4())),
			),
			(
				inbox.send_reply,
				dict(
					kind="messenger",
					name=self.conversation.name,
					text="Previous user reply",
					mutation_id=str(uuid4()),
				),
			),
			(
				inbox.link_customer,
				dict(
					kind="messenger",
					name=self.conversation.name,
					reference_doctype="CRM Lead",
					reference_name=self.lead.name,
				),
			),
			(
				inbox.set_account_access,
				dict(kind="messenger", account=self.channel.name, user=self.user, can_read=0),
			),
			(inbox.upload_attachment, dict(kind="messenger", docname=self.conversation.name)),
		]
		for endpoint, kwargs in cases:
			with self.subTest(endpoint=endpoint.__name__), self.assertRaises(frappe.PermissionError):
				endpoint(**kwargs, expected_viewer=self.other)
		self.assertEqual(before, {dt: frappe.db.count(dt) for dt in before})
		stored = inbox.save_private(
			"messenger", self.conversation.name, 0, draft={"text": "Own draft"}, expected_viewer=self.user
		)
		self.assertEqual(stored["draft"]["text"], "Own draft")

	def test_reader_cannot_acknowledge_a_message_from_another_thread(self):
		self.grant()
		with self.assertRaises(frappe.ValidationError):
			inbox.save_private("messenger", self.conversation.name, 0, read_cursor=["2026-01-01", "foreign"])

	def test_new_inbound_reopens_closed_work_without_changing_source(self):
		self.grant()
		inbox.update_work("messenger", self.conversation.name, 0, status="closed", assigned_to=self.user)
		self.inbound("New inbound")
		data = inbox.get_thread("messenger", self.conversation.name)
		self.assertEqual(data["thread"]["status"], "needs_reply")
		self.assertEqual(data["thread"]["work"]["assigned_to"], self.user)
		self.assertEqual(
			frappe.db.get_value("Messenger Conversation", self.conversation.name, "status"), "Open"
		)

	def test_snooze_requires_a_future_deadline_and_conflicts_are_detected(self):
		self.grant()
		with self.assertRaises(frappe.ValidationError):
			inbox.update_work(
				"messenger", self.conversation.name, 0, status="snoozed", snoozed_until="2000-01-01"
			)
		inbox.update_work(
			"messenger",
			self.conversation.name,
			0,
			status="snoozed",
			snoozed_until=add_to_date(now_datetime(), hours=1),
		)
		with self.assertRaises(frappe.TimestampMismatchError):
			inbox.update_work("messenger", self.conversation.name, 0, status="closed")

	def test_note_is_canonical_and_exact_retry_does_not_duplicate_it(self):
		self.grant()
		request = str(uuid4())
		kwargs = {
			"kind": "messenger",
			"name": self.conversation.name,
			"text": "<script>plain note</script>",
			"mutation_id": request,
			"context_doctype": "CRM Lead",
			"context_name": self.lead.name,
		}
		first = inbox.add_note(**kwargs)
		second = inbox.add_note(**kwargs)
		self.assertEqual(first, second)
		doc = frappe.get_doc("FCRM Note", first["name"])
		self.assertEqual(doc.reference_docname, self.lead.name)
		self.assertIn("&lt;script&gt;", doc.content)
		self.assertEqual(frappe.db.count("FCRM Note", {"reference_docname": self.lead.name}), 1)
		with self.assertRaises(frappe.ValidationError):
			inbox.add_note(**{**kwargs, "text": "different"})

	def test_task_is_native_and_idempotent(self):
		self.grant()
		request = str(uuid4())
		values = {
			"title": self.tag,
			"context_kind": "lead",
			"context_name": self.lead.name,
			"assigned_to": self.user,
			"status": "Todo",
			"priority": "Medium",
		}
		first = inbox.add_task("messenger", self.conversation.name, values, request)
		second = inbox.add_task("messenger", self.conversation.name, values, request)
		self.assertEqual(first["task"]["name"], second["task"]["name"])
		doc = frappe.get_doc("CRM Task", first["task"]["name"])
		self.assertEqual(doc.reference_docname, self.lead.name)

	def test_note_context_cannot_be_redirected_to_an_unrelated_card(self):
		self.grant()
		with self.assertRaises(frappe.PermissionError):
			inbox.add_note(
				"messenger", self.conversation.name, "No", str(uuid4()), "CRM Lead", "not-this-customer"
			)

	def test_demo_response_is_stored_locally_once_and_never_claims_delivery(self):
		self.grant()
		request = str(uuid4())
		first = inbox.send_reply("messenger", self.conversation.name, "Local reply", request)
		second = inbox.send_reply("messenger", self.conversation.name, "Local reply", request)
		self.assertEqual(first, second)
		self.assertTrue(first["local_only"])
		message = frappe.get_doc("Messenger Message", first["name"])
		self.assertEqual(message.status, "queued")
		self.assertEqual(message.provider_status, "local_preview")
		self.assertFalse(message.external_message_id)

	def test_service_storage_cannot_be_inserted_through_generic_rest(self):
		self.grant()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": inbox.STATE, "name": "forged", "user": self.user}).insert(
				ignore_permissions=True
			)

	def test_revocation_hides_existing_private_draft_and_native_messages(self):
		self.grant()
		inbox.save_private("messenger", self.conversation.name, 0, draft={"text": "Personal"})
		frappe.set_user("Administrator")
		inbox.set_account_access("messenger", self.channel.name, self.user, 0, 0)
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			inbox.save_private("messenger", self.conversation.name, 1, draft={"text": "After revocation"})
		with self.assertRaises(frappe.PermissionError):
			messages.get_message(self.message.name)

	def test_unlinked_queue_is_admin_only_even_with_channel_grant(self):
		frappe.db.set_value(
			"Messenger Conversation",
			self.conversation.name,
			{"reference_doctype": None, "reference_name": None},
			update_modified=False,
		)
		self.grant()
		with self.assertRaises(frappe.PermissionError):
			inbox.get_thread("messenger", self.conversation.name)

	def test_email_threads_use_reply_identity_not_equal_subjects(self):
		def mail(reply=None):
			return frappe.get_doc(
				{
					"doctype": "Communication",
					"communication_type": "Communication",
					"communication_medium": "Email",
					"sent_or_received": "Received",
					"sender": "client@example.invalid",
					"recipients": "team@example.invalid",
					"subject": "Same subject",
					"content": "Email body",
					"reference_doctype": "CRM Lead",
					"reference_name": self.lead.name,
					"in_reply_to": reply,
					"message_id": f"<{uuid4()}@inbox.local.invalid>",
				}
			).insert(ignore_permissions=True)

		first = mail()
		reply = mail(first.name)
		other = mail()
		groups = inbox._groups("email")
		self.assertEqual({r.name for r in groups[first.name]}, {first.name, reply.name})
		self.assertEqual({r.name for r in groups[other.name]}, {other.name})

	def test_missing_email_account_never_enables_real_send(self):
		mail = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "client@example.invalid",
				"recipients": "team@example.invalid",
				"subject": "Unconfigured",
				"content": "No route",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
			}
		).insert(ignore_permissions=True)
		self.assertFalse(inbox.get_thread("email", mail.name)["can_send"])
		with self.assertRaises(frappe.PermissionError):
			inbox.send_reply("email", mail.name, "Not sent", str(uuid4()))

	def test_guest_denial_has_no_account_metadata(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			inbox.list_threads()
		with self.assertRaises(frappe.PermissionError):
			inbox.accounts()

	def test_demo_email_reply_preserves_native_thread_and_exact_retries(self):
		mail = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "client@example.invalid",
				"recipients": "team@example.invalid",
				"subject": "Local example",
				"content": "Original mail",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
				"message_id": f"<{uuid4()}@inbox.local.invalid>",
			}
		).insert(ignore_permissions=True)
		request = str(uuid4())
		first = inbox.send_reply(
			"email",
			mail.name,
			"Local response",
			request,
			to="client@example.invalid",
			cc="other@example.invalid",
		)
		self.assertEqual(
			first,
			inbox.send_reply(
				"email",
				mail.name,
				"Local response",
				request,
				to="client@example.invalid",
				cc="other@example.invalid",
			),
		)
		reply = frappe.get_doc("Communication", first["name"])
		self.assertEqual(reply.in_reply_to, mail.name)
		self.assertEqual(reply.cc, "other@example.invalid")
		self.assertEqual(reply.reference_name, self.lead.name)
		self.assertEqual(len(inbox._groups("email")[mail.name]), 2)

	def test_account_permission_also_protects_native_mail_and_private_files(self):
		account = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": self.tag.lower() + "-mail@example.invalid",
				"email_account_name": self.tag,
				"enable_incoming": 0,
				"enable_outgoing": 0,
			}
		).insert(ignore_permissions=True)
		mail = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "client@example.invalid",
				"recipients": account.email_id,
				"subject": "Private mailbox",
				"content": "Mailbox secret",
				"email_account": account.name,
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(self.user)
		self.assertTrue(frappe.has_permission("CRM Lead", "read", self.lead.name))
		self.assertFalse(frappe.has_permission("Communication", "read", doc=mail))
		with self.assertRaises(frappe.PermissionError):
			inbox.get_thread("email", mail.name)
		frappe.set_user("Administrator")
		inbox.set_account_access("email", account.name, self.user, 1, 0)
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("Communication", "read", doc=mail))
		self.assertEqual(inbox.get_thread("email", mail.name)["messages"][0]["text"], "Mailbox secret")
		self.assertFalse(inbox.get_thread("email", mail.name)["can_send"])
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", self.user)
		user.append("roles", {"role": "Inbox User"})
		user.save()
		frappe.set_user(self.user)
		self.assertTrue(frappe.has_permission("Communication", "read", doc=mail))
		frappe.set_user("Administrator")
		inbox.set_account_access("email", account.name, self.user, 0, 0)
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("Communication", "read", doc=mail))

	def test_email_headers_reject_line_break_injection(self):
		with self.assertRaises(frappe.ValidationError):
			inbox._addresses("client@example.invalid\r\nBCC:steal@example.invalid")

	def test_dedicated_worker_ignores_demo_and_legacy_queue_and_checks_actor(self):
		from crm.inbox_delivery import work

		self.grant()
		frappe.db.set_value(
			"Messenger Conversation",
			self.conversation.name,
			"provider_chat_key",
			"worker-proof:" + self.tag,
			update_modified=False,
		)
		own = frappe.get_doc(
			{
				"doctype": "Messenger Message",
				"provider": "telegram_bot",
				"conversation": self.conversation.name,
				"channel": self.channel.name,
				"direction": "outbound",
				"text": "Explicit inbox reply",
				"status": "queued",
				"message_datetime": now_datetime(),
				"client_request_id": "crm-inbox-" + uuid4().hex,
				"crm_user": self.user,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Messenger Message",
				"provider": "telegram_bot",
				"conversation": self.conversation.name,
				"channel": self.channel.name,
				"direction": "outbound",
				"text": "Legacy queued reply",
				"status": "queued",
				"message_datetime": now_datetime(),
				"client_request_id": uuid4().hex,
				"crm_user": self.user,
			}
		).insert(ignore_permissions=True)
		with (
			patch(
				"crm_messenger.services.outbound.process_outbound_message", return_value={"ok": True}
			) as process,
			patch.object(frappe.db, "commit"),
		):
			work()
			self.assertEqual([c.args[0] for c in process.call_args_list], [own.name])
		frappe.set_user("Administrator")
		inbox.set_account_access("messenger", self.channel.name, self.user, 0, 0)
		with (
			patch("crm_messenger.services.outbound.process_outbound_message") as process,
			patch.object(frappe.db, "rollback"),
		):
			work()
			process.assert_not_called()

	def test_email_upload_is_private_until_send_and_bound_to_its_author(self):
		from io import BytesIO

		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from crm.permissions.inbox import file_permission

		mail = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Received",
				"sender": "client@example.invalid",
				"recipients": "team@example.invalid",
				"subject": "Upload ownership",
				"content": "Original",
				"reference_doctype": "CRM Lead",
				"reference_name": self.lead.name,
			}
		).insert(ignore_permissions=True)
		original = getattr(frappe.local, "request", None)
		self.addCleanup(lambda: setattr(frappe.local, "request", original))
		frappe.local.request = Request(
			EnvironBuilder(
				method="POST", data={"file": (BytesIO(b"private draft attachment"), self.tag + ".txt")}
			).get_environ()
		)
		with patch("crm.api.inbox.get_thread", return_value={"can_send": True}):
			file = inbox.upload_attachment("email", mail.name)
		self.assertEqual(file.attached_to_doctype, inbox.STATE)
		self.assertTrue(file.is_private)
		self.assertFalse(inbox.get_thread("email", mail.name)["messages"][0]["attachments"])
		self.assertTrue(file_permission(file, user="Administrator"))
		self.assertFalse(file_permission(file, user=self.user))
