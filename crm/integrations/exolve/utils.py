from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


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
	elif direction == "inbound" and service == "sip_redirect":
		if not any(str(leg.get("to")) == sip_username for leg in legs):
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
		talk_time = max((float(leg.get("talk_time") or 0) for leg in legs), default=0)
	except (ValueError, TypeError, KeyError, OverflowError):
		return None
	if end < start or talk_time < 0 or talk_time > (end - start).total_seconds() + 2:
		return None
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
		"exolve_recording_state": "ready" if call.get("voice_record_exist") else "pending" if call.get("record_call") and status == "Completed" else "unavailable",
		"recording_url": f"https://api.exolve.ru/statistics/download/{call_id}"
		if call.get("voice_record_exist")
		else "",
	}
