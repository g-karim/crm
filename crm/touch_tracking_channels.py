"""Channel facts, separate from mutable delivery/recording/analysis metadata.

Receipts bind a source to one card and its origin before asynchronous sending.
Confirmed receipts are a minimal durable outbox; no message bodies or addresses.
Native direct SQL email updates are observed by cooperative DocType mixins.
Optional providers must pass a site acceptance check before activation.
"""

import hashlib
import json
from email.parser import Parser
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import cint, get_datetime, get_system_timezone, now_datetime

from crm import touch_tracking as touch

RECEIPT = "CRM Touch Receipt"
CHANNEL_RULES = {
	"message_received": "Incoming message",
	"message_sent": "Successfully sent message",
	"call_incoming_answered": "Answered incoming call",
	"call_outgoing_answered": "Answered outgoing call",
	"call_incoming_missed": "Missed incoming call",
	"call_outgoing_unsuccessful": "Unsuccessful outgoing call",
	"call_manual": "Manually logged call",
	"email_received": "Received email",
	"email_sent": "Successfully sent email",
}


def identity(*parts):
	return hashlib.sha256(json.dumps([str(p or "") for p in parts]).encode()).hexdigest()


def event_time(value):
	date = get_datetime(value)
	return date.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None) if date.tzinfo else date


def verified(adapter):
	# Populated only after per-site live acceptance; installing an app is not proof.
	return adapter == "calls:manual" or adapter in (frappe.conf.get("crm_touch_verified_adapters") or [])


def capabilities():
	apps = set(frappe.get_installed_apps())
	messenger = "crm_messenger" in apps and frappe.db.table_exists("Messenger Message")
	providers = []
	if messenger:
		providers = frappe.get_all("Messenger Channel", filters={"enabled": 1}, pluck="provider")
	message_ready = messenger_supported() and any(verified(f"messenger:{provider}") for provider in providers)
	# Provider call facts use the explicit adapter contract below, never generic Completed.
	call_ready = provider_calls_ready()
	return [
		{
			"key": "messenger",
			"label": "Messaging",
			"installed": messenger,
			"available": message_ready,
			"rules": ["message_received", "message_sent"],
			"automation": "messenger_automation",
			"description": "Only received messages and confirmed successful sends will count.",
		},
		{
			"key": "calls",
			"label": "Calls",
			"installed": True,
			"available": call_ready,
			"rules": [
				"call_incoming_answered",
				"call_outgoing_answered",
				"call_incoming_missed",
				"call_outgoing_unsuccessful",
				"call_manual",
			],
			"description": "A completed conversation must be confirmed by the phone provider.",
		},
		{
			"key": "email",
			"label": "Emails",
			"installed": True,
			"available": verified("email:frappe"),
			"rules": ["email_received", "email_sent"],
			"automation": "email_automation",
			"description": "Drafts, queued mail and failed sends will not count.",
		},
	]


def provider_calls_ready():
	# An allowlist entry without installed producer code must not unlock settings.
	for adapter, methods in frappe.get_hooks("crm_touch_call_adapters", {}).items():
		if not verified(adapter):
			continue
		for method in methods if isinstance(methods, list) else [methods]:
			try:
				if frappe.get_attr(method)():
					return True
			except Exception as exc:
				if touch._transaction_failure(exc):
					raise
	return False


def validate_channel_rules(doc, prefix, rules):
	from crm.touch_tracking_internal import selections

	previous = doc.get_doc_before_save()
	old = set(selections(previous.get(f"{prefix}_channels"))) if previous else set()
	available = {
		rule
		for channel in capabilities()
		for rule in channel["rules"]
		if channel["available"] or rule == "call_manual"
	}
	if set(rules) - set(CHANNEL_RULES):
		frappe.throw(frappe._("Unsupported channel touch rule"))
	if set(rules) - old - available:
		frappe.throw(frappe._("Channel checks are required before enabling this touch rule"))


