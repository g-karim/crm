"""Site-local touch tracking. No public endpoints and no changes to modified.

Creation/status use native recovery sources. Other internal changes use a
minimal transactional source log; no business content or field values are copied.
Policy snapshots keep recovery from reinterpreting old actions with new settings.
"""

import hashlib
import json
from datetime import timedelta

import frappe
from frappe.utils import cint, get_datetime, now_datetime

FIELD = "last_touch_at"
SETTINGS = "CRM Touch Settings"
POLICY = "CRM Touch Policy"
EVENT = "CRM Touch Event"
TARGETS = ("CRM Lead", "CRM Deal")
POLICY_FIELDS = ("enabled", "track_leads", "track_deals", "lead_status_changes", "deal_status_changes")


def event_key(
	reference_doctype, reference_name, event_type, source_doctype, source_name, source_revision=None
):
	# Frappe may expose an autonumber task name as int in memory and as text
	# after loading a Data reference from SQL. Both identify the same source.
	identity = tuple(
		str(value) for value in (reference_doctype, reference_name, event_type, source_doctype, source_name)
	)
	# Preserve all Stage 2 identities; edits need a stable persisted revision.
	if source_revision:
		identity += (str(source_revision),)
	return hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest()


def policy_accepts(policy, doctype, event_type):
	if not policy or doctype not in TARGETS or not cint(policy.get("enabled")):
		return False
	prefix = "lead" if doctype == "CRM Lead" else "deal"
	if not cint(policy.get("track_leads" if prefix == "lead" else "track_deals")):
		return False
	return event_type == "Created" or (
		event_type == "Status Changed" and cint(policy.get(f"{prefix}_status_changes"))
	)


def policy_at(policies, occurred_at):
	occurred_at = get_datetime(occurred_at)
	return next(
		(policy for policy in reversed(policies) if get_datetime(policy.effective_from) <= occurred_at),
		None,
	)


def eligible_intervals(policies, doctype, event_type):
	for index, policy in enumerate(policies):
		if policy_accepts(policy, doctype, event_type):
			yield (
				policy.effective_from,
				policies[index + 1].effective_from if index + 1 < len(policies) else None,
			)


def protect_last_touch(doc, method=None):
	"""Frappe already loaded/locked the latest row for its concurrency check.

	Always restore this server-owned field, including while tracking is disabled.
	A background touch deliberately leaves modified unchanged, so trusting the
	client's stale value here would otherwise lose that touch during normal save.
	"""
	if doc.doctype not in TARGETS or not doc.meta.has_field(FIELD):
		return
	previous = doc.get_doc_before_save()
	doc.set(FIELD, previous.get(FIELD) if previous else None)


def capture_created(doc, method=None):
	_capture(doc, "Created")


def capture_status_change(doc, method=None):
	from crm.touch_tracking_internal import capture_card_update

	if capture_card_update(doc):
		return
	previous = doc.get_doc_before_save()
	if previous and previous.status != doc.status:
		_capture(doc, "Status Changed")


def _capture(doc, event_type):
	if not doc.meta.has_field(FIELD):
		return
	try:
		settings = frappe.get_cached_doc(SETTINGS)
		if not settings.policy_revision or not policy_accepts(settings, doc.doctype, event_type):
			return
		if event_type == "Created":
			source_doctype, source_name, occurred_at, actor = doc.doctype, doc.name, doc.creation, doc.owner
		else:
			row = doc.status_change_log[-1]
			if not row.name or not row.creation or row.idx <= 1:
				raise ValueError("Status transition has no persisted native source")
			source_doctype, source_name, occurred_at, actor = (
				"CRM Status Change Log",
				row.name,
				row.creation,
				row.owner,
			)
		policies = _policies()
		policy = policy_at(policies, occurred_at)
		if not policy_accepts(policy, doc.doctype, event_type):
			return
		name = _record_event(
			doc.doctype, doc.name, event_type, source_doctype, source_name, occurred_at, actor, policy
		)
		if name:
			_apply_safely(name)
			# Return the actual persisted value to the caller, including after a retry.
			doc.set(FIELD, frappe.db.get_value(doc.doctype, doc.name, FIELD))
	except Exception as exc:
		if _transaction_failure(exc):
			raise
		# The native source and policy snapshot remain durable in the business
		# transaction. Scheduled recovery recreates a missing event, without save().
		_diagnose("capture")


