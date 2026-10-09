"""Explicit, transactional cutover preparation. Never an automatic migration patch.

CLI-only operations; retain the returned manifest outside the database for rollback.
No implicit commit, historical events, business hooks or arbitrary modified dates.
"""

import hashlib
import json
from functools import wraps
from itertools import pairwise

import frappe
from frappe.utils import get_datetime, now_datetime

from crm import touch_tracking as touch
from crm.list_settings import STATUS_SORT_FIELD
from crm.touch_tracking_internal import ADDITIONAL_POLICY_FIELDS

CONTROLS = ("legacy_sort_retired", "legacy_sort_migration_id", "legacy_sort_retired_at")
VIEW_FIELDS = ("order_by", "columns", "rows", "filters", "group_by_field", "column_field", "kanban_fields")
CONFIG_FIELDS = (*touch.POLICY_FIELDS, *ADDITIONAL_POLICY_FIELDS)


def _digest(value):
	return hashlib.sha256(
		json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
	).hexdigest()


def _permission():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	if not all(frappe.get_meta(dt).has_field(touch.FIELD) for dt in touch.TARGETS):
		frappe.throw(frappe._("Touch schema must be installed before migration"))


def _string(value):
	return str(value) if value is not None else None


def _targets(lock=False):
	result = {}
	for dt in touch.TARGETS:
		fields = ["name", "creation", "modified", "status", touch.FIELD]
		if dt == "CRM Lead" and frappe.get_meta(dt).has_field(STATUS_SORT_FIELD):
			fields.append(STATUS_SORT_FIELD)
		rows = frappe.db.sql(
			f"select {','.join('`' + field + '`' for field in fields)} from `tab{dt}` order by name"
			+ (" for update" if lock else ""),
			as_dict=True,
		)
		result[dt] = [{field: _string(row.get(field)) for field in fields} for row in rows]
	return result


def _history(lock=False):
	# Locking reads see current committed rows even when the caller already has
	# a repeatable-read snapshot. This is essential when rebuilding rollback dates.
	rows = frappe.db.sql(
		"select name,parent,parenttype,parentfield,idx,creation,`from`,`to` "
		"from `tabCRM Status Change Log` where parenttype in (%s,%s) order by name"
		+ (" for update" if lock else ""),
		touch.TARGETS,
		as_dict=True,
	)
	return [
		{field: _string(value) if field != "idx" else int(value) for field, value in row.items()}
		for row in rows
	]


def status_dates(history, doctype, name):
	rows = sorted(
		(
			row
			for row in history
			if row["parenttype"] == doctype
			and row["parent"] == name
			and row["parentfield"] == "status_change_log"
		),
		key=lambda row: row["idx"],
	)
	if len({row["idx"] for row in rows}) != len(rows):
		raise ValueError("Ambiguous native status history")
	for previous, row in pairwise(rows):
		# Native history opens a new row FROM the newly selected status. Its empty
		# TO is filled only by a later change; never drop the current final row.
		if (
			row["idx"] == previous["idx"] + 1
			and row.get("from")
			and previous.get("to") == row["from"]
			and previous.get("from") != row["from"]
		):
			if not row.get("creation"):
				raise ValueError("Native status row has no source time")
			yield get_datetime(row["creation"])


def _seed(row, history, doctype):
	created = get_datetime(row["creation"])
	if doctype == "CRM Lead" and row.get(STATUS_SORT_FIELD):
		date = get_datetime(row[STATUS_SORT_FIELD])
		if date < created or date > now_datetime():
			raise ValueError("Invalid legacy lead date")
		return str(date), "legacy_status_date"
	dates = [created, *status_dates(history, doctype, row["name"])]
	if any(date > now_datetime() for date in dates):
		raise ValueError("Future native source date")
	return str(max(dates)), "creation_and_native_status_history"


def _views(lock=False):
	fields = ["name", "dt", "modified", "type", "user", "is_standard", "kanban_columns", *VIEW_FIELDS]
	rows = frappe.db.sql(
		f"select {','.join('`' + field + '`' for field in fields)} from `tabCRM View Settings` where dt in (%s,%s) order by name"
		+ (" for update" if lock else ""),
		touch.TARGETS,
		as_dict=True,
	)
	return [{key: _string(value) for key, value in row.items()} for row in rows]