def messenger_supported():
	if not frappe.db.table_exists("Messenger Message"):
		return False
	meta = frappe.get_meta("Messenger Message")
	return all(
		meta.has_field(field)
		for field in (
			"ingest_source",
			"last_update_source",
			"message_datetime",
			"sent_at",
			"external_message_id",
			"direction",
			"status",
			"conversation",
			"channel",
			"crm_user",
			"raw_payload",
		)
	)


def _target(doc):
	dt = doc.get("reference_doctype")
	name = doc.get("reference_name") or doc.get("reference_docname")
	if dt in touch.TARGETS and name and frappe.db.exists(dt, name):
		return dt, name
	return None


def _active(target, rules):
	from crm.touch_tracking_internal import selections

	if not target or not frappe.db.table_exists(RECEIPT):
		return False
	settings = frappe.get_cached_doc(touch.SETTINGS)
	prefix = "lead" if target[0] == "CRM Lead" else "deal"
	return touch.policy_accepts(settings, target[0], "Created") and bool(
		set(rules) & set(selections(settings.get(f"{prefix}_channels")))
	)


def _guard(action, fn):
	# Ancillary failures must not turn a successfully sent message into a failed send.
	point = "touch_channel_" + frappe.generate_hash(length=10)
	frappe.db.savepoint(point)
	try:
		return fn()
	except Exception as exc:
		if touch._transaction_failure(exc):
			raise
		frappe.db.rollback(save_point=point)
		touch._diagnose(action)


def bind(source, target, adapter, origin, actor=None, *, provider_context=None):
	key = identity(source.doctype, source.name)
	if frappe.db.exists(RECEIPT, key):
		return frappe.get_doc(RECEIPT, key)
	if not target or not verified(adapter):
		return None
	doc = frappe.get_doc(
		dict(
			doctype=RECEIPT,
			name=key,
			source_doctype=source.doctype,
			source_name=str(source.name),
			reference_doctype=target[0],
			reference_name=target[1],
			adapter=adapter,
			origin=origin,
			actor=actor,
			bound_at=now_datetime(),
			event_source_doctype="Communication" if source.doctype == "Email Queue" else source.doctype,
			event_source_name=source.communication if source.doctype == "Email Queue" else str(source.name),
		)
	)
	# Optional producer metadata is immutable and contains no raw callback/phone.
	for field in (
		"provider_started_at",
		"provider_timezone",
		"provider_agent_id",
		"provider_phone_key",
		"provider_call_key",
	):
		if provider_context and field in provider_context:
			doc.set(field, provider_context[field])
	doc.flags.touch_internal = True
	doc.insert(ignore_permissions=True)
	return doc


def confirm(receipt, rule, occurred_at, confirmation_id):
	from crm.touch_tracking_internal import selections

	if not receipt or rule not in CHANNEL_RULES or not occurred_at or not confirmation_id:
		return
	date = event_time(occurred_at)
	if date > now_datetime() or date.year < 2000:
		return
	receipt = frappe.get_doc(RECEIPT, receipt.name, for_update=True)
	if receipt.occurred_at:
		return receipt.name
	key = identity(receipt.adapter, rule, confirmation_id)
	policy = touch.policy_at(touch._policies(), date)
	prefix = "lead" if receipt.reference_doctype == "CRM Lead" else "deal"
	allowed = bool(
		policy
		and touch.policy_accepts(policy, receipt.reference_doctype, "Created")
		and rule in selections(policy.get(f"{prefix}_channels"))
	)
	if rule in ("message_sent", "email_sent"):
		if receipt.origin == "Automation":
			channel = "messenger" if rule == "message_sent" else "email"
			allowed = allowed and bool(cint(policy.get(f"{prefix}_{channel}_automation")))
		elif receipt.origin != "User":
			allowed = False  # Unknown outgoing authors are not guessed to be people/bots.
	if allowed and frappe.db.exists(RECEIPT, {"confirmation_key": key}):
		return
	receipt.update(
		dict(
			rule=rule,
			occurred_at=date,
			# An unclassified provider echo must not suppress a later confirmed CRM send.
			confirmation_key=key if allowed else None,
			policy_revision=policy.name if allowed else None,
		)
	)
	if allowed:
		receipt.change_name = touch.event_key(
			receipt.reference_doctype,
			receipt.reference_name,
			"Channel Interaction",
			receipt.event_source_doctype,
			receipt.event_source_name,
			key,
		)
	receipt.flags.touch_internal = True
	receipt.save(ignore_permissions=True)
	if allowed:
		_guard("channel event outbox", lambda: materialize(receipt))
	return receipt.name


