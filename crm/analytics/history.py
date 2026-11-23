"""Transaction-local facts for analytics, never a second CRM CRUD interface."""

from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import orjson
from threading import RLock
from time import monotonic

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

EVENT = "CRM Analytics Event"
_writing = ContextVar("crm_analytics_history_write", default=False)
# One bounded, process-local entry. A revision is checked inside the report's
# repeatable-read transaction before any event from this entry is reused.
_read_cache_lock = RLock()
_read_cache = {}
_fact_read_cache = {}
_FACT_READ_CACHE_MAX_BYTES = 24 * 1024 * 1024
_READ_CACHE_MAX_EVENTS = 120000
_READ_CACHE_MAX_BYTES = 48 * 1024 * 1024
_READ_CACHE_TTL_SECONDS = 300
FIELDS = {
	"CRM Deal": ("creation", "status", "pipeline", "deal_owner", "source", "lead", "deal_value", "currency",
		"exchange_rate", "expected_deal_value", "probability", "expected_closure_date", "closed_date", "lost_reason", "analytics_value_presence"),
	"CRM Lead": ("creation", "status", "lead_owner", "source", "planned_deal_pipeline", "converted"),
	"CRM Task": ("status", "assigned_to", "due_date", "reference_doctype", "reference_docname"),
}

VALUE_FIELDS = ("deal_value", "expected_deal_value", "probability", "exchange_rate")


def _same_value(field, left, right):
	if field in VALUE_FIELDS and left is not None and right is not None:
		try:
			return Decimal(str(left)) == Decimal(str(right))
		except InvalidOperation:
			pass
	return left == right


def _same_state(left, right):
	return left is not None and right is not None and left.keys() == right.keys() and all(
		_same_value(field, value, right[field]) for field, value in left.items()
	)


def _last_after(doc):
	if not frappe.db.table_exists(EVENT):
		return None
	last = frappe.get_all(EVENT, filters={"source_type": doc.doctype, "source_name": doc.name},
		fields=["payload"], order_by="sequence desc, name desc", limit_page_length=1)
	return json.loads(last[0].payload).get("after") if last else None


def remember_value_presence(doc):
	"""Keep missing values distinct from Frappe's numeric SQL default zero.

	The incoming metadata is never trusted. Unchanged legacy zero is uncertain;
	new/changed explicit zero is known. Unrelated saves preserve prior evidence.
	"""
	old = doc.get_doc_before_save()
	previous = frappe.parse_json(old.get("analytics_value_presence") or "{}") if old else {}
	if not isinstance(previous, dict):
		previous = {}
	last_after = _last_after(doc) if old else None
	known = {}
	for field in VALUE_FIELDS:
		value = doc.get(field)
		if doc.is_new() or doc.has_value_changed(field):
			known[field] = value is not None and value != ""
		else:
			known[field] = previous.get(field, bool(value)) is True
			# Direct db_set bypasses document hooks. A later unrelated save must
			# not turn that unrecorded numeric change into a confirmed zero.
			if last_after is not None and not _same_value(field, last_after.get(field), value):
				known[field] = False
	doc.analytics_value_presence = json.dumps(known, sort_keys=True)


def prepare():
	# Provision only during installation/migration, never on an analytics GET.
	from frappe.utils.password import get_encryption_key
	get_encryption_key()
	if frappe.db.table_exists(EVENT):
		frappe.db.add_unique(EVENT, ["source_type", "source_name", "sequence"], constraint_name="analytics_source_sequence")
		if frappe.db.has_column(EVENT, "source_event_key"):
			# Existing local pilots may predate the indexed key. Preserve their
			# receipts when the schema is migrated instead of making old IDs reusable.
			rows = frappe.db.sql("""SELECT `name`, `payload` FROM `tabCRM Analytics Event`
				WHERE `source_type`='CRM Deal' AND `source_event_key` IS NULL
				AND `payload` LIKE %s""", ('%"source_event"%',), as_dict=True)
			from crm.analytics.source_event_import import source_event_key
			for row in rows:
				info = json.loads(row.payload).get("source_event")
				if not info:
					continue
				key = source_event_key(info["source"], info["record_id"], info["event_id"])
				frappe.db.set_value(EVENT, row.name, "source_event_key", key, update_modified=False)
			frappe.db.add_unique(EVENT, ["source_event_key"], constraint_name="analytics_source_event_key")