def _source(lock=False):
	settings = frappe.get_doc(touch.SETTINGS, for_update=lock)
	return dict(
		targets=_targets(lock),
		history=_history(lock),
		views=_views(lock),
		settings={field: settings.get(field) for field in (*CONFIG_FIELDS, *CONTROLS)},
		settings_modified=_string(settings.modified),
	)


def prepare():
	_permission()
	source = _source()
	if source["settings"].get("enabled") or source["settings"].get("legacy_sort_migration_id"):
		frappe.throw(frappe._("Prepare cutover while touch tracking is disabled and not migrated"))
	seeds = {
		dt: [
			{
				"name": row["name"],
				"date": _seed(row, source["history"], dt)[0],
				"basis": _seed(row, source["history"], dt)[1],
			}
			for row in rows
		]
		for dt, rows in source["targets"].items()
	}
	body = dict(schema=1, site=frappe.local.site, prepared_at=str(now_datetime()), source=source, seeds=seeds)
	return {**body, "id": _digest(body)}


def _manifest(value):
	value = frappe.parse_json(value)
	if not isinstance(value, dict):
		frappe.throw(frappe._("Invalid touch migration manifest"))
	body = {key: item for key, item in value.items() if key != "id"}
	if value.get("schema") != 1 or value.get("site") != frappe.local.site or _digest(body) != value.get("id"):
		frappe.throw(frappe._("Invalid or foreign-site touch migration manifest"))
	return value


def _view_changes(view):
	if view["dt"] != "CRM Lead":
		return {}
	changes = {}
	for field in VIEW_FIELDS:
		value = view.get(field)
		if not value:
			continue
		if field == "order_by":
			parts = [part.strip().split() for part in value.split(",")]
			changed = False
			for part in parts:
				if part and part[0] == STATUS_SORT_FIELD:
					part[0] = touch.FIELD
					changed = True
			updated = ", ".join(" ".join(part) for part in parts) if changed else value
		elif field in ("group_by_field", "column_field"):
			updated = touch.FIELD if value == STATUS_SORT_FIELD else value
		else:
			data = json.loads(value)
			if field in ("rows", "kanban_fields"):
				data = [touch.FIELD if item == STATUS_SORT_FIELD else item for item in data]
			elif field == "columns":
				for column in data:
					if column.get("key") == STATUS_SORT_FIELD:
						column["key"] = touch.FIELD
						if column.get("label") == "Created or Status Changed":
							column["label"] = "Last Touch"
			elif isinstance(data, dict):
				data = {touch.FIELD if key == STATUS_SORT_FIELD else key: item for key, item in data.items()}
			elif isinstance(data, list):
				for condition in data:
					if (
						isinstance(condition, list)
						and len(condition) in (3, 4)
						and condition[-3] == STATUS_SORT_FIELD
					):
						condition[-3] = touch.FIELD
			updated = json.dumps(data, ensure_ascii=False)
			# Keep byte-for-byte original preferences when no key changed.
			if data == json.loads(value):
				updated = value
		if updated != value:
			changes[field] = updated
	return changes


def _unchanged(source):
	# Background touches do not change business modified. Keep newer dates rather
	# than requiring an otherwise identical pending-event result to disappear.
	copy = json.loads(json.dumps(source, default=str))
	for rows in copy["targets"].values():
		for row in rows:
			row.pop(touch.FIELD, None)
	return copy


def _transactional(fn):
	@wraps(fn)
	def run(*args, **kwargs):
		point = "touch_cutover_" + frappe.generate_hash(length=10)
		frappe.db.savepoint(point)
		try:
			return fn(*args, **kwargs)
		except Exception as exc:
			if not touch._transaction_failure(exc):
				frappe.db.rollback(save_point=point)
				frappe.clear_document_cache(touch.SETTINGS)
			raise

	return run