def materialize(receipt):
	from crm.touch_tracking_internal import store_change

	if not receipt.occurred_at or not receipt.policy_revision:
		return
	# The source link is bound before dispatch, even if the queue is later purged.
	source_type, source_name = receipt.event_source_doctype, receipt.event_source_name
	return store_change(
		receipt.reference_doctype,
		receipt.reference_name,
		"Channel Interaction",
		source_type,
		source_name,
		receipt.confirmation_key,
		receipt.occurred_at,
		receipt.actor,
		frappe._dict(name=receipt.policy_revision),
		[receipt.rule],
		receipt.origin,
	)


def capture_communication(doc, method=None):
	from crm.touch_tracking_internal import operation_origin

	# Received mail is observed with parsed headers in EmailAccount's receive path.
	if doc.communication_medium != "Email" or doc.sent_or_received != "Sent":
		return
	target = _target(doc)
	if _active(target, ["email_sent"]) and verified("email:frappe"):
		return _guard(
			"email origin", lambda: bind(doc, target, "email:frappe", operation_origin(), frappe.session.user)
		)


def capture_queue(doc, method=None):
	from crm.touch_tracking_internal import operation_origin

	if not doc.communication or not frappe.db.exists("Communication", doc.communication):
		return
	communication = frappe.get_doc("Communication", doc.communication)
	target = _target(communication)
	if not _active(target, ["email_sent"]) or not verified("email:frappe"):
		return
	origin = operation_origin()
	actor = frappe.session.user
	original = identity("Communication", communication.name)
	if frappe.db.exists(RECEIPT, original):
		receipt = frappe.get_doc(RECEIPT, original)
		target = receipt.reference_doctype, receipt.reference_name
		origin, actor = receipt.origin, receipt.actor
	elif communication.sent_or_received != "Sent":
		origin = "Automation"
	headers = Parser().parsestr(doc.message or "", headersonly=True)
	if str(headers.get("Auto-Submitted") or "no").strip().lower() != "no":
		origin = "Automation"
	return _guard("email queue binding", lambda: bind(doc, target, "email:frappe", origin, actor))


def capture_email_sent(queue):
	key = identity(queue.doctype, queue.name)
	if not frappe.db.table_exists(RECEIPT) or not frappe.db.exists(RECEIPT, key):
		return
	rows = frappe.get_all(
		"Email Queue Recipient", filters={"parent": queue.name}, fields=["status", "modified"]
	)
	if not rows or any(row.status != "Sent" for row in rows) or not queue.message_id:
		return
	headers = Parser().parsestr(queue.message or "", headersonly=True)
	if headers.get_content_type() in (
		"multipart/report",
		"message/delivery-status",
		"message/disposition-notification",
	):
		return
	date = max(get_datetime(row.modified) for row in rows)
	return confirm(frappe.get_doc(RECEIPT, key), "email_sent", date, queue.message_id)


class TouchEmailQueueMixin:
	def update_status(self, status, commit=False, **kwargs):
		# Original method commits via update_db before synchronizing Communication.
		# Observe before that same commit, keeping its status/commit behavior intact.
		previous = getattr(self.flags, "touch_transport_status", None)
		self.flags.touch_transport_status = status
		try:
			return super().update_status(status, commit=commit, **kwargs)
		finally:
			self.flags.touch_transport_status = previous

	def update_db(self, commit=False, **kwargs):
		if kwargs.get("status") != "Sent" or self.flags.touch_transport_status != "Sent":
			return super().update_db(commit=commit, **kwargs)
		result = super().update_db(commit=False, **kwargs)
		_guard("confirmed email send", lambda: capture_email_sent(self))
		if commit:
			frappe.db.commit()
		return result


