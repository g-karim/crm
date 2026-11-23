from __future__ import annotations

import hashlib
from math import isfinite
import re
from datetime import datetime, timedelta, timezone


def normalize_phone(value: str) -> str:
	value = str(value or "").strip()
	if not re.fullmatch(r"\+?[\d\s().-]+", value):
		raise ValueError("Enter a valid phone number.")
	digits = re.sub(r"\D", "", value)
	if len(digits) == 11 and digits.startswith("8"):
		digits = "7" + digits[1:]
	if not 7 <= len(digits) <= 15:
		raise ValueError("Enter a valid phone number.")
	return digits


def parse_timestamp(value: str) -> datetime:
	parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	if parsed.tzinfo is None:
		raise ValueError("Exolve returned a timestamp without a timezone.")
	return parsed.astimezone(timezone.utc)


def log_name(application_id: str, call_id: str) -> str:
	return "exolve-" + hashlib.sha256(f"{application_id}:{call_id}".encode()).hexdigest()[:40]


def _connection_time(leg, talk_time, start, end):
	try:
		leg_start = parse_timestamp(leg["start_time"])
		leg_end = parse_timestamp(leg["end_time"])
		setup = float(leg["setup_time"])
		connected = leg_start + timedelta(seconds=setup)
	except (KeyError, TypeError, ValueError, OverflowError):
		return None
	if start <= leg_start <= connected < leg_end <= end and talk_time <= (leg_end - connected).total_seconds() + 2:
		return connected
	return None


def normalize_call(call: dict, *, application_id: str, sip_username: str, number: str) -> dict | None:
	"""Accept only terminal calls proven to belong to this exact SIP account.

	Statistics durations are seconds; webhook durations are not used here. IDs
	remain decimal strings all the way to the browser (Exolve uses uint64).
	"""
	if call.get("application_uuid") != application_id:
		return None
	call_id = str(call.get("call_id") or "")
	if not call_id.isdecimal() or len(call_id) > 20 or int(call_id) > 2**64 - 1:
		return None
	direction = str(call.get("direction", "")).lower()
	service = str(call.get("service", "")).lower()
	legs = call.get("legs") or []
	if direction == "outbound" and service == "sip" and str(call.get("from")) == sip_username:
		kind, peer = "Outgoing", call.get("to")
		legs = [leg for leg in legs if str(leg.get("to")) == str(peer)]
	elif direction == "inbound" and service == "sip_redirect":
		legs = [leg for leg in legs if str(leg.get("to")) == sip_username]
		if not legs:
			return None
		kind, peer = "Incoming", call.get("from")
	else:
		return None
	statuses = {
		"answered": "Completed",
		"busy": "Busy",
		"no_answer": "No Answer",
		"canceled": "Canceled",
		"rejected": "Failed",
		"error": "Failed",
	}
	status = statuses.get(str(call.get("status", "")).lower())
	if not status or not call.get("end_time"):
		return None
	try:
		start, end = parse_timestamp(call["start_time"]), parse_timestamp(call["end_time"])
		peer = normalize_phone(peer)
		answered = [(leg, float(leg.get("talk_time") or 0)) for leg in legs
			if status == "Completed" and str(leg.get("status") or "answered").lower() == "answered"]
		talk_time = max((seconds for _leg, seconds in answered), default=0)
	except (ValueError, TypeError, KeyError, OverflowError):
		return None
	if end < start or any(not isfinite(seconds) or not 0 <= seconds <= (end - start).total_seconds() + 2
		for _leg, seconds in answered):
		return None
	connections = [_connection_time(leg, seconds, start, end) for leg, seconds in answered
		if seconds > 0 and str(leg.get("status") or "").lower() == "answered"]
	return {
		"id": log_name(application_id, call_id),
		"exolve_call_id": call_id,
		"exolve_application_id": application_id,
		"telephony_medium": "Exolve",
		"type": kind,
		"from": number if kind == "Outgoing" else peer,
		"to": peer if kind == "Outgoing" else number,
		"status": status,
		"duration": talk_time if status == "Completed" else 0,
		"start_time": start,
		"end_time": end,
		"analytics_connected_at": min((value for value in connections if value is not None), default=None),
		"exolve_recording_state": "ready" if call.get("voice_record_exist") else "pending" if call.get("record_call") and status == "Completed" else "unavailable",
		"recording_url": f"https://api.exolve.ru/statistics/download/{call_id}"
		if call.get("voice_record_exist")
		else "",
	}
