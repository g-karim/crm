"""Local, evidence-based script checks with human confirmation and a shared quota."""

from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, time, timedelta
from decimal import Decimal
import re

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.model.document import Document

from crm.analytics.call_journal import _call
from crm.analytics.call_reporting import CALL, _batch, _connected, _filters, _line, _make_report, read_named
from crm.analytics.sales_plans import company_plan_editor, plan_scope
from crm.analytics.service import coherent_read, exact_json, normalize_filters, snapshot_hash
from crm.analytics.utm import clean_tag
from crm.utils import sales_user_only

SETTINGS = "CRM Call Quality Settings"
REVIEW = "CRM Call Quality Review"
DEFAULT = "Default"
STATE = "ai_analysis_status"
TRANSCRIPT = "ai_transcript"
DECISIONS = {"Passed", "Failed", "Not applicable"}
REVIEW_FIELDS = ["name", "call_log", "script_key", "script_revision", "transcript_digest",
	"state", "review_data", "reviewer", "score", "modified"]
MAX_TRANSCRIPT = 50_000
TRANSCRIPT_STATES = ("ready", "not_started", "in_progress", "failed", "empty", "too_long", "unavailable")
_writing = ContextVar("crm_call_quality_write", default=False)


@contextmanager
def _write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class InternalQualityDocument(Document):
	def validate(self):
		if not _writing.get():
			frappe.throw(_("Call quality records are managed by analytics."), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("Call quality history is preserved."), frappe.PermissionError)


def _bad():
	frappe.throw(_("Choose valid lines, scripts, criteria and a daily review limit."), frappe.ValidationError)


def _denied():
	frappe.throw(_("This call quality operation is unavailable."), frappe.PermissionError)


def _revision_conflict():
	frappe.throw(_("Call quality data changed. Reload the current version."), frappe.TimestampMismatchError)


def _key(value):
	if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", value):
		_bad()
	return value


def _definition(value):
	try:
		data = frappe.parse_json(value) if isinstance(value, str) else value
	except ValueError:
		_bad()
	required = {"daily_limit", "scripts"}
	if not isinstance(data, dict) or not required <= set(data) <= required | {"allowed_lines"}:
		_bad()
	limit, scripts = data["daily_limit"], data["scripts"]
	if type(limit) is not int or not 0 <= limit <= 500 or not isinstance(scripts, list) or len(scripts) > 5:
		_bad()
	result = {}
	for script in scripts:
		if not isinstance(script, dict) or set(script) != {"key", "title", "criteria"}:
			_bad()
		key, title, criteria = _key(script["key"]), clean_tag(script["title"]), script["criteria"]
		if key in result or not title or not isinstance(criteria, list) or not 1 <= len(criteria) <= 12:
			_bad()
		items = {}
		for item in criteria:
			if not isinstance(item, dict) or set(item) != {"key", "label", "phrases"}:
				_bad()
			identifier, label, phrases = _key(item["key"]), clean_tag(item["label"]), item["phrases"]
			if identifier in items or not label or not isinstance(phrases, list) or not 1 <= len(phrases) <= 8:
				_bad()
			terms = list(dict.fromkeys(" ".join(clean_tag(phrase).split()) for phrase in phrases))
			if any(not 2 <= len(term) <= 100 for term in terms):
				_bad()
			items[identifier] = {"key": identifier, "label": label, "phrases": terms}
		result[key] = {"key": key, "title": title, "criteria": list(items.values())}
	config = {"daily_limit": limit, "scripts": list(result.values())}
	if "allowed_lines" in data:
		lines = data["allowed_lines"]
		if lines is not None and (
			not isinstance(lines, list) or not lines
			or any(not isinstance(line, str) or not re.fullmatch(r"[a-f0-9]{24}", line) for line in lines)
		):
			_bad()
		config["allowed_lines"] = None if lines is None else sorted(set(lines))
	return config


def _settings(*, lock=False):
	row = frappe.db.get_value(SETTINGS, DEFAULT, ["definition", "modified"], as_dict=True, for_update=lock)
	if not row:
		return {"daily_limit": 0, "scripts": [], "allowed_lines": None}, ""
	return {"allowed_lines": None, **_definition(row.definition)}, str(row.modified)


def _budget(config):
	today = normalize_filters().as_of.date()
	left = datetime.combine(today, time.min)
	right = datetime.combine(today + timedelta(days=1), time.min)
	used = frappe.db.count(REVIEW, [["creation", ">=", left], ["creation", "<", right]])
	return {"limit": config["daily_limit"], "used": used, "day": str(today)}


