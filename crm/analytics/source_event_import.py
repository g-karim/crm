"""Explicit source-event metadata for native CRM Deal Data Import updates.

Ordinary imports remain current-state corrections. An event-marked row must
identify a source event and be newer than the last accepted CRM history fact.
The native Deal document remains the only business record being changed.
"""

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from hashlib import sha256

import frappe
from frappe.utils import get_datetime


_event = ContextVar("crm_analytics_source_event", default=None)
_EVENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")


@dataclass(frozen=True)
class SourceEvent:
	source: str
	record_id: str
	event_id: str
	occurred_at: datetime  # naive local time in the site's configured zone
	occurred_at_utc: datetime  # aware UTC instant; survives repeated local DST hours

	def payload(self):
		return {"source": self.source, "record_id": self.record_id,
			"event_id": self.event_id, "occurred_at": self.occurred_at.isoformat(),
			"occurred_at_utc": self.occurred_at_utc.isoformat()}

	def key(self):
		return source_event_key(self.source, self.record_id, self.event_id)


def source_event_key(source, record_id, event_id):
	return sha256(json.dumps([source, record_id, event_id],
		ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def utc_now():
	return datetime.now(timezone.utc)


def parse_event(source, record_id, event_id, occurred_at):
	if not isinstance(source, str) or not source.strip() or not isinstance(record_id, str) or not record_id.strip():
		frappe.throw(frappe._("Source-event imports require an external source and record ID."), frappe.ValidationError)
	if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id.strip()):
		frappe.throw(frappe._("Source event ID must be stable and contain 1–120 safe characters."), frappe.ValidationError)
	try:
		stamp = datetime.fromisoformat(str(occurred_at).strip().replace("Z", "+00:00"))
		if stamp.tzinfo is None:
			raise ValueError("timezone required")
		zone_name = frappe.db.get_single_value("System Settings", "time_zone")
		if not zone_name:
			frappe.throw(frappe._("Configure the site time zone before importing timed source events."), frappe.ValidationError)
		zone = ZoneInfo(zone_name)
		instant = stamp.astimezone(timezone.utc)
		local = stamp.astimezone(zone).replace(tzinfo=None)
	except ZoneInfoNotFoundError:
		frappe.throw(frappe._("The configured site time zone is invalid."), frappe.ValidationError)
	except (TypeError, ValueError):
		frappe.throw(frappe._("Source event time must be ISO 8601 with an explicit UTC offset."), frappe.ValidationError)
	if instant > utc_now():
		frappe.throw(frappe._("Source event time cannot be in the future."), frappe.ValidationError)
	return SourceEvent(source.strip(), record_id.strip(), event_id.strip(), local, instant)


def event_instant(row):
	"""Recover a fact's absolute time or reject an ambiguous legacy wall time."""
	payload = json.loads(row.payload)
	origin = payload.get("source_event") or {}
	absolute = origin.get("occurred_at_utc") or payload.get("occurred_at_utc")
	if absolute:
		try:
			instant = datetime.fromisoformat(absolute)
			if instant.tzinfo is not None:
				return instant.astimezone(timezone.utc)
		except (TypeError, ValueError):
			pass
		frappe.throw(frappe._("The previous source event has an invalid absolute time."), frappe.ValidationError)
	zone_name = payload.get("timezone") or frappe.db.get_single_value("System Settings", "time_zone")
	if not zone_name:
		frappe.throw(frappe._("The previous CRM event has no known time zone."), frappe.ValidationError)
	try:
		zone = ZoneInfo(zone_name)
	except ZoneInfoNotFoundError:
		frappe.throw(frappe._("The previous CRM event has an invalid time zone."), frappe.ValidationError)
	local = get_datetime(row.occurred_at)
	first = local.replace(tzinfo=zone, fold=0)
	second = local.replace(tzinfo=zone, fold=1)
	if first.utcoffset() != second.utcoffset():
		frappe.throw(frappe._("The previous CRM event has an ambiguous local time; review its source."), frappe.ValidationError)
	return first.astimezone(timezone.utc)


@contextmanager
def source_event_scope(event):
	token = _event.set(event)
	try:
		yield
	finally:
		_event.reset(token)


def current_source_event():
	return _event.get()


def check_event_order(deal_name, event, *, allow_exact_replay=False):
	if not frappe.db.has_column("CRM Analytics Event", "source_event_key"):
		frappe.throw(frappe._("Migrate CRM before importing timed source events."), frappe.ValidationError)
	last = frappe.get_all("CRM Analytics Event", filters={"source_type": "CRM Deal", "source_name": deal_name},
		fields=["name", "occurred_at", "payload"], order_by="sequence desc, name desc", limit_page_length=1)
	used = frappe.db.get_value("CRM Analytics Event", {"source_event_key": event.key()}, "name")
	if used:
		if last and used == last[0].name and event.occurred_at_utc == event_instant(last[0]) and allow_exact_replay:
			return True
		frappe.throw(frappe._("This source event ID has already been accepted."), frappe.ValidationError)
	if last:
		last_time = event_instant(last[0])
		if event.occurred_at_utc < last_time:
			frappe.throw(frappe._("This source event predates the latest accepted CRM change."), frappe.ValidationError)
		if event.occurred_at_utc == last_time:
			previous = json.loads(last[0].payload).get("source_event") or {}
			if (previous.get("source"), previous.get("record_id")) != (event.source, event.record_id):
				frappe.throw(frappe._("This source event is repeated or out of order."), frappe.ValidationError)
			if event.event_id <= previous.get("event_id", ""):
				frappe.throw(frappe._("This source event is repeated or out of order."), frappe.ValidationError)
	return False


def validate_deal_source_event(doc):
	"""Called before status logs, sharing, and any analytics fact are written."""
	event = current_source_event()
	if not event:
		if doc.get("analytics_source_event_id") or doc.get("analytics_source_event_at"):
			frappe.throw(frappe._("Source event markers are only accepted by CRM Deal Data Import."), frappe.PermissionError)
		return None
	if not frappe.flags.in_import or doc.is_new():
		frappe.throw(frappe._("Source events update existing deals through Data Import only."), frappe.PermissionError)
	if doc.external_source != event.source or doc.external_record_id != event.record_id:
		frappe.throw(frappe._("Source event identity does not match this deal."), frappe.ValidationError)
	previous = doc.get_doc_before_save()
	if not previous or previous.external_source != event.source or previous.external_record_id != event.record_id:
		frappe.throw(frappe._("Source event identity cannot be changed by the same import row."), frappe.ValidationError)
	check_event_order(doc.name, event)
	return event
