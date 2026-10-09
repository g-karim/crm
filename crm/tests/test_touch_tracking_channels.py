import json
import unittest
from datetime import timedelta
from email.parser import Parser
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.utils import get_datetime, now_datetime

from crm import touch_tracking as touch
from crm import touch_tracking_channels as channels
from crm.tests import test_touch_tracking as base_cases


class TestChannelHeaders(unittest.TestCase):
	def test_service_mail_uses_headers_not_address_guesses(self):
		for headers in (
			"Auto-Submitted: auto-replied",
			"Content-Type: multipart/report; report-type=delivery-status",
			"Return-Path: <>",
		):
			self.assertTrue(channels.service_email(Parser().parsestr(headers + "\n\nbody")))
		for headers in ("Auto-Submitted: no", "From: noreply@example.invalid", "Subject: delivery status"):
			self.assertFalse(channels.service_email(Parser().parsestr(headers + "\n\nbody")))


class TestChannelTouchTracking(unittest.TestCase):
	create = base_cases.TestTouchTrackingDatabase.create
	events = base_cases.TestTouchTrackingDatabase.events
	tearDown = base_cases.TestTouchTrackingDatabase.tearDown

	def setUp(self):
		base_cases.TestTouchTrackingDatabase.setUp(self)
		self.origin = patch("crm.touch_tracking_internal.operation_origin", return_value="User")
		self.origin.start()
		self.addCleanup(self.origin.stop)
		self.old_adapters = frappe.conf.get("crm_touch_verified_adapters")
		frappe.conf.crm_touch_verified_adapters = ["email:frappe", "messenger:telegram_bot", "calls:twilio"]
		self.addCleanup(lambda: frappe.conf.update(crm_touch_verified_adapters=self.old_adapters))
		# These tests exercise the normalized contract with a controlled producer.
		ready = patch.object(
			channels, "provider_calls_ready", side_effect=lambda: channels.verified("calls:twilio")
		)
		ready.start()
		self.addCleanup(ready.stop)
		# Isolated fixture, no external credentials or network requests.
		self.channel = frappe.get_doc(
			dict(
				doctype="Messenger Channel",
				provider="telegram_bot",
				platform="telegram",
				provider_channel_id="stage5",
				state="connected",
				enabled=1,
			)
		).insert()
		self.settings.lead_channels = json.dumps(list(channels.CHANNEL_RULES))
		self.settings.deal_channels = json.dumps(list(channels.CHANNEL_RULES))
		self.settings.save()

	def conversation(self, parent):
		return frappe.get_doc(
			dict(
				doctype="Messenger Conversation",
				provider="telegram_bot",
				channel=self.channel.name,
				provider_chat_key=frappe.generate_hash(length=32),
				reference_doctype=parent.doctype,
				reference_name=parent.name,
			)
		).insert()

	def message(self, parent, *, inbound=False, **values):
		conversation = self.conversation(parent)
		return frappe.get_doc(
			dict(
				doctype="Messenger Message",
				provider="telegram_bot",
				channel=self.channel.name,
				conversation=conversation.name,
				provider_message_key=frappe.generate_hash(length=32),
				direction="inbound" if inbound else "outbound",
				status="received" if inbound else "queued",
				crm_user=frappe.session.user if not inbound else None,
				message_datetime=now_datetime(),
				raw_payload='{"source":"crm_api"}' if not inbound else "{}",
				ingest_source="provider_webhook" if inbound else None,
				**values,
			)
		).insert()

	def send(self, message, native_id="sent-1"):
		from crm_messenger.services.crm_linker import mark_outbound_first_sent

		message.external_message_id = native_id
		mark_outbound_first_sent(
			message, frappe.get_doc("Messenger Conversation", message.conversation), now_datetime()
		)
		message.save()

	def flush(self):
		touch.maintenance()

	def last_reason(self, parent):
		return json.loads(self.events(parent)[-1].reasons)

	def test_channels_are_rejected_until_site_acceptance(self):
		frappe.conf.crm_touch_verified_adapters = []
		self.settings.lead_channels = json.dumps(["email_received", "message_received"])
		# Existing choices can still be removed when a provider becomes unavailable.
		self.settings.save()
		self.settings.lead_channels = "[]"
		self.settings.save()
		self.settings.lead_channels = '["email_received"]'
		with self.assertRaises(frappe.ValidationError):
			self.settings.save()

	def test_inbound_repeat_edit_read_and_relink_are_one_event(self):
		parent, other = self.create(), self.create("CRM Deal")
		message = self.message(parent, inbound=True, external_message_id="incoming-1")
		self.flush()
		date = frappe.db.get_value(parent.doctype, parent.name, touch.FIELD)
		message.text = "edited content must not enter audit"
		message.is_edited = 1
		message.save()
		conversation = frappe.get_doc("Messenger Conversation", message.conversation)
		conversation.reference_doctype, conversation.reference_name = other.doctype, other.name
		conversation.save()
		channels.on_message(message)
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(len(self.events(other)), 1)
		self.assertEqual(frappe.db.get_value(parent.doctype, parent.name, touch.FIELD), date)
		self.assertEqual(self.last_reason(parent), ["message_received"])

	def test_history_and_future_inbound_messages_do_not_touch(self):
		parent = self.create()
		for source, date in (
			("provider_history", now_datetime()),
			("migration", now_datetime()),
			("legacy", now_datetime()),
			("provider_webhook", now_datetime() + timedelta(days=3)),
		):
			conversation = self.conversation(parent)
			frappe.get_doc(
				dict(
					doctype="Messenger Message",
					provider="telegram_bot",
					channel=self.channel.name,
					conversation=conversation.name,
					provider_message_key=frappe.generate_hash(length=32),
					direction="inbound",
					status="received",
					external_message_id=source,
					ingest_source=source,
					message_datetime=date,
				)
			).insert()
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)

	def test_outgoing_counts_confirmation_not_queue_or_failure(self):
		parent = self.create()
		message = self.message(parent)
		message.status = "failed"
		message.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		self.send(message)
		self.flush()
		first_date = frappe.db.get_value(parent.doctype, parent.name, touch.FIELD)
		for status in ("delivered", "read"):
			message.status = status
			message.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(frappe.db.get_value(parent.doctype, parent.name, touch.FIELD), first_date)
		self.assertEqual(self.last_reason(parent), ["message_sent"])

	def test_outgoing_binding_does_not_move_with_conversation(self):
		parent, other = self.create(), self.create()
		message = self.message(parent)
		conversation = frappe.get_doc("Messenger Conversation", message.conversation)
		conversation.reference_name = other.name
		conversation.save()
		self.send(message)
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(len(self.events(other)), 1)

	def test_automation_permission_is_independent_for_channels_and_types(self):
		parent, deal = self.create(), self.create("CRM Deal")
		self.settings.deal_messenger_automation = 1
		self.settings.save()
		with patch("crm.touch_tracking_internal.operation_origin", return_value="Automation"):
			first, second = self.message(parent), self.message(deal)
		self.send(first, "auto-lead")
		self.send(second, "auto-deal")
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		self.assertEqual(len(self.events(deal)), 2)

	def test_native_duplicate_message_id_only_one_touch(self):
		parent = self.create()
		for _ in range(2):
			self.message(parent, inbound=True, external_message_id="same-external-id")
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)

	def test_recover_missing_change_from_confirmed_receipt_even_after_disable(self):
		parent = self.create()
		with patch.object(
			channels, "materialize", side_effect=RuntimeError("outbox write temporarily unavailable")
		):
			self.message(parent, inbound=True, external_message_id="recover")
		self.settings.enabled = 0
		self.settings.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)

	def communication(self, parent):
		return frappe.get_doc(
			dict(
				doctype="Communication",
				communication_medium="Email",
				communication_type="Communication",
				sent_or_received="Sent",
				sender="employee@example.invalid",
				recipients="client@example.invalid",
				subject="Stage5",
				reference_doctype=parent.doctype,
				reference_name=parent.name,
			)
		).insert()

	def queue(self, parent):
		communication = self.communication(parent)
		return frappe.get_doc(
			dict(
				doctype="Email Queue",
				communication=communication.name,
				message_id=f"{frappe.generate_hash(length=32)}@example.invalid",
				sender="employee@example.invalid",
				message="From: employee@example.invalid\nTo: client@example.invalid\nSubject: Stage5\n\nbody",
				recipients=[{"recipient": "client@example.invalid", "status": "Not Sent"}],
				status="Not Sent",
			)
		).insert()

	def transport_send(self, queue, *, fail=False):
		smtp = SimpleNamespace(
			session=SimpleNamespace(
				has_extn=lambda _: False,
				sendmail=Mock(side_effect=RuntimeError("transport refused") if fail else None),
			)
		)
		account = frappe._dict(service="SMTP")
		with (
			patch.object(queue, "get_email_account", return_value=account),
			patch("frappe.db.commit"),
			patch.dict(frappe.flags, testing_email=True),
		):
			if fail:
				with self.assertRaises(RuntimeError):
					queue.send(force_send=True, smtp_server_instance=smtp)
			else:
				queue.send(force_send=True, smtp_server_instance=smtp)
		return smtp.session.sendmail

	def test_real_email_transport_path_and_redaction_only_touch_once(self):
		parent = self.create()
		queue = self.queue(parent)
		self.transport_send(queue, fail=True)
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		queue.reload()
		self.assertEqual(self.transport_send(queue).call_count, 1)
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.last_reason(parent), ["email_sent"])
		date = frappe.db.get_value(parent.doctype, parent.name, touch.FIELD)
		with patch("frappe.db.commit"):
			if hasattr(queue, "redact_message"):
				queue.redact_message()
			else:
				# Frappe 16.25 has no redaction method; a service body edit must
				# also leave the already confirmed interaction unchanged.
				queue.db_set("message", "[service edit]")
			queue.update_status("Sent")
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(frappe.db.get_value(parent.doctype, parent.name, touch.FIELD), date)

	def test_communication_sent_and_direct_queue_status_are_not_confirmation(self):
		parent = self.create()
		queue = self.queue(parent)
		frappe.db.set_value("Email Queue", queue.name, "status", "Sent")
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)

	def test_email_first_success_proof_survives_recovery_and_policy_disable(self):
		parent = self.create()
		queue = self.queue(parent)
		with patch.object(
			channels, "capture_email_sent", side_effect=RuntimeError("temporary event observer failure")
		):
			self.transport_send(queue)
		self.settings.enabled = 0
		self.settings.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)

	def test_manual_call_uses_creation_and_ignores_old_date_recording_and_ai(self):
		parent = self.create()
		call = frappe.get_doc(
			dict(
				doctype="CRM Call Log",
				telephony_medium="Manual",
				type="Outgoing",
				status="Completed",
				**{"from": "+70000000001"},
				to="+70000000000",
				reference_doctype=parent.doctype,
				reference_docname=parent.name,
				start_time=now_datetime() - timedelta(days=20),
			)
		).insert()
		self.flush()
		self.assertEqual(self.events(parent)[-1].occurred_at, get_datetime(call.creation))
		call.start_time = now_datetime() - timedelta(days=5)
		call.recording_url = "/private/files/fixture.mp3"
		call.ai_analysis_status = "Completed"
		call.save()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)

	def test_provider_requires_explicit_final_fact_employee_authentication_and_primary_link(self):
		parent, other = self.create(), self.create()
		call = frappe.get_doc(
			dict(
				doctype="CRM Call Log",
				id="provider-1",
				telephony_medium="Twilio",
				type="Incoming",
				status="Completed",
				**{"from": "+70000000001"},
				to="+70000000000",
				reference_doctype=parent.doctype,
				reference_docname=parent.name,
				links=[{"link_doctype": other.doctype, "link_name": other.name}],
			)
		).insert()
		proof = dict(
			provider="twilio",
			event_id=call.id,
			direction="incoming",
			outcome="answered",
			occurred_at=now_datetime(),
			employee="Administrator",
		)
		channels.capture_provider_call(call, **proof)
		channels.capture_provider_call(call, **{**proof, "authenticated": True, "employee": None})
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		channels.capture_provider_call(call, **proof, authenticated=True)
		channels.capture_provider_call(call, **proof, authenticated=True)
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(len(self.events(other)), 1)

	def test_minimal_audit_contains_no_message_body_or_email_addresses(self):
		parent = self.create()
		message = self.message(
			parent, inbound=True, external_message_id="minimal", text="Private stage 5 client message"
		)
		self.transport_send(self.queue(parent))
		self.flush()
		for dt in (touch.EVENT, "CRM Touch Change", channels.RECEIPT):
			data = frappe.as_json(frappe.get_all(dt, fields=["*"]))
			self.assertNotIn("client@example.invalid", data)
			self.assertNotIn("Private stage 5 client message", data)
			self.assertNotIn("raw_payload", data)
		self.assertTrue(message.name)

	def inbound_mail(self, parent, headers="", message_id="inbound-fixture"):
		from frappe.email.receive import InboundMail

		account = frappe.get_doc(
			dict(
				doctype="Email Account",
				email_account_name="Stage 5 Inbox",
				email_id="inbox@example.invalid",
				enable_incoming=0,
				enable_outgoing=0,
			)
		).insert()
		raw = f"From: Client <client@example.invalid>\nTo: inbox@example.invalid\nSubject: Stage5 inbound\nMessage-ID: <{message_id}@example.invalid>\nDate: Tue, 1 Jan 2030 12:00:00 +0000\n{headers}\nbody"
		mail = InboundMail(raw, account)
		mail._reference_document = parent
		return account, mail

	def test_real_inbound_mail_path_uses_receive_time_and_deduplicates_uid_updates(self):
		from frappe.email.doctype.email_account.email_account import EmailAccount

		parent = self.create()
		account, mail = self.inbound_mail(parent)
		with patch.object(EmailAccount, "get_inbound_mails", return_value=[mail]):
			wrapped = account.get_inbound_mails()[0]
			communication = wrapped.process()
			wrapped.process()
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.events(parent)[-1].occurred_at, get_datetime(communication.creation))
		self.assertEqual(self.last_reason(parent), ["email_received"])

	def test_real_inbound_transport_notifications_do_not_touch(self):
		from frappe.email.doctype.email_account.email_account import EmailAccount

		parent = self.create()
		account, mail = self.inbound_mail(parent, "Auto-Submitted: auto-replied\n")
		with patch.object(EmailAccount, "get_inbound_mails", return_value=[mail]):
			account.get_inbound_mails()[0].process()
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)

	def test_unknown_outgoing_author_is_excluded_even_when_automation_allowed(self):
		parent = self.create()
		self.settings.lead_messenger_automation = 1
		self.settings.save()
		conversation = self.conversation(parent)
		message = frappe.get_doc(
			dict(
				doctype="Messenger Message",
				provider="telegram_bot",
				channel=self.channel.name,
				conversation=conversation.name,
				provider_message_key=frappe.generate_hash(length=32),
				direction="outbound",
				status="sent",
				external_message_id="unknown-author",
				sent_at=now_datetime(),
				message_datetime=now_datetime(),
				ingest_source="provider_webhook",
			)
		).insert()
		self.flush()
		self.assertEqual(len(self.events(parent)), 1)
		self.assertEqual(
			frappe.get_doc(channels.RECEIPT, channels.identity(message.doctype, message.name)).origin,
			"Unknown",
		)

	def test_all_terminal_call_rules_are_independent_and_no_generic_completed_mapping(self):
		for direction, outcome in (
			("incoming", "answered"),
			("outgoing", "answered"),
			("incoming", "missed"),
			("outgoing", "unsuccessful"),
		):
			parent = self.create()
			date = now_datetime()
			call = frappe.get_doc(
				dict(
					doctype="CRM Call Log",
					id=frappe.generate_hash(length=24),
					telephony_medium="Twilio",
					type=direction.title(),
					status="Completed",
					**{"from": "+70000000001"},
					to="+70000000000",
					reference_doctype=parent.doctype,
					reference_docname=parent.name,
				)
			).insert()
			proof = dict(
				provider="twilio",
				event_id=call.id,
				direction=direction,
				occurred_at=date,
				employee="Administrator",
				authenticated=True,
			)
			channels.capture_provider_call(call, outcome="Completed", **proof)
			self.flush()
			self.assertEqual(len(self.events(parent)), 1)
			channels.capture_provider_call(call, outcome=outcome, **proof)
			self.flush()
			self.assertEqual(self.last_reason(parent), [f"call_{direction}_{outcome}"])

	def test_old_confirmed_message_cannot_regress_date(self):
		parent = self.create()
		date = get_datetime(parent.creation)
		conversation = self.conversation(parent)
		frappe.get_doc(
			dict(
				doctype="Messenger Message",
				provider="telegram_bot",
				channel=self.channel.name,
				conversation=conversation.name,
				provider_message_key=frappe.generate_hash(length=32),
				direction="inbound",
				status="received",
				external_message_id="late-message",
				ingest_source="provider_webhook",
				message_datetime=date - timedelta(microseconds=1),
			)
		).insert()
		self.flush()
		self.assertEqual(frappe.db.get_value(parent.doctype, parent.name, touch.FIELD), date)

	def test_event_time_converts_offsets_to_site_timezone(self):
		from datetime import timezone
		from zoneinfo import ZoneInfo

		from frappe.utils import get_system_timezone

		date = now_datetime()
		aware = date.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(timezone.utc)
		self.assertEqual(channels.event_time(aware.isoformat()), date)

	def test_unknown_echo_does_not_claim_identity_before_known_user_send(self):
		parent = self.create()
		conversation = self.conversation(parent)
		frappe.get_doc(
			dict(
				doctype="Messenger Message",
				provider="telegram_bot",
				channel=self.channel.name,
				conversation=conversation.name,
				provider_message_key=frappe.generate_hash(length=32),
				direction="outbound",
				status="sent",
				external_message_id="echo-first",
				sent_at=now_datetime(),
				message_datetime=now_datetime(),
				ingest_source="provider_webhook",
			)
		).insert()
		message = self.message(parent)
		self.send(message, "echo-first")
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.last_reason(parent), ["message_sent"])

	def test_confirmed_message_recovery_uses_original_binding_and_policy(self):
		parent = self.create()
		message = self.message(parent)
		with patch.object(
			channels, "capture_message", side_effect=RuntimeError("temporary event observer failure")
		):
			self.send(message, "recover-send")
		self.settings.enabled = 0
		self.settings.save()
		frappe.conf.crm_touch_verified_adapters = []
		self.flush()
		self.assertEqual(len(self.events(parent)), 2)
		self.assertEqual(self.last_reason(parent), ["message_sent"])