def _reviewer():
	return plan_scope()[0]


def _script(config, key):
	return next((item for item in config["scripts"] if item["key"] == key), None)


def _status_visible(field):
	return field in (set(get_permitted_fields(CALL, permission_type="read"))
		- {item.fieldname for item in frappe.get_meta(CALL).get_masked_fields()})


def _transcript_state(row):
	if not row or STATE not in row:
		return "unavailable"
	status = row.get(STATE)
	if status in ("Queued", "Processing"):
		return "in_progress"
	if status == "Failed":
		return "failed"
	if not status:
		return "not_started"
	if status != "Completed" or TRANSCRIPT not in row:
		return "unavailable"
	text = row.get(TRANSCRIPT)
	if not isinstance(text, str):
		return "empty" if text is None else "unavailable"
	if len(text) > MAX_TRANSCRIPT:
		return "too_long"
	return "ready" if text.strip() else "empty"


def _transcripts(names, extra_fields=()):
	from frappe.query_builder import Order

	from crm.call_analysis import workspace

	fields = ["name", STATE, TRANSCRIPT, *extra_fields]
	has_runs = frappe.db.table_exists(workspace.RUN)
	source = ("recording_url", "reference_doctype", "reference_docname")
	if has_runs:
		fields.extend(source)
	for batch in _batch(names):
		rows = {row["name"]: row for row in read_named(CALL, fields, batch)}
		if has_runs and rows:
			table = frappe.qb.DocType(workspace.RUN)
			runs = (workspace.run_query(fields=[table.call_log, table.state, table.recording_source,
				table.reference_doctype, table.reference_docname, table.raw_transcript])
				.where(table.call_log.isin(list(rows)))
				.orderby(table.creation, order=Order.desc)
				.orderby(table.name, order=Order.desc)
				.run(as_dict=True))
			seen = set()
			for run in runs:
				if run.call_log in seen:
					continue
				seen.add(run.call_log)
				row = rows[run.call_log]
				if not {STATE, TRANSCRIPT, *source} <= row.keys():
					continue
				if tuple(row.get(field) for field in source) != (
					run.recording_source, run.reference_doctype, run.reference_docname
				):
					row[STATE] = "Unavailable"
					row[TRANSCRIPT] = None
					continue
				row[STATE] = run.state
				row[TRANSCRIPT] = run.raw_transcript
		yield from rows.values()


def _local_transcript(name, config, *, lock=False):
	doc = _call(name, lock=lock)
	if not _connected(doc):
		return None
	allowed = config["allowed_lines"]
	line_fields = ("type", "from", "to")
	row = next(_transcripts([name], line_fields if allowed is not None else ()), None)
	if allowed is not None:
		secret = frappe.local.conf.get("encryption_key", "").encode()
		if not row or not set(line_fields) <= row.keys() or not secret or _line(row, secret)[0] not in allowed:
			_denied()
	return row[TRANSCRIPT] if _transcript_state(row) == "ready" else None


def _identity(call, script_revision, transcript_revision):
	return "quality-" + snapshot_hash(call, script_revision, transcript_revision)[:40]


def _draft(script, transcript):
	results = []
	for item in script["criteria"]:
		match = None
		for phrase in item["phrases"]:
			pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in phrase.split()) + r"(?!\w)"
			found = re.search(pattern, transcript, re.IGNORECASE)
			if found and (match is None or found.start() < match.start()):
				match = found
		results.append({"key": item["key"], "label": item["label"], "span": list(match.span()) if match else None,
			"decision": None})
	return {"title": script["title"], "criteria": results}


def _review_row(name, *, lock=False):
	return frappe.db.get_value(REVIEW, name, REVIEW_FIELDS, as_dict=True, for_update=lock)


def _public_review(row, transcript):
	data = frappe.parse_json(row.review_data)
	for item in data["criteria"]:
		span = item.pop("span")
		item["evidence"] = transcript[span[0]:span[1]] if span and 0 <= span[0] < span[1] <= len(transcript) else None
	return {"name": row.name, "version": str(row.modified), "state": row.state, "score": row.score, **data}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_settings(from_date: str | None = None, to_date: str | None = None):
	if not _reviewer():
		_denied()
	config, version = _settings()
	editable = company_plan_editor()
	budget = _budget(config)
	if not editable:
		config.pop("allowed_lines")
	elif from_date or to_date:
		report, _, _ = _make_report(_filters({"from_date": from_date, "to_date": to_date}))
		config["line_options"] = [
			{"value": row["key"], "label": row["label"]} for row in report["groups"]["lines"] if row["key"]
		]
	return {**config, "version": version, "viewer": frappe.session.user,
		"can_edit": editable, "budget": budget, "mode": "local_phrases"}


