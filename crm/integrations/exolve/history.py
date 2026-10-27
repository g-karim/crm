"""Bounded, resumable server polling. Never places calls or changes provider routes."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, getdate, now_datetime

from crm.call_work_storage import internal_write

from . import api
from .utils import normalize_call, parse_timestamp

DOCTYPE = "CRM Exolve History Sync"
PAGE_SIZE = 100
MAX_PAGES = 8


def _utc(value):
	return parse_timestamp(value)


def _start(settings, now):
	if settings.history_start:
		return datetime.combine(
			getdate(settings.history_start),
			datetime.min.time(),
			tzinfo=ZoneInfo(frappe.utils.get_system_timezone()),
		).astimezone(timezone.utc)
	return now - timedelta(days=30)


def _new_lane(start, end):
	return {"start": start.isoformat(), "end": end.isoformat(), "offset": 0}


def _write(doc):
	with internal_write():
		doc.save(ignore_permissions=True)


def _scan(doc, state, lane, client, settings, attrs, until, pages):
	position = state[lane]
	for page in range(pages):
		start, end = _utc(position["start"]), _utc(position["end"])
		if start >= until:
			return 0
		response = client.read(
			"calls",
			{
				"date_from": start.isoformat(),
				"date_to": end.isoformat(),
				"limit": PAGE_SIZE,
				"offset": position["offset"],
			},
		)
		if not isinstance(response, dict) or (response and "calls" not in response):
			raise RuntimeError("Invalid history response")
		rows = response.get("calls", [])
		if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
			raise RuntimeError("Invalid history response")
		accepted = {}
		for row in rows:
			if not isinstance(row, dict):
				raise RuntimeError("Invalid history response")
			values = normalize_call(
				row, application_id=settings.application_id, sip_username=attrs["login"], number=attrs["cli"]
			)
			if values and start <= values["start_time"] <= values["end_time"] <= until:
				accepted[values["id"]] = values
		for name in sorted(accepted):
			api._save_call(accepted[name], preserve_participant=True)
		if len(rows) == PAGE_SIZE:
			position["offset"] += len(rows)
		else:
			# One-day historical partitions keep recovery bounded. Recent scans
			# overlap two days; completed historical sweeps repeat once a day.
			if lane == "recent":
				state["recent_complete"] = end.isoformat()
				state[lane] = None
			else:
				state["cursor"] = end.isoformat()
				state[lane] = None
		doc.state = frappe.as_json(state)
		doc.last_success_at = now_datetime()
		doc.failures = 0
		doc.last_error = ""
		doc.next_retry_at = None
		_write(doc)
		frappe.db.commit()
		if state[lane] is None:
			return page + 1
	return pages


def sync_agent(settings, agent, now=None):
	"""Owns its background transactions; call only outside a business RPC."""
	now = now or datetime.now(timezone.utc)
	key = sha256(f"{settings.application_id}:{agent.sip_resource_id}:{agent.user}".encode()).hexdigest()
	with frappe.cache.lock(f"exolve-history:{key}", timeout=600, blocking_timeout=1):
		previous_user = frappe.session.user
		try:
			frappe.set_user(agent.user)
			api._check_user()
			fresh = api._settings()
			if not fresh.history_enabled or fresh.application_id != settings.application_id:
				return
			if not any(
				a.user == agent.user and a.enabled and a.sip_resource_id == agent.sip_resource_id
				for a in fresh.agents
			):
				return
			settings = fresh
			doc = (
				frappe.get_doc(DOCTYPE, key)
				if frappe.db.exists(DOCTYPE, key)
				else frappe.get_doc(
					{
						"doctype": DOCTYPE,
						"name": key,
						"__islocal": 1,
						"application_id": settings.application_id,
						"sip_resource_id": agent.sip_resource_id,
						"user": agent.user,
						"failures": 0,
					}
				)
			)
			if doc.next_retry_at and get_datetime(doc.next_retry_at) > now_datetime():
				return
			client = api._client(settings)
			_, attrs = api._sip(settings, agent, client)
			start = _start(settings, now)
			until = now - timedelta(seconds=30)
			if start >= until:
				return
			state = (
				frappe.parse_json(doc.state)
				if doc.state
				else {
					"cursor": start.isoformat(),
					"recent": None,
					"history": None,
					"origin": start.isoformat(),
					"sweep_at": now.isoformat(),
					"start_setting": str(settings.history_start or ""),
				}
			)
			if state.get("identity") and state["identity"] != {
				"username": attrs["login"],
				"line": attrs["cli"],
			}:
				raise RuntimeError("SIP identity changed")
			state["identity"] = {"username": attrs["login"], "line": attrs["cli"]}
			if state.get("start_setting") != str(settings.history_start or ""):
				state.update(
					{
						"cursor": start.isoformat(),
						"origin": start.isoformat(),
						"sweep_at": now.isoformat(),
						"start_setting": str(settings.history_start or ""),
						"history": None,
						"recent": None,
					}
				)
			start = _utc(state["origin"])
			if not state.get("recent"):
				state["recent"] = _new_lane(max(start, until - timedelta(days=2)), until)
			_scan(doc, state, "recent", client, settings, attrs, until, MAX_PAGES)
			budget = MAX_PAGES
			while budget > 0:
				if not state.get("history"):
					cursor = _utc(state["cursor"])
					if cursor >= until:
						if state.get("sweep_at") and now - _utc(state["sweep_at"]) < timedelta(days=1):
							return
						cursor = start
						state["sweep_at"] = now.isoformat()
					state["history"] = _new_lane(cursor, min(cursor + timedelta(days=1), until))
				used = _scan(doc, state, "history", client, settings, attrs, until, budget)
				budget -= max(1, used)
				if state.get("history"):
					break
		except Exception:
			frappe.db.rollback()
			# No provider bodies, URLs, credentials or customer numbers in job logs.
			if "doc" in locals():
				if frappe.db.exists(DOCTYPE, key):
					doc = frappe.get_doc(DOCTYPE, key)
				doc.failures = (doc.failures or 0) + 1
				doc.last_error = "Call history could not be synchronized. Check the Exolve connection."
				doc.next_retry_at = now_datetime() + timedelta(
					seconds=min(3600, 60 * 2 ** min(doc.failures - 1, 6))
				)
				_write(doc)
				frappe.db.commit()
			else:
				raise
		finally:
			frappe.set_user(previous_user)


def run():
	if not frappe.db.table_exists(DOCTYPE) or not api.is_enabled():
		return
	settings = api._settings()
	if not settings.history_enabled:
		return
	for agent in settings.agents:
		if agent.enabled and frappe.db.get_value("User", agent.user, "enabled"):
			try:
				sync_agent(settings, agent)
			except Exception:
				frappe.db.rollback()  # One account never blocks another account's recovery.


@frappe.whitelist()
def status():
	api._check_user()
	s = api._settings()
	agent = api._agent(s)
	key = sha256(f"{s.application_id}:{agent.sip_resource_id}:{agent.user}".encode()).hexdigest()
	row = frappe.db.get_value(
		DOCTYPE, key, ["last_success_at", "next_retry_at", "last_error", "state"], as_dict=True
	)
	state = frappe.parse_json(row.state) if row and row.state else {}
	catching_up = bool(
		state.get("recent")
		or state.get("history")
		or (state.get("recent_complete") and _utc(state["cursor"]) < _utc(state["recent_complete"]))
	)
	return {
		"catching_up": catching_up,
		"enabled": bool(s.history_enabled),
		"last_success": row.last_success_at if row else None,
		"error": row.last_error if row else None,
	}