def service_email(headers):
	"""Classify transport notifications/automatic replies from actual MIME headers."""
	submitted = str(headers.get("Auto-Submitted") or "").strip().lower()
	return bool(
		(submitted and submitted != "no")
		or headers.get_content_type()
		in ("multipart/report", "message/delivery-status", "message/disposition-notification")
		or str(headers.get("Return-Path") or "").strip() == "<>"
	)


class _TrackedInboundMail:
	def __init__(self, mail):
		self.mail = mail

	def __getattr__(self, name):
		return getattr(self.mail, name)

	def process(self):
		communication = self.mail.process()
		if communication and self.mail.flags.is_new_communication and not service_email(self.mail.mail):
			target = _target(communication)
			if _active(target, ["email_received"]) and communication.message_id:

				def capture():
					receipt = bind(communication, target, "email:frappe", "External")
					return confirm(
						receipt,
						"email_received",
						communication.creation,
						identity(communication.email_account, communication.message_id),
					)

				_guard("received email", capture)
		return communication


class TouchEmailAccountMixin:
	def get_inbound_mails(self):
		mails = super().get_inbound_mails()
		if not verified("email:frappe") or not frappe.db.table_exists(RECEIPT):
			return mails
		return [_TrackedInboundMail(mail) for mail in mails]


def capture_message(doc, method=None):
	from crm.touch_tracking_internal import operation_origin

	adapter = f"messenger:{doc.provider}"
	if not verified(adapter) or not frappe.db.table_exists(RECEIPT) or not messenger_supported():
		return
	previous = doc.get_doc_before_save()
	key = identity(doc.doctype, doc.name)
	if not previous and not frappe.db.exists(RECEIPT, key):
		if (
			doc.ingest_source in ("provider_history", "migration", "legacy")
			or doc.is_edited
			or doc.deleted_at
		):
			return
		conversation = frappe.get_doc("Messenger Conversation", doc.conversation)
		target = _target(conversation)
		rule = "message_received" if doc.direction == "inbound" else "message_sent"
		if not _active(target, [rule]):
			return
		if doc.direction == "inbound":
			if (
				doc.ingest_source != "provider_webhook"
				or not doc.external_message_id
				or not doc.message_datetime
				or event_time(doc.message_datetime) > get_datetime(doc.creation)
			):
				return
			origin = "External"
		else:
			payload = frappe.parse_json(doc.raw_payload or "{}")
			origin = (
				operation_origin()
				if payload.get("source") == "crm_api" and doc.crm_user == frappe.session.user
				else "Unknown"
			)
		receipt = bind(doc, target, adapter, origin, doc.crm_user)
	else:
		receipt = frappe.get_doc(RECEIPT, key) if frappe.db.exists(RECEIPT, key) else None
	if not receipt or doc.last_update_source in ("provider_history", "migration", "legacy"):
		return
	if doc.direction == "inbound" and not previous and doc.status == "received":
		return confirm(
			receipt, "message_received", doc.message_datetime, identity(doc.channel, doc.external_message_id)
		)
	if (
		doc.direction == "outbound"
		and doc.sent_at
		and doc.external_message_id
		and doc.status in ("sent", "delivered", "read")
	):
		return confirm(receipt, "message_sent", doc.sent_at, identity(doc.channel, doc.external_message_id))


def on_message(doc, method=None):
	return _guard("messenger event", lambda: capture_message(doc, method))