@frappe.whitelist(methods=["POST"])
@sales_user_only
def save_settings(definition: dict | str, expected_version: str, expected_viewer: str):
	if not company_plan_editor() or expected_viewer != frappe.session.user:
		_denied()
	data = _definition(definition)
	try:
		current, version = _settings(lock=True)
		data.setdefault("allowed_lines", current["allowed_lines"])
		if (data == current) and version:
			return {"version": version}
		if version != expected_version:
			_revision_conflict()
		with _write():
			if version:
				doc = frappe.get_doc(SETTINGS, DEFAULT, for_update=True)
				doc.definition = frappe.as_json(data)
				doc.save(ignore_permissions=True)
			else:
				doc = frappe.get_doc({"doctype": SETTINGS, "definition": frappe.as_json(data)})
				doc.insert(set_name=DEFAULT, ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.QueryDeadlockError):
		_revision_conflict()
	return {"version": str(doc.modified)}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_workspace(call_log: str, script_key: str):
	if not _reviewer():
		_denied()
	config, version = _settings()
	transcript = _local_transcript(call_log, config)
	script = _script(config, script_key)
	review = None
	if transcript and script:
		name = _identity(call_log, snapshot_hash(script), snapshot_hash(transcript))
		row = _review_row(name)
		if row:
			review = _public_review(row, transcript)
	return {"call": call_log, "viewer": frappe.session.user, "version": version, "mode": "local_phrases",
		"available": bool(transcript and script), "review": review, "budget": _budget(config)}


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_transcript(call_log: str, review_name: str | None = None):
	if not _reviewer():
		_denied()
	config, _version = _settings()
	text = _local_transcript(call_log, config)
	if not text:
		frappe.throw(_("This local transcript is unavailable."), frappe.ValidationError)
	if review_name:
		row = _review_row(review_name)
		if not row or row.call_log != call_log:
			_denied()
		if row.transcript_digest != snapshot_hash(text):
			_revision_conflict()
	return {"text": text}


@frappe.whitelist(methods=["POST"])
@sales_user_only
def start_review(call_log: str, script_key: str, expected_version: str, expected_viewer: str):
	if expected_viewer != frappe.session.user or not _reviewer():
		_denied()
	config, version = _settings(lock=True)
	if expected_version != version:
		_revision_conflict()
	script = _script(config, script_key)
	transcript = _local_transcript(call_log, config, lock=True)
	if not transcript or not script:
		frappe.throw(_("Use a completed local transcript and a configured script."), frappe.ValidationError)
	script_revision, digest = snapshot_hash(script), snapshot_hash(transcript)
	name = _identity(call_log, script_revision, digest)
	row = _review_row(name, lock=True)
	if not row:
		if _budget(config)["used"] >= config["daily_limit"]:
			frappe.throw(_("The daily local call review quota has been reached."), frappe.ValidationError)
		with _write():
			frappe.get_doc({"doctype": REVIEW, "call_log": call_log, "script_key": script_key,
				"script_revision": script_revision, "transcript_digest": digest, "state": "Draft",
				"review_data": frappe.as_json(_draft(script, transcript))}).insert(set_name=name, ignore_permissions=True)
		row = _review_row(name)
	return _public_review(row, transcript)