def _policies():
	from crm.touch_tracking_internal import ADDITIONAL_POLICY_FIELDS

	return frappe.get_all(
		POLICY,
		fields=["name", "effective_from", *POLICY_FIELDS, *ADDITIONAL_POLICY_FIELDS],
		order_by="effective_from asc",
	)


def _record_event(
	doctype,
	name,
	event_type,
	source_doctype,
	source_name,
	occurred_at,
	actor,
	policy,
	*,
	source_revision=None,
	reasons=None,
	origin=None,
):
	key = event_key(doctype, name, event_type, source_doctype, source_name, source_revision)
	if frappe.db.exists(EVENT, key):
		return key
	occurred_at = get_datetime(occurred_at)
	if occurred_at > now_datetime():
		raise ValueError("Touch source timestamp is in the future")
	values = {
		"doctype": EVENT,
		"name": key,
		"reference_doctype": doctype,
		"reference_name": name,
		"event_type": event_type,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"source_revision": source_revision,
		"reasons": json.dumps(reasons or []),
		"origin": origin,
		"occurred_at": occurred_at,
		"actor": actor,
		"policy_revision": policy.name,
		"state": "Pending",
	}
	savepoint = "touch_capture_" + frappe.generate_hash(length=10)
	frappe.db.savepoint(savepoint)
	try:
		event = frappe.get_doc(values)
		event.flags.touch_internal = True
		event.insert(ignore_permissions=True)
		return key
	except Exception as exc:
		if _transaction_failure(exc):
			raise
		frappe.db.rollback(save_point=savepoint)
		raise


def _apply_event(name):
	# Lock order is parent, then event, matching a normal business save. Locking
	# the event first could deadlock with capture while the parent is being saved.
	event = frappe.get_doc(EVENT, name)
	if event.reference_doctype not in TARGETS:
		raise ValueError("Unsupported touch target")
	current = frappe.db.get_value(
		event.reference_doctype, event.reference_name, ["name", FIELD], as_dict=True, for_update=True
	)
	event = frappe.get_doc(EVENT, name, for_update=True)
	if event.state != "Pending":
		return
	if not current:
		frappe.db.set_value(EVENT, name, {"state": "Ignored", "last_error": "Target no longer exists"})
		return
	if not current.get(FIELD) or get_datetime(current[FIELD]) < get_datetime(event.occurred_at):
		frappe.db.set_value(
			event.reference_doctype, event.reference_name, FIELD, event.occurred_at, update_modified=False
		)
	frappe.db.set_value(EVENT, name, {"state": "Applied", "last_error": None, "next_retry_at": None})
	frappe.clear_document_cache(event.reference_doctype, event.reference_name)


def _apply_safely(name):
	savepoint = "touch_apply_" + frappe.generate_hash(length=10)
	frappe.db.savepoint(savepoint)
	try:
		_apply_event(name)
		return True
	except Exception as exc:
		if _transaction_failure(exc):
			raise
		frappe.db.rollback(save_point=savepoint)
		_diagnose("apply")
		try:
			attempts = cint(frappe.db.get_value(EVENT, name, "attempts")) + 1
			frappe.db.set_value(
				EVENT,
				name,
				{
					"attempts": attempts,
					"last_error": type(exc).__name__,
					"next_retry_at": now_datetime() + timedelta(minutes=min(60, 2 ** min(attempts, 6))),
				},
			)
		except Exception as retry_exc:
			if _transaction_failure(retry_exc):
				raise
			_diagnose("retry metadata")
		return False


def process_pending(limit=100):
	"""Retry accepted events using their original policy, even after disable."""
	rows = frappe.get_all(
		EVENT,
		filters={"state": "Pending"},
		or_filters=[["next_retry_at", "is", "not set"], ["next_retry_at", "<=", now_datetime()]],
		pluck="name",
		order_by="occurred_at asc, name asc",
		limit_page_length=limit,
	)
	return sum(_apply_safely(name) for name in rows)