def capture_manual_call(doc, method=None):
	from crm.touch_tracking_internal import operation_origin

	target = _target(doc)
	if (
		doc.telephony_medium != "Manual"
		or operation_origin() != "User"
		or not _active(target, ["call_manual"])
	):
		return

	def capture():
		receipt = bind(doc, target, "calls:manual", "User", frappe.session.user)
		return confirm(receipt, "call_manual", doc.creation, doc.name)

	return _guard("manual call", capture)


def capture_provider_call(
	doc, *, provider, event_id, direction, outcome, occurred_at, employee, authenticated=False
):
	"""Private server adapter. Caller must prove terminal outcome and authentication.

	outcome is answered/missed/unsuccessful from provider-specific verified semantics;
	generic Completed, recording existence and duration alone are never accepted.
	Only an explicit primary CRM link is used; secondary/phone matches are not fanned out.
	"""
	adapter = f"calls:{provider}"
	target = _target(doc)
	if not authenticated or not verified(adapter) or not event_id or not target:
		return
	if str(doc.telephony_medium or "").lower() != provider or str(doc.id) != str(event_id):
		return
	valid = {
		("incoming", "answered"),
		("outgoing", "answered"),
		("incoming", "missed"),
		("outgoing", "unsuccessful"),
	}
	if (direction, outcome) not in valid or doc.type.lower() != direction:
		return
	if (outcome == "answered" or direction == "outgoing") and (
		not employee or not frappe.db.exists("User", employee)
	):
		return
	rule = f"call_{direction}_{outcome}"
	if not _active(target, [rule]):
		return

	def capture():
		receipt = bind(doc, target, adapter, "External", employee)
		return confirm(receipt, rule, occurred_at, event_id)

	return _guard("provider call", capture)


def recover_receipts(limit=100):
	if not frappe.db.table_exists(RECEIPT):
		return
	# No native historical scans: only previously bound/confirmed source receipts.
	for row in frappe.db.sql(
		"""SELECT r.name FROM `tabCRM Touch Receipt` r
		LEFT JOIN `tabCRM Touch Change` c ON c.name=r.change_name
		WHERE r.policy_revision IS NOT NULL AND r.policy_revision != '' AND c.name IS NULL
		ORDER BY r.occurred_at,r.name LIMIT %s""",
		(cint(limit),),
		as_dict=True,
	):
		_guard("channel receipt recovery", lambda: materialize(frappe.get_doc(RECEIPT, row.name)))
	for row in frappe.db.sql(
		"""SELECT r.source_name FROM `tabCRM Touch Receipt` r
		JOIN `tabEmail Queue` q ON q.name=r.source_name AND r.source_doctype='Email Queue'
		WHERE r.occurred_at IS NULL AND q.status='Sent'
		ORDER BY r.creation,r.name LIMIT %s""",
		(cint(limit),),
		as_dict=True,
	):
		_guard(
			"email receipt recovery",
			lambda: capture_email_sent(frappe.get_doc("Email Queue", row.source_name)),
		)
	if messenger_supported():
		for row in frappe.db.sql(
			"""SELECT r.name,r.source_name FROM `tabCRM Touch Receipt` r
			JOIN `tabMessenger Message` m ON m.name=r.source_name AND r.source_doctype='Messenger Message'
			WHERE r.occurred_at IS NULL AND m.direction='outbound' AND m.sent_at IS NOT NULL
			AND m.status IN ('sent','delivered','read') AND m.external_message_id IS NOT NULL
			AND COALESCE(m.last_update_source,'') NOT IN ('provider_history','migration','legacy')
			ORDER BY r.creation,r.name LIMIT %s""",
			(cint(limit),),
			as_dict=True,
		):

			def recover_message(row=row):
				message = frappe.get_doc("Messenger Message", row.source_name)
				if get_datetime(message.sent_at) <= get_datetime(message.modified):
					return confirm(
						frappe.get_doc(RECEIPT, row.name),
						"message_sent",
						message.sent_at,
						identity(message.channel, message.external_message_id),
					)

			_guard("message receipt recovery", recover_message)