@frappe.whitelist(methods=["POST"])
@sales_user_only
def confirm_review(call_log: str, name: str, decisions: dict | str, expected_version: str, expected_viewer: str):
	if expected_viewer != frappe.session.user or not _reviewer():
		_denied()
	config, _version = _settings(lock=True)
	transcript = _local_transcript(call_log, config, lock=True)
	row = _review_row(name, lock=True)
	if not row or row.call_log != call_log:
		_denied()
	if not transcript or snapshot_hash(transcript) != row.transcript_digest:
		_revision_conflict()
	items = frappe.parse_json(row.review_data)
	data = frappe.parse_json(decisions) if isinstance(decisions, str) else decisions
	if not isinstance(data, dict) or data.keys() != {item["key"] for item in items["criteria"]}:
		_bad()
	if any(not isinstance(value, str) or value not in DECISIONS for value in data.values()):
		_bad()
	if row.state == "Confirmed" and all(data[item["key"]] == item["decision"] for item in items["criteria"]):
		return _public_review(row, transcript)
	if expected_version != str(row.modified):
		_revision_conflict()
	for item in items["criteria"]:
		item["decision"] = data[item["key"]]
	assessed = len(data) - sum(value == "Not applicable" for value in data.values())
	score = (100 * Decimal(sum(value == "Passed" for value in data.values())) / assessed).quantize(Decimal("0.01")) if assessed else None
	with _write():
		doc = frappe.get_doc(REVIEW, name, for_update=True)
		doc.update({"review_data": frappe.as_json(items), "state": "Confirmed",
			"reviewer": frappe.session.user, "score": str(score) if score is not None else ""})
		doc.save(ignore_permissions=True)
	return _public_review(_review_row(name), transcript)


def _criterion_breakdown(review_names):
	groups = {}
	for batch in _batch(review_names):
		for review in frappe.get_all(REVIEW, filters={"name": ["in", batch]},
			fields=["script_key", "script_revision", "review_data"], limit_page_length=0):
			data = frappe.parse_json(review.review_data)
			group_key = (review.script_key, review.script_revision)
			group = groups.setdefault(group_key, {
				"key": ":".join(group_key), "revision": review.script_revision,
				"title": data["title"], "confirmed": 0, "criteria": {},
			})
			group["confirmed"] += 1
			for item in data["criteria"]:
				criterion = group["criteria"].setdefault(item["key"], {
					"key": item["key"], "label": item["label"], "Passed": 0, "Failed": 0, "Not applicable": 0,
				})
				criterion[item["decision"]] += 1
	result = []
	for group in sorted(groups.values(), key=lambda item: (item["title"].casefold(), item["key"])):
		rows = []
		for criterion in group["criteria"].values():
			passed, failed = criterion["Passed"], criterion["Failed"]
			assessed = passed + failed
			rows.append({
				"key": criterion["key"], "label": criterion["label"],
				"passed": passed, "failed": failed, "not_applicable": criterion["Not applicable"],
				"pass_rate": (100 * Decimal(passed) / assessed).quantize(Decimal("0.01")) if assessed else None,
			})
		result.append({**group, "criteria": rows})
	return result


def _script_review_state(history, script_key, revision, digest):
	reviews = [row for row in history if row.script_key == script_key]
	current = next((row for row in reviews if row.script_revision == revision and row.transcript_digest == digest), None)
	if current:
		return "confirmed" if current.state == "Confirmed" else "draft"
	if not reviews:
		return "new"
	if reviews[0].script_revision == revision:
		return "transcript_changed"
	if reviews[0].transcript_digest == digest:
		return "script_changed"
	return "changed"