def recover_missing(limit=100):
	"""Recover only sources in historically enabled policy intervals.

	No old modified dates, guessed task history, or replay under today's rules.
	LEFT JOIN skips known events; the bounded queries cannot be starved by old
	disabled intervals. Policies are immutable and captured with settings.save().
	"""
	from crm.touch_tracking_internal import recover_changes

	policies = _policies()
	# Recover grouped status+field changes first so native status recovery cannot
	# replace the accepted list of reasons with a status-only event.
	recovered = recover_changes(limit)
	for doctype in TARGETS:
		for event_type in ("Created", "Status Changed"):
			intervals = list(eligible_intervals(policies, doctype, event_type))
			if not intervals:
				continue
			for source in _missing_sources(doctype, event_type, intervals, limit):
				try:
					policy = policy_at(policies, source.occurred_at)
					_record_event(
						doctype,
						source.reference_name,
						event_type,
						source.source_doctype,
						source.source_name,
						source.occurred_at,
						source.actor,
						policy,
					)
					recovered += 1
				except Exception as exc:
					if _transaction_failure(exc):
						raise
					_diagnose("recovery")
	return recovered


def _missing_sources(doctype, event_type, intervals, limit):
	# Only hard-coded table/column expressions are interpolated; values remain
	# parameters. These recovery queries target the deployed MariaDB runtime.
	is_created = event_type == "Created"
	source_doctype = doctype if is_created else "CRM Status Change Log"
	table = "tab" + source_doctype
	reference = "s.name" if is_created else "s.parent"
	values = [source_doctype, source_doctype, doctype, event_type]
	conditions = []
	for start, end in intervals:
		conditions.append("(s.creation >= %s" + (" AND s.creation < %s" if end else "") + ")")
		values.append(start)
		if end:
			values.append(end)
	extra = (
		"" if is_created else "AND s.parenttype = %s AND s.parentfield = 'status_change_log' AND s.idx > 1"
	)
	if not is_created:
		values.append(doctype)
	values.append(cint(limit))
	return frappe.db.sql(
		f"""SELECT {reference} AS reference_name, %s AS source_doctype,
		           s.name AS source_name, s.creation AS occurred_at, s.owner AS actor
		    FROM `{table}` s
		    LEFT JOIN `tabCRM Touch Event` e
		      ON e.source_doctype = %s AND e.source_name = s.name
		     AND e.reference_doctype = %s AND e.event_type = %s AND e.reference_name = {reference}
		    WHERE e.name IS NULL AND ({" OR ".join(conditions)}) {extra}
		    ORDER BY s.creation, s.name LIMIT %s""",
		values,
		as_dict=True,
	)


def maintenance():
	# This dedicated job owns its transaction. Retry only at that boundary, never
	# by rolling back a caller's business save or replaying its HTTP request. Some
	# Frappe 16 workers do not retry wrapped QueryDeadlockError correctly.
	job = getattr(frappe.local, "job", None)
	is_job = bool(job and job.method == "crm.touch_tracking.maintenance")
	for attempt in range(3 if is_job else 1):
		try:
			if not frappe.db.table_exists(EVENT) or not frappe.db.table_exists(POLICY):
				return
			process_pending()
			from crm.touch_tracking_channels import recover_receipts

			recover_receipts()
			recover_missing()
			process_pending()
			return
		except Exception as exc:
			if (
				is_job
				and attempt < 2
				and (isinstance(exc, frappe.QueryDeadlockError) or (exc.args and exc.args[0] in (1020, 1213)))
			):
				frappe.db.rollback(chain=True)
				continue
			if _transaction_failure(exc):
				raise
			_diagnose("maintenance")
			return


def _transaction_failure(exc):
	"""Never report success after MariaDB has aborted the business transaction.

	Recoverable feature errors are isolated by a savepoint. A deadlock, lost
	connection or failed savepoint instead needs Frappe's normal rollback/retry.
	"""
	code = exc.args[0] if exc.args else None
	return (
		isinstance(exc, frappe.QueryDeadlockError | frappe.QueryTimeoutError)
		or code in (1020, 1205, 1213, 1927, 2006, 2013)
		or (code == 1305 and "SAVEPOINT" in str(exc).upper())
	)


def _diagnose(operation):
	# Keep diagnostics out of the HTTP response and out of the business payload.
	# A logger failure must not turn a successfully saved comment into an error.
	try:
		frappe.logger("crm_touch").exception("Touch tracking failed during %s", operation)
	except Exception:
		pass