@contextmanager
def internal_write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class CRMAnalyticsEvent(Document):
	def validate(self):
		if not _writing.get() or not self.is_new():
			frappe.throw(frappe._("Analytics history is managed by CRM."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(frappe._("Analytics history cannot be deleted through document operations."), frappe.PermissionError)

	def before_rename(self, *args, **kwargs):
		frappe.throw(frappe._("Analytics history cannot be renamed."), frappe.PermissionError)

	def notify_update(self):
		pass

	def notify_change(self):
		pass


def state(doc):
	values = {field: str(doc.get(field)) if doc.get(field) is not None else None for field in FIELDS[doc.doctype]}
	if doc.doctype == "CRM Deal":
		values["status_type"] = frappe.db.get_value("CRM Deal Status", doc.get("status"), "type") if doc.get("status") else None
	return values


def capture(doc, method=None):
	if doc.doctype not in FIELDS or frappe.flags.in_install_db or not frappe.db.table_exists(EVENT):
		return
	current = state(doc)
	old = doc.get_doc_before_save()
	previous = state(old) if old else None
	# No analytical change means no new analytical fact, including comments/AI updates.
	if method != "on_trash" and _same_state(previous, current):
		return
	last = frappe.get_all(EVENT, filters={"source_type": doc.doctype, "source_name": doc.name},
		fields=["name", "payload", "occurred_at", "sequence"], order_by="sequence desc, name desc", limit_page_length=1)
	if previous is None and last:
		previous = json.loads(last[0].payload).get("after")
		if previous is not None:
			previous = {field: previous.get(field) for field in current}
		if method != "on_trash" and _same_state(previous, current):
			return
	from crm.analytics.source_event_import import current_source_event, event_instant, utc_now
	source_event = current_source_event() if doc.doctype == "CRM Deal" else None
	when = source_event.occurred_at if source_event else now_datetime()
	last_payload = json.loads(last[0].payload) if last else {}
	last_absolute = bool(last_payload.get("occurred_at_utc") or
		(last_payload.get("source_event") or {}).get("occurred_at_utc"))
	# Once a source event has a known absolute instant, keep that timeline
	# through subsequent native saves, even across a repeated local hour.
	native_utc = utc_now() if not source_event and last_absolute else None
	if last and (event_instant(last[0]) > (source_event.occurred_at_utc if source_event else native_utc)
		if source_event or native_utc else get_datetime(last[0].occurred_at) > when):
		frappe.throw(
			frappe._("This change predates the latest accepted CRM history event. Import source changes in order."),
			frappe.ValidationError,
		)
	created_now = previous is None and abs((get_datetime(doc.creation) - when).total_seconds()) < 1
	kind = "Deleted" if method == "on_trash" else "Created" if created_now else "Updated" if previous is not None else "Baseline"
	payload = {"before": current if kind == "Deleted" else previous, "after": None if kind == "Deleted" else current,
		"timezone": frappe.db.get_single_value("System Settings", "time_zone") or "UTC"}
	if source_event:
		payload["source_event"] = source_event.payload()
	elif native_utc:
		payload["occurred_at_utc"] = native_utc.isoformat()
	encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
	# Native source saves already hold that source row's write lock. An explicit
	# sequence preserves order even when two accepted writes share a timestamp.
	sequence = int(last[0].sequence) + 1 if last else 1
	name = sha256(json.dumps([doc.doctype, doc.name, sequence, str(doc.modified), kind, encoded], ensure_ascii=False).encode()).hexdigest()
	if frappe.db.exists(EVENT, name):
		return
	with internal_write():
		frappe.get_doc({"doctype": EVENT, "name": name, "source_type": doc.doctype, "source_name": doc.name,
			"sequence": sequence,
			"source_event_key": source_event.key() if source_event else None,
			"source_modified": doc.modified, "event_kind": kind, "occurred_at": when,
			"actor": frappe.session.user, "payload": encoded, "history_complete": int(created_now),
		}).insert(ignore_permissions=True, set_name=name)


def backfill_baselines(*, source_names: dict[str, list[str]] | None = None) -> dict[str, int]:
	"""Record an observation boundary for pre-analytics CRM rows without inventing past events.

	Run in the site's migration transaction. Native writers must be stopped by
	maintenance mode while missing rows are selected and baselines are inserted.
	"""
	if source_names is not None and (
		not isinstance(source_names, dict) or set(source_names) - set(FIELDS)
		or any(not isinstance(names, list) or any(not isinstance(name, str) for name in names)
			for names in source_names.values())
	):
		raise ValueError("Explicit source names must belong to supported CRM types")
	prepare()
	counts = {}
	for doctype in FIELDS:
		if not frappe.db.table_exists(doctype):
			continue
		counts[doctype] = 0
		if source_names is not None and not source_names.get(doctype):
			continue
		scope = " AND source.`name` IN %s" if source_names is not None else ""
		params = (doctype, tuple(source_names[doctype])) if source_names is not None else (doctype,)
		rows = frappe.db.sql(
			f"""SELECT source.`name` FROM `tab{doctype}` source
				WHERE NOT EXISTS (
					SELECT 1 FROM `tabCRM Analytics Event` event
					WHERE event.`source_type` = %s AND event.`source_name` = source.`name`
				) {scope} ORDER BY source.`name`""",
			params, as_list=True,
		)
		counts[doctype] = 0
		for (name,) in rows:
			doc = frappe.get_doc(doctype, name)
			current = state(doc)
			payload = {"before": None, "after": current,
				"timezone": frappe.db.get_single_value("System Settings", "time_zone") or "UTC"}
			encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
			fingerprint = sha256(json.dumps(
				[doctype, name, 1, str(doc.modified), "Baseline", encoded],
				ensure_ascii=False,
			).encode()).hexdigest()
			with internal_write():
				frappe.get_doc({"doctype": EVENT, "name": fingerprint,
					"source_type": doctype, "source_name": name, "sequence": 1,
					"source_modified": doc.modified, "event_kind": "Baseline",
					"occurred_at": now_datetime(), "actor": frappe.session.user,
					"payload": encoded, "history_complete": 0,
				}).insert(ignore_permissions=True, set_name=fingerprint)
			counts[doctype] += 1
	return counts


def load_events(doctype: str, permitted_names: list[str], *, administrator_scan: bool = False) -> dict[str, list[dict]]:
	"""Internal read: callers must supply identities from the current authorized query."""
	result = {name: [] for name in permitted_names}
	if not permitted_names or not frappe.db.table_exists(EVENT):
		return result
	if administrator_scan and frappe.session.user == "Administrator":
		# Administrator can read every native source document. One indexed scan
		# avoids 20 per-batch round trips per 10k deals; the selected source IDs
		# still constrain the returned map, including after source deletion.
		rows = frappe.db.sql(
			"""SELECT `name`, `source_name`, `event_kind`, `occurred_at`, `payload`,
				`history_complete`, `creation`, `sequence`
				FROM `tabCRM Analytics Event`
				WHERE `source_type` = %s
				ORDER BY `source_name` ASC, `sequence` ASC""",
			(doctype,), as_dict=True,
		)
		for row in rows:
			if row["source_name"] in result:
				row["payload"] = orjson.loads(row["payload"])
				result[row["source_name"]].append(row)
		return result
	# Bounded IN lists; the unique (source_type, source_name, sequence) index
	# gives stable event order even when timestamps match.
	for offset in range(0, len(permitted_names), 500):
		batch = permitted_names[offset:offset + 500]
		placeholders = ", ".join(["%s"] * len(batch))
		# Identities were selected by native source permissions before this call.
		# Bind each value and avoid the ORM's per-row conversion for large histories.
		rows = frappe.db.sql(
			f"""SELECT `name`, `source_name`, `event_kind`, `occurred_at`, `payload`,
				`history_complete`, `creation`, `sequence`
				FROM `tabCRM Analytics Event`
				WHERE `source_type` = %s AND `source_name` IN ({placeholders})
				ORDER BY `source_name` ASC, `sequence` ASC""",
			(doctype, *batch), as_dict=True,
		)
		for row in rows:
			row["payload"] = orjson.loads(row["payload"])
			result[row["source_name"]].append(row)
	return result


def _event_revision(doctype: str) -> tuple[str, int]:
	"""Detect accepted appends/deletions, including rollback then new same-sequence event.

	Native document operations never edit an existing event. The final event's
	content-addressed name and the count therefore identify every source chain.
	"""
	rows = frappe.db.sql(
		"""SELECT latest.source_name, latest.event_count, latest.max_sequence,
			event.name AS last_event_name
			FROM (SELECT source_name, COUNT(*) AS event_count,
				MAX(sequence) AS max_sequence
				FROM `tabCRM Analytics Event` WHERE source_type = %s
				GROUP BY source_name) latest
			JOIN `tabCRM Analytics Event` event
				ON event.source_type = %s AND event.source_name = latest.source_name
				AND event.sequence = latest.max_sequence
			ORDER BY latest.source_name""",
		(doctype, doctype), as_list=True,
	)
	return sha256(orjson.dumps(rows)).hexdigest(), sum(row[1] for row in rows)


def load_events_for_report(doctype: str, permitted_names: list[str], *, administrator_scan: bool = False) -> dict[str, list[dict]]:
	"""Reuse only an Administrator GET's immutable event history after revalidation.

	Every source row and its native permissions are selected again by the caller.
	The cache is never used by internal save/rollback calls or non-admin viewers.
	"""
	if not (administrator_scan and frappe.session.user == "Administrator"
		and getattr(frappe.local, "analytics_consistent_read", False)
		and permitted_names and frappe.db.table_exists(EVENT)):
		return load_events(doctype, permitted_names, administrator_scan=administrator_scan)
	revision, event_count = _event_revision(doctype)
	if event_count > _READ_CACHE_MAX_EVENTS:
		return load_events(doctype, permitted_names, administrator_scan=administrator_scan)
	with _read_cache_lock:
		entry = _read_cache.get("entry")
		if entry and entry["site"] == frappe.local.site and entry["doctype"] == doctype \
			and entry["revision"] == revision and entry["expires"] > monotonic() \
			and set(permitted_names) <= entry["loaded_names"]:
			return {name: entry["events"].get(name, []) for name in permitted_names}
		events = load_events(doctype, permitted_names, administrator_scan=True)
		# Guard retained memory. The temporary encoding is discarded immediately;
		# a source with unusually large payloads falls back to fresh reads.
		encoded_bytes = len(orjson.dumps(events))
		if encoded_bytes <= _READ_CACHE_MAX_BYTES:
			_read_cache["entry"] = {"site": frappe.local.site, "doctype": doctype,
				"revision": revision, "events": events,
				"loaded_names": set(permitted_names),
				"expires": monotonic() + _READ_CACHE_TTL_SECONDS}
		else:
			_read_cache.clear()
		return events


def deal_history(rows: list[dict]) -> dict:
	"""Only confirmed transitions carry dates; a baseline does not invent an interval."""
	result = {"stage_entered_at": None, "lost_date": None, "close_date_pushed": False,
		"stage_history_complete": False, "history_known_from": None, "outcome_attribution": None, "transitions": []}
	for event in rows:
		before = event["payload"].get("before") or {}
		after = event["payload"].get("after")
		if after is None:
			continue
		# A source event may fall in a repeated local hour. Its UTC instant
		# preserves stage duration and chronological filtering across DST.
		occurred_at = ((event["payload"].get("source_event") or {}).get("occurred_at_utc")
			or event["payload"].get("occurred_at_utc") or event["occurred_at"])
		if result["history_known_from"] is None:
			result["history_known_from"] = occurred_at
		confirmed = event["event_kind"] != "Baseline"
		previous_kind, kind = before.get("status_type"), after.get("status_type")
		if confirmed and before.get("status") != after.get("status") and previous_kind != kind:
			result["outcome_attribution"] = (
				{"kind": kind, "at": occurred_at, "owner": after.get("deal_owner"),
					"closed_date": after.get("closed_date")}
				if kind in ("Won", "Lost") else None
			)
		if confirmed and (before.get("status") != after.get("status")):
			result["stage_entered_at"] = occurred_at
			result["stage_history_complete"] = True
			result["transitions"].append({"name": event["name"], "deal": event["source_name"],
				"from_stage": before.get("status"), "to_stage": after.get("status"), "occurred_at": occurred_at})
			if after.get("status_type") == "Lost":
				result["lost_date"] = occurred_at
		old_date, new_date = before.get("expected_closure_date"), after.get("expected_closure_date")
		if confirmed and old_date and new_date and new_date > old_date:
			result["close_date_pushed"] = True
			result["close_date_push"] = {"at": occurred_at, "previous_date": old_date, "new_date": new_date}
	return result


def _stream_deal_facts(permitted_names):
	"""Fold one source chain at a time; full payloads never accumulate in memory."""
	allowed = set(permitted_names)
	projected = {}
	current_name = None
	chain = []
	with frappe.db.unbuffered_cursor():
		rows = frappe.db.sql("""
			SELECT name, source_name, event_kind, occurred_at, history_complete, payload, sequence
			FROM `tabCRM Analytics Event` WHERE source_type = %s
			ORDER BY source_name, sequence
			""", ("CRM Deal",), as_dict=True, as_iterator=True)
		for row in rows:
			name = row["source_name"]
			if name not in allowed:
				continue
			if current_name is not None and name != current_name:
				projected.update(_project_deal_events({current_name: chain}))
				chain = []
			current_name = name
			row["payload"] = orjson.loads(row["payload"])
			chain.append(row)
		if current_name is not None:
			projected.update(_project_deal_events({current_name: chain}))
	projected.update(_project_deal_events({name: [] for name in allowed - projected.keys()}))
	return projected


def _project_deal_events(events):
	"""Keep only facts consumed by reporting; never retain arbitrary payload text."""
	projected = {}
	for name, rows in events.items():
		latest = rows[-1]["payload"].get("after") if rows else None
		first = rows[0] if rows else None
		projected[name] = {
			"latest_after": {field: latest.get(field) for field in VALUE_FIELDS} if latest is not None else None,
			"first": {key: first[key] for key in ("event_kind", "history_complete", "occurred_at")} if first else None,
			"fact": deal_history(rows),
		}
	return projected


def load_deal_facts_for_report(permitted_names, *, administrator_scan=False):
	"""Bounded projection cache, revalidated inside the current source snapshot.

	Only Administrator consistent reads can reuse it. Permissions and current
	source values are selected on every call. Native writes/rollback and other
	users always read fresh events. Event payloads are not retained in this cache.
	"""
	if not (administrator_scan and frappe.session.user == "Administrator"
		and getattr(frappe.local, "analytics_consistent_read", False)
		and permitted_names and frappe.db.table_exists(EVENT)):
		return _project_deal_events(load_events("CRM Deal", permitted_names, administrator_scan=administrator_scan))
	revision, count = _event_revision("CRM Deal")
	if count > _READ_CACHE_MAX_EVENTS:
		return _project_deal_events(load_events("CRM Deal", permitted_names, administrator_scan=True))
	with _read_cache_lock:
		entry = _fact_read_cache.get("entry")
		if not (entry and entry["site"] == frappe.local.site and entry["revision"] == revision
			and entry["expires"] > monotonic() and set(permitted_names) <= entry["loaded_names"]):
			facts = _stream_deal_facts(permitted_names)
			if len(orjson.dumps(facts)) <= _FACT_READ_CACHE_MAX_BYTES:
				entry = {"site": frappe.local.site, "revision": revision, "facts": facts,
					"loaded_names": set(permitted_names), "expires": monotonic() + _READ_CACHE_TTL_SECONDS}
				_fact_read_cache["entry"] = entry
			else:
				_fact_read_cache.clear()
				return facts
		# Callers consume transitions with pop(); never expose the cached dict itself.
		return {name: {"latest_after": dict(item["latest_after"]) if item["latest_after"] is not None else None,
			"first": dict(item["first"]) if item["first"] else None,
			"fact": {**item["fact"], "transitions": [dict(row) for row in item["fact"]["transitions"]]}}
			for name in permitted_names if (item := entry["facts"].get(name)) is not None}