@frappe.whitelist(methods=["GET"])
@sales_user_only
@coherent_read
def get_quality_report(
	filters: dict | str | None = None, start: int = 0, transcript_state: str = "", script_key: str = "",
):
	if transcript_state and transcript_state not in (*TRANSCRIPT_STATES, "eligible", "pending_review"):
		frappe.throw(_("Choose a valid transcript state."), frappe.ValidationError)
	queue_mode = transcript_state == "pending_review"
	can_review = _reviewer()
	if queue_mode and not can_review:
		_denied()
	if not frappe.db.table_exists(SETTINGS) or not frappe.db.table_exists(REVIEW):
		return {"available": False, "rows": []}
	report, all_calls, _revision = _make_report(_filters(filters))
	if not report["coverage"]["duration"] or not _status_visible(STATE) or not _status_visible(TRANSCRIPT):
		return {"available": False, "rows": []}
	config, _version = _settings()
	scripts = config["scripts"]
	active_script = None
	if queue_mode:
		active_script = _script(config, _key(script_key)) if script_key else next(iter(scripts), None)
	active_revision = snapshot_hash(active_script) if active_script else None
	queue_states = {}
	calls = [row for row in all_calls if row["connected"]]
	ids = [row["name"] for row in calls]
	transcript_states, completed = {}, set()
	states, scores, drafts = {}, {}, set()
	confirmed_names = []
	for batch in _batch(ids):
		transcripts = list(_transcripts(batch))
		for raw in transcripts:
			name = raw["name"]
			transcript_states[name] = _transcript_state(raw)
			if raw.get(STATE) == "Completed":
				completed.add(name)
		ready = [raw for raw in transcripts if transcript_states[raw["name"]] == "ready"]
		if not ready:
			continue
		latest = defaultdict(list)
		for row in frappe.get_all(REVIEW, filters={"call_log": ["in", [raw["name"] for raw in ready]]},
			fields=["name", "call_log", "transcript_digest", "state", "score", "script_key", "script_revision"],
			order_by="modified desc, name asc", limit_page_length=0):
			latest[row.call_log].append(row)
		for raw in ready:
			name = raw["name"]
			if name not in latest:
				continue
			digest = snapshot_hash(raw[TRANSCRIPT])
			valid = [row for row in latest[name] if row.transcript_digest == digest]
			if active_script:
				queue_states[name] = _script_review_state(latest[name], active_script["key"], active_revision, digest)
			if any(row.state == "Draft" for row in valid):
				drafts.add(name)
			confirmed = next((row for row in valid if row.state == "Confirmed"), None)
			if confirmed:
				states[name] = "Confirmed"
				confirmed_names.append(confirmed.name)
				if confirmed.score not in (None, ""):
					scores[name] = Decimal(confirmed.score)
			else:
				states[name] = "Draft" if valid else "Needs renewed review"
	transcript_states = {name: transcript_states.get(name, "unavailable") for name in ids}
	coverage_counts = Counter(transcript_states.values())
	counts = defaultdict(lambda: {"connected": 0, "confirmed": 0, "ready": 0, "scores": []})
	for row in calls:
		name = row["name"]
		day = counts[row["at"].date().isoformat()]
		day["connected"] += 1
		day["ready"] += int(transcript_states[name] == "ready")
		day["confirmed"] += int(states.get(name) == "Confirmed")
		if name in scores:
			day["scores"].append(scores[name])
	confirmed_count = len(confirmed_names)
	allowed = config["allowed_lines"]
	eligible = {row["name"] for row in calls if allowed is None or row["line"] in allowed}
	eligible_ready = {name for name in eligible if transcript_states[name] == "ready"}
	if transcript_state == "eligible":
		selected = eligible_ready
	elif queue_mode:
		selected = {name for name in eligible_ready if queue_states.get(name) != "confirmed"} if active_script else set()
	elif transcript_state:
		selected = {name for name, state in transcript_states.items() if state == transcript_state}
	else:
		selected = completed
	current = [row for row in calls if row["name"] in selected]
	start = max(0, start)
	return exact_json({"available": True, "can_review": can_review, "can_configure": company_plan_editor(),
		"configured": bool(config["scripts"]), "mode": "local_phrases", "connected": len(calls),
		"completed_transcripts": len(completed), "confirmed": confirmed_count, "drafts": len(drafts),
		"transcript_coverage": {state: coverage_counts[state] for state in TRANSCRIPT_STATES},
		"line_restricted": allowed is not None,
		"eligible_ready": len(eligible_ready),
		"queue": {
			"script": active_script["key"] if active_script else None,
			"scripts": [{"key": script["key"], "title": script["title"]} for script in scripts],
		} if queue_mode else None,
		"coverage": (100 * Decimal(confirmed_count) / len(calls)).quantize(Decimal("0.01")) if calls else None,
		"average": (sum(scores.values()) / len(scores)).quantize(Decimal("0.01")) if scores else None,
		"scored": len(scores), "total": len(current), "start": start,
		"script_breakdown": _criterion_breakdown(confirmed_names) if can_review else [],
		"rows": [{"name": row["name"], "at": row["at"], "employee": row["employee"],
			"agent": frappe.get_cached_value("User", row["employee"], "full_name") if row["employee"] else None,
			"transcript_state": transcript_states[row["name"]],
			"review_line_allowed": row["name"] in eligible,
			"queue_state": queue_states.get(row["name"], "new") if queue_mode else None,
			"status": states.get(row["name"], "Not reviewed"), "score": scores.get(row["name"])}
			for row in current[start:start + 25]],
		"days": [{"key": key, "connected": value["connected"], "confirmed": value["confirmed"],
			"scored": len(value["scores"]),
			"ready_transcripts": value["ready"],
			"average": (sum(value["scores"]) / len(value["scores"])).quantize(Decimal("0.01")) if value["scores"] else None}
			for key, value in sorted(counts.items(), reverse=True)]})