@_transactional
def apply(manifest):
	_permission()
	manifest = _manifest(manifest)
	settings = frappe.get_doc(touch.SETTINGS, for_update=True)
	if settings.legacy_sort_migration_id == manifest["id"]:
		return {"id": manifest["id"], "already_applied": True}
	if settings.enabled or settings.legacy_sort_migration_id:
		frappe.throw(frappe._("Touch migration is already active"))
	current = _source(lock=True)
	if _unchanged(current) != _unchanged(manifest["source"]):
		frappe.throw(
			frappe._("Migration sources changed; prepare a fresh manifest"), frappe.TimestampMismatchError
		)
	for dt, rows in current["targets"].items():
		for row, seed in zip(rows, manifest["seeds"][dt], strict=True):
			date, basis = _seed(row, current["history"], dt)
			if seed != {"name": row["name"], "date": date, "basis": basis}:
				frappe.throw(frappe._("Migration seed does not match its verified source"))
			date = max(
				get_datetime(date),
				get_datetime(row[touch.FIELD]) if row.get(touch.FIELD) else get_datetime(date),
			)
			frappe.db.set_value(dt, row["name"], touch.FIELD, date, update_modified=False)
	views = {}
	for view in current["views"]:
		changes = _view_changes(view)
		if changes:
			frappe.db.set_value("CRM View Settings", view["name"], changes, update_modified=False)
			views[str(view["name"])] = changes
	settings.enabled = settings.track_leads = settings.track_deals = 1
	settings.lead_status_changes = settings.deal_status_changes = 1
	for field in ADDITIONAL_POLICY_FIELDS:
		settings.set(field, "[]" if field.endswith(("_fields", "_events", "_channels")) else 0)
	settings.legacy_sort_retired = 1
	settings.legacy_sort_migration_id = manifest["id"]
	settings.legacy_sort_retired_at = now_datetime()
	settings.flags.touch_migration = True
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache(touch.SETTINGS)
	return {
		"id": manifest["id"],
		"already_applied": False,
		"seeded": {dt: len(rows) for dt, rows in current["targets"].items()},
		"views": views,
	}


@_transactional
def rollback(manifest):
	_permission()
	manifest = _manifest(manifest)
	settings = frappe.get_doc(touch.SETTINGS, for_update=True)
	if not settings.legacy_sort_migration_id:
		return {"already_rolled_back": True}
	if settings.legacy_sort_migration_id != manifest["id"]:
		frappe.throw(frappe._("The migration manifest does not own this cutover"))
	cutover = get_datetime(settings.legacy_sort_retired_at)
	current = _targets(lock=True)
	history = _history(lock=True)
	initial = {row["name"]: row for row in manifest["source"]["targets"]["CRM Lead"]}
	# Rebuild the old status-only date for newer genuine transitions. Do not copy
	# last_touch_at: it may now include comments, tasks or external interactions.
	if frappe.get_meta("CRM Lead").has_field(STATUS_SORT_FIELD):
		for row in current["CRM Lead"]:
			base = initial.get(row["name"], {})
			dates = [get_datetime(row["creation"])]
			if base.get(STATUS_SORT_FIELD):
				dates.append(get_datetime(base[STATUS_SORT_FIELD]))
			dates.extend(date for date in status_dates(history, "CRM Lead", row["name"]) if date >= cutover)
			frappe.db.set_value("CRM Lead", row["name"], STATUS_SORT_FIELD, max(dates), update_modified=False)
	restored, preserved = [], []
	current_views = {view["name"]: view for view in _views(lock=True)}
	for view in manifest["source"]["views"]:
		if view["name"] not in current_views:
			continue
		changes = _view_changes(view)
		current_view = current_views[view["name"]]
		for field, applied in changes.items():
			if current_view.get(field) == applied:
				frappe.db.set_value(
					"CRM View Settings", view["name"], field, view[field], update_modified=False
				)
				restored.append(f"{view['name']}:{field}")
			else:
				preserved.append(f"{view['name']}:{field}")
	settings.enabled = 0
	settings.legacy_sort_retired = 0
	settings.legacy_sort_migration_id = None
	settings.legacy_sort_retired_at = None
	settings.flags.touch_migration = True
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache(touch.SETTINGS)
	return {
		"already_rolled_back": False,
		"views_restored": restored,
		"new_view_choices_preserved": preserved,
		"touch_dates_and_audit_retained": True,
	}
