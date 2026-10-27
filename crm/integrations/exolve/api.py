from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe import _

from .client import ExolveClient, ExolveError
from .utils import log_name, normalize_call


def is_enabled() -> bool:
	return bool(
		frappe.db.exists("DocType", "CRM Exolve Settings")
		and frappe.db.get_single_value("CRM Exolve Settings", "enabled")
	)


def _check_user():
	if frappe.session.user == "Guest" or not frappe.has_permission("CRM Call Log", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not frappe.db.get_value("User", frappe.session.user, "enabled"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _manager():
	_check_user()
	frappe.only_for(["System Manager", "Sales Manager"])


def _settings(require_enabled=True):
	if not frappe.db.exists("DocType", "CRM Exolve Settings"):
		frappe.throw(_("Exolve is not installed on this site."))
	doc = frappe.get_single("CRM Exolve Settings")
	if require_enabled and not doc.enabled:
		frappe.throw(_("Exolve calling is disabled."))
	return doc


def _client(settings):
	key = settings.get_password("api_key", raise_exception=False)
	if not key:
		frappe.throw(_("Enter the Exolve application ID and API key."))
	return ExolveClient(key)


def _read(client, operation, values):
	try:
		return client.read(operation, values)
	except ExolveError as exc:
		frappe.throw(_(str(exc)))


def _agent(settings):
	_check_user()
	agent = next((row for row in settings.agents if row.user == frappe.session.user and row.enabled), None)
	if not agent:
		frappe.throw(_("Your CRM user has no Exolve SIP account. Contact your administrator."))
	return agent


def _sip(settings, agent, client):
	data = _read(client, "sip", {"sip_resource_id": str(agent.sip_resource_id)})
	attrs = data.get("attributes") or {}
	if (
		data.get("application_uuid") != settings.application_id
		or not attrs.get("login")
		or not attrs.get("cli")
	):
		frappe.throw(
			_("The SIP account does not belong to this Exolve application or has no outgoing number.")
		)
	return data, attrs


@frappe.whitelist()
def get_settings() -> dict:
	_manager()
	s = _settings(False)
	return {
		"enabled": bool(s.enabled),
		"history_enabled": bool(s.get("history_enabled")),
		"history_start": str(s.history_start) if s.get("history_start") else "",
		"application_id": s.application_id or "",
		"api_key_configured": bool(s.get_password("api_key", raise_exception=False)),
		"agents": [
			{"user": row.user, "sip_resource_id": row.sip_resource_id, "enabled": bool(row.enabled)}
			for row in s.agents
		],
		"modified": str(s.modified),
	}


@frappe.whitelist(methods=["POST"])
def save_settings(
	application_id: str,
	agents: list | str,
	enabled: bool = False,
	api_key: str | None = None,
	expected_modified: str | None = None,
	history_enabled=None,
	history_start=None,
) -> dict:
	_manager()
	s = _settings(False)
	def connection_config(doc):
		return (bool(doc.enabled), doc.application_id, [(a.user, str(a.sip_resource_id), bool(a.enabled)) for a in doc.agents])
	previous_connection = connection_config(s)
	if expected_modified and str(s.modified) != expected_modified:
		frappe.throw(_("Settings changed. Reload before saving."), frappe.TimestampMismatchError)
	s.application_id = application_id
	if history_enabled is not None:s.history_enabled = frappe.utils.cint(history_enabled)
	if history_start is not None:s.history_start = history_start or None
	s.enabled = frappe.utils.cint(enabled)
	if api_key:
		s.api_key = api_key.strip().removeprefix("Bearer ").strip()
	rows = frappe.parse_json(agents) if isinstance(agents, str) else agents
	if not isinstance(rows, list) or len(rows) > 100:
		frappe.throw(_("Invalid Exolve agent mappings."))
	s.set("agents", [{k: row.get(k) for k in ("user", "sip_resource_id", "enabled")} for row in rows])
	s.save()
	result = get_settings()
	result["connection_changed"] = bool(api_key) or previous_connection != connection_config(s)
	return result


@frappe.whitelist(methods=["POST"])
def test_connection() -> dict:
	_manager()
	s = _settings(False)
	c = _client(s)
	sips = _read(c, "sips", {"limit": 100, "offset": 0}).get("sips", [])
	numbers = _read(c, "numbers", {"application_uuid": s.application_id, "limit": 100, "offset": 0}).get(
		"numbers", []
	)
	return {
		"sips": [
			{
				"sip_resource_id": str(r.get("sip_resource_id")),
				"username": r.get("user_name"),
				"number": r.get("cli"),
			}
			for r in sips
			if r.get("application_uuid") == s.application_id
		],
		"numbers": [r.get("number_name") for r in numbers if r.get("application_uuid") == s.application_id],
	}


@frappe.whitelist(methods=["POST"])
def get_connection_status() -> dict:
	"""Local readiness for this user only; never fetch SIP secrets or call Exolve."""
	if frappe.session.user == "Guest" or not frappe.db.get_value("User", frappe.session.user, "enabled"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not is_enabled():
		return {"available": False, "reason": "disabled"}
	if not frappe.has_permission("CRM Call Log", "create"):
		return {"available": False, "reason": "not_permitted"}
	s = _settings()
	if not any(row.user == frappe.session.user and row.enabled for row in s.agents):
		return {"available": False, "reason": "unmapped"}
	if not s.application_id or not s.get_password("api_key", raise_exception=False):
		return {"available": False, "reason": "missing_key"}
	return {"available": True, "reason": None}


@frappe.whitelist(methods=["POST"])
def get_sip_credentials() -> dict:
	_check_user()
	s = _settings()
	agent = _agent(s)
	_, attrs = _sip(s, agent, _client(s))
	frappe.local.response_headers["Cache-Control"] = "no-store"
	return {"username": attrs["login"], "password": attrs.get("password"), "number": attrs["cli"]}


@frappe.whitelist(methods=["POST"])
def sync_calls() -> dict:
	# Only this top-level RPC owns its transaction. A concurrent insert can
	# invalidate a snapshot created during request authentication (MariaDB 1020).
	for attempt in range(2):
		try:
			return _sync_calls_once()
		except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
			request = getattr(frappe.local, "request", None)
			if (
				attempt
				or not request
				or request.method != "POST"
				or frappe.form_dict.get("cmd") != "crm.integrations.exolve.api.sync_calls"
			):
				raise
			frappe.db.rollback()
			frappe.clear_cache(user=frappe.session.user)
			frappe.local.user_perms = None


def _sync_calls_once() -> dict:
	"""Reconcile this user's last 15 minutes from authenticated provider statistics.

	No guest callback, browser-reported disposition or historical scan is trusted.
	The first pilot requires no public webhook and never changes provider routes.
	"""
	_check_user()
	s = _settings()
	agent = _agent(s)
	c = _client(s)
	_, attrs = _sip(s, agent, c)
	now = datetime.now(timezone.utc)
	start = now - timedelta(minutes=15)
	rows = _read(
		c, "calls", {"date_from": start.isoformat(), "date_to": now.isoformat(), "limit": 100, "offset": 0}
	).get("calls", [])
	accepted = {}
	for row in rows:
		values = normalize_call(
			row, application_id=s.application_id, sip_username=attrs["login"], number=attrs["cli"]
		)
		if not values or not start <= values["start_time"] <= values["end_time"] <= now:
			continue
		accepted[values["id"]] = values
	# Every transaction acquires call locks in the same order.
	logs = [_save_call(accepted[name]) for name in sorted(accepted)]
	return {"logs": logs, "truncated": len(rows) == 100}


def _save_call(values, *, preserve_participant=False):
	from crm.integrations.api import get_contact_by_phone_number

	values = dict(values)
	name = values["id"]
	for field in ("start_time", "end_time"):
		values[field] = (
			values[field].astimezone(ZoneInfo(frappe.utils.get_system_timezone())).replace(tzinfo=None)
		)
	values["caller" if values["type"] == "Outgoing" else "receiver"] = frappe.session.user
	old_flag = frappe.flags.in_exolve_sync
	frappe.flags.in_exolve_sync = True
	try:
		_lock_call(name)
		# A locking read sees a row committed while we waited for another tab.
		if frappe.db.get_value("CRM Call Log", name, "name", for_update=True):
			doc = frappe.get_doc("CRM Call Log", name, for_update=True)
			if doc.telephony_medium != "Exolve" or doc.exolve_application_id != values["exolve_application_id"] or doc.exolve_call_id != values["exolve_call_id"] or doc.type != values["type"]:
				frappe.throw(_("Not permitted"), frappe.PermissionError)
			if preserve_participant:
				# Existing start/end values are immutable history. Reinterpreting
				# them after a site timezone change must not shift old calls.
				for field in ("start_time", "end_time", "from", "to"):
					values[field] = doc.get(field)
			participant = "caller" if doc.type == "Outgoing" else "receiver"
			if doc.get(participant) != frappe.session.user:
				if not preserve_participant:
					frappe.throw(_("Not permitted"), frappe.PermissionError)
				# Background reads may refresh provider facts for a historical SIP
				# mapping. They never transfer an existing employee or caller line.
				values.pop(participant, None)
				line_field = "from" if doc.type == "Outgoing" else "to"
				values[line_field] = doc.get(line_field)
			if not values["recording_url"]:
				if doc.recording_url:values.pop("exolve_recording_state",None)
				values.pop("recording_url")  # A late snapshot cannot remove a ready recording.
			if any(doc.get(key) != value for key, value in values.items()):
				doc.update(values)
				doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": "CRM Call Log", "reference_doctype": "", "reference_docname": "", **values})
			peer = values["to"] if values["type"] == "Outgoing" else values["from"]
			contact = get_contact_by_phone_number(peer)
			reference = next(
				(
					(doctype, contact.get(key))
					for key, doctype in (("lead", "CRM Lead"), ("deal", "CRM Deal"), ("name", "Contact"))
					if contact.get(key)
				),
				None,
			)
			if reference and frappe.has_permission(reference[0], "read", reference[1]):
				doc.link_with_reference_doc(*reference)
			doc.save(ignore_permissions=True)
		return {
			"name": doc.name,
			"status": doc.status,
			"duration": doc.duration,
			"recording_ready": bool(doc.recording_url),
		}
	finally:
		frappe.flags.in_exolve_sync = old_flag


def _lock_call(name):
	"""Hold reconciliation locks through commit/rollback, not just doc.save()."""
	from redis.exceptions import LockError

	if not getattr(frappe.local, "exolve_locks", None):
		frappe.local.exolve_locks = {}
	locks = frappe.local.exolve_locks
	if name in locks:
		return
	lock = frappe.cache.lock(f"exolve-call:{name}", timeout=120, blocking_timeout=15)
	if not lock.acquire():
		frappe.throw(_("Call history is being updated. Try again shortly."))
	locks[name] = lock

	def release():
		if locks.pop(name, None):
			try:
				lock.release()
			except LockError:
				pass

	frappe.db.after_commit.add(release)
	frappe.db.after_rollback.add(release)


def validate_call_log(doc):
	if frappe.flags.in_exolve_sync:
		return
	old = doc.get_doc_before_save()
	if doc.telephony_medium != "Exolve" and not (old and old.telephony_medium == "Exolve"):
		return
	protected = (
		"telephony_medium",
		"id",
		"exolve_call_id",
		"exolve_application_id",
		"from",
		"to",
		"type",
		"status",
		"duration",
		"start_time",
		"end_time",
		"recording_url",
		"exolve_recording_state",
		"caller",
		"receiver",
	)
	if doc.is_new() or any(doc.has_value_changed(field) for field in protected):
		frappe.throw(
			_("Exolve call details are updated only from provider statistics."), frappe.PermissionError
		)


def check_recording_access(log):
	log.check_permission("read")
	_check_user()
	s = _settings()
	_agent(s)
	if log.caller != frappe.session.user and log.receiver != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	call_id = str(log.exolve_call_id or "")
	if log.exolve_application_id != s.application_id or log.name != log_name(s.application_id, call_id):
		frappe.throw(_("Invalid Exolve call identifier."), frappe.PermissionError)
	return s, call_id


def fetch_recording(log, range_header=None):
	s, call_id = check_recording_access(log)
	try:
		return _client(s).recording(call_id, range_header)
	except ExolveError as exc:
		frappe.throw(_(str(exc)))
