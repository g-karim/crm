"""Internal CRM rules. Hooks preserve the original document/assignment behavior.

Mutable sources (especially tasks without Versions) have a minimal durable change
log in the business transaction. Workers update the parent only after commit:
a task/comment save never takes an additional parent lock in reverse order.
"""

import json
from decimal import Decimal

import frappe
from frappe.utils import cint, get_datetime, getdate, now_datetime

from crm import touch_tracking as touch

CHANGE = "CRM Touch Change"
INTERNAL_EVENTS = (
	"comment_created",
	"comment_edited",
	"note_created",
	"note_edited",
	"task_created",
	"task_completed",
	"task_status",
	"task_due_date",
	"task_start_date",
	"task_priority",
	"task_assigned_to",
	"task_title",
	"task_description",
	"task_comment",
)
ADDITIONAL_POLICY_FIELDS = tuple(
	f"{prefix}_{suffix}"
	for prefix in ("lead", "deal")
	for suffix in (
		"fields",
		"events",
		"allow_automation",
		"channels",
		"messenger_automation",
		"email_automation",
	)
)
EXCLUDED_FIELDS = {
	"status",
	"naming_series",
	"lead_name",
	"deal_name",
	"organization_name",
	"organization_logo",
	"converted",
	"lead",
	"sla",
	"communication_status",
	"pipeline_label",
	"status_label",
	"external_source",
	"exchange_rate",
	"custom_crm_status_sort_date",
	touch.FIELD,
}
FIELD_TYPES = {
	"Data",
	"Link",
	"Select",
	"Check",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Date",
	"Datetime",
	"Time",
	"Small Text",
	"Text",
	"Long Text",
	"Text Editor",
}


def available_fields(doctype):
	"""Server-side allowlist from site metadata; tables/derived/secret fields excluded."""
	if doctype not in touch.TARGETS:
		return {}
	return {
		field.fieldname: field
		for field in frappe.get_meta(doctype).fields
		if field.fieldname not in EXCLUDED_FIELDS
		and not field.fieldname.startswith(("_", "external_", "facebook_", "sla_"))
		and field.fieldtype in FIELD_TYPES
		and not (field.read_only or field.is_virtual or field.fetch_from)
	}


def selections(value):
	if value in (None, ""):
		return []
	parsed = json.loads(value) if isinstance(value, str) else value
	if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
		raise ValueError("Touch selections must be a list of names")
	return sorted(set(parsed))


def policy_values(doc, *, validate=True):
	from crm.touch_tracking_channels import CHANNEL_RULES, validate_channel_rules

	values = {field: cint(doc.get(field)) for field in touch.POLICY_FIELDS}
	for prefix, doctype in (("lead", "CRM Lead"), ("deal", "CRM Deal")):
		for suffix, allowed in (("fields", available_fields(doctype)), ("events", INTERNAL_EVENTS)):
			field = f"{prefix}_{suffix}"
			try:
				selected = selections(doc.get(field))
			except (ValueError, TypeError):
				frappe.throw(frappe._("Invalid touch selections for {0}").format(field))
			if validate and any(name not in allowed for name in selected):
				frappe.throw(frappe._("Unsupported touch selection for {0}").format(field))
			values[field] = json.dumps(selected)
		values[f"{prefix}_allow_automation"] = cint(doc.get(f"{prefix}_allow_automation"))
		try:
			selected = selections(doc.get(f"{prefix}_channels"))
		except (ValueError, TypeError):
			frappe.throw(frappe._("Invalid touch selections for {0}").format(f"{prefix}_channels"))
		if validate:
			validate_channel_rules(doc, prefix, selected)
		elif any(rule not in CHANNEL_RULES for rule in selected):
			selected = [rule for rule in selected if rule in CHANNEL_RULES]
		values[f"{prefix}_channels"] = json.dumps(selected)
		for channel in ("messenger", "email"):
			values[f"{prefix}_{channel}_automation"] = cint(doc.get(f"{prefix}_{channel}_automation"))
	return values


def normalized(value, field):
	if field.fieldtype in ("Check", "Int"):
		return cint(value)
	if field.fieldtype in ("Float", "Currency", "Percent"):
		return Decimal(str(value or 0))
	if value in (None, ""):
		return None
	if field.fieldtype == "Date":
		return getdate(value)
	if field.fieldtype == "Datetime":
		return get_datetime(value)
	# Do not collapse whitespace/HTML that may be meaningful to the user.
	return str(value)


def changed(doc, previous, fieldname):
	field = doc.meta.get_field(fieldname)
	return field and normalized(doc.get(fieldname), field) != normalized(previous.get(fieldname), field)


def operation_origin():
	# Background/import actions are not classified from modified_by. Authenticated
	# session requests include normal card/list/API operations. Token API calls and
	# Python calls without a request are conservative automation by default.
	request = getattr(frappe.local, "request", None)
	if (
		frappe.flags.in_import
		or frappe.flags.in_patch
		or frappe.flags.in_migrate
		or frappe.flags.in_safe_exec
		or getattr(frappe.local, "job", None)
		or not request
		or frappe.session.user == "Guest"
		or request.headers.get("Authorization")
	):
		return "Automation"
	return "User"


def current_policy(doctype, occurred_at):
	if not frappe.db.table_exists(touch.POLICY):
		return None  # Shared app code can precede migration of this site.
	settings = frappe.get_cached_doc(touch.SETTINGS)
	if not settings.policy_revision or not touch.policy_accepts(settings, doctype, "Created"):
		return None
	return touch.policy_at(touch._policies(), occurred_at)


def selected_reasons(policy, doctype, reasons, origin):
	if not touch.policy_accepts(policy, doctype, "Created"):
		return []
	prefix = "lead" if doctype == "CRM Lead" else "deal"
	if origin != "User" and not cint(policy.get(f"{prefix}_allow_automation")):
		return []
	fields = set(selections(policy.get(f"{prefix}_fields"))) & available_fields(doctype).keys()
	events = set(selections(policy.get(f"{prefix}_events")))
	return sorted(
		{
			reason
			for reason in reasons
			if (reason.removeprefix("field:") in fields if reason.startswith("field:") else reason in events)
		}
	)


def remember_card_input(doc, method=None):
	"""Record explicit input before validate derives other business values."""
	doc.flags.touch_input_fields = []
	if not doc.meta.has_field(touch.FIELD):
		return
	previous = doc.get_doc_before_save()
	if not previous:
		return
	try:
		prefix = "lead" if doc.doctype == "CRM Lead" else "deal"
		settings = frappe.get_cached_doc(touch.SETTINGS)
		if not settings.enabled or not selections(settings.get(f"{prefix}_fields")):
			return
		policy = current_policy(doc.doctype, doc.modified)
		if policy:
			doc.flags.touch_input_fields = [
				name
				for name in selections(policy.get(f"{prefix}_fields"))
				if name in available_fields(doc.doctype) and changed(doc, previous, name)
			]
	except Exception as exc:
		_fail("card input", exc)


def capture_card_update(doc):
	previous = doc.get_doc_before_save()
	if not previous or doc.flags.in_insert or not doc.flags.touch_input_fields:
		return False
	try:
		origin = operation_origin()
		policy = current_policy(doc.doctype, doc.modified)
		reasons = selected_reasons(
			policy,
			doc.doctype,
			[f"field:{name}" for name in doc.flags.touch_input_fields or [] if changed(doc, previous, name)],
			origin,
		)
		if not reasons:
			return False
		status_changed = previous.status != doc.status and touch.policy_accepts(
			policy, doc.doctype, "Status Changed"
		)
		if status_changed:
			row = doc.status_change_log[-1]
			reasons.append("status_changed")
			kind, source_type, source_name, revision = "Status Changed", row.doctype, row.name, None
		else:
			kind, source_type, source_name, revision = (
				"Internal Changed",
				doc.doctype,
				doc.name,
				str(doc.modified),
			)
		store_change(
			doc.doctype,
			doc.name,
			kind,
			source_type,
			source_name,
			revision,
			doc.modified,
			doc.modified_by,
			policy,
			reasons,
			origin,
			immediate=True,
		)
		doc.set(touch.FIELD, frappe.db.get_value(doc.doctype, doc.name, touch.FIELD))
		return True
	except Exception as exc:
		_fail("card change", exc)
		return False


def capture_internal(doc, method=None):
	"""on_update also runs on insert; use Frappe's insert flag to avoid double capture."""
	if not frappe.db.table_exists(CHANGE):
		return
	try:
		previous = None if doc.flags.in_insert else doc.get_doc_before_save()
		reasons = []
		if doc.doctype == "Comment":
			if doc.comment_type != "Comment" or (previous and previous.comment_type != "Comment"):
				return
			doctype, name = doc.reference_doctype, doc.reference_name
			if doctype == "CRM Task":
				# Task comments are creation only, never parent comment rules.
				if previous:
					return
				task = frappe.db.get_value(
					"CRM Task", name, ["reference_doctype", "reference_docname"], as_dict=True
				)
				if not task:
					return
				doctype, name = task.reference_doctype, task.reference_docname
				reasons = ["task_comment"]
			elif not previous:
				reasons = ["comment_created"]
			elif changed(doc, previous, "content"):
				reasons = ["comment_edited"]
		else:
			doctype, name = doc.reference_doctype, doc.reference_docname
			if doc.doctype == "FCRM Note":
				if not previous:
					reasons = ["note_created"]
				elif any(changed(doc, previous, field) for field in ("title", "content")):
					reasons = ["note_edited"]
			elif doc.doctype == "CRM Task":
				if not previous:
					reasons = ["task_created"]
				else:
					if changed(doc, previous, "status"):
						reasons.append("task_completed" if doc.status == "Done" else "task_status")
					reasons.extend(
						f"task_{field}"
						for field in (
							"due_date",
							"start_date",
							"priority",
							"assigned_to",
							"title",
							"description",
						)
						if changed(doc, previous, field)
					)
		if doctype not in touch.TARGETS or not name or not reasons:
			return
		occurred_at = doc.modified if previous else doc.creation
		origin = operation_origin()
		policy = current_policy(doctype, occurred_at)
		reasons = selected_reasons(policy, doctype, reasons, origin)
		if reasons:
			store_change(
				doctype,
				name,
				"Internal Changed",
				doc.doctype,
				doc.name,
				str(occurred_at),
				occurred_at,
				doc.modified_by,
				policy,
				reasons,
				origin,
			)
	except Exception as exc:
		_fail("internal change", exc)


def owner_assignment(doc, fieldname, old_value, new_value):
	"""Called only after CRM's native ToDo mirror wrote the actual owner value."""
	if (doc.reference_type, doc.reference_name) in (frappe.flags.currently_saving or []):
		return  # The parent save groups this field with its other selected inputs.
	if (old_value or None) == (new_value or None):
		return
	try:
		origin, occurred_at = operation_origin(), doc.modified
		policy = current_policy(doc.reference_type, occurred_at)
		reasons = selected_reasons(policy, doc.reference_type, [f"field:{fieldname}"], origin)
		if reasons:
			store_change(
				doc.reference_type,
				doc.reference_name,
				"Internal Changed",
				doc.doctype,
				doc.name,
				str(doc.modified),
				occurred_at,
				doc.modified_by,
				policy,
				reasons,
				origin,
			)
	except Exception as exc:
		_fail("assignment", exc)


def store_change(
	doctype,
	name,
	kind,
	source_type,
	source_name,
	revision,
	occurred_at,
	actor,
	policy,
	reasons,
	origin,
	*,
	immediate=False,
):
	key = touch.event_key(doctype, name, kind, source_type, source_name, revision)
	if not frappe.db.exists(CHANGE, key):
		values = dict(
			doctype=CHANGE,
			reference_doctype=doctype,
			reference_name=name,
			event_type=kind,
			source_doctype=source_type,
			source_name=source_name,
			source_revision=revision,
			occurred_at=occurred_at,
			actor=actor,
			policy_revision=policy.name,
			reasons=json.dumps(sorted(set(reasons))),
			origin=origin,
		)
		point = "touch_source_" + frappe.generate_hash(length=10)
		frappe.db.savepoint(point)
		try:
			change = frappe.get_doc(values)
			change.flags.touch_internal = True
			change.insert(ignore_permissions=True)
		except Exception as exc:
			if touch._transaction_failure(exc):
				raise
			frappe.db.rollback(save_point=point)
			raise
	try:
		materialize_change(frappe.get_doc(CHANGE, key))
		if immediate:
			touch._apply_safely(key)
		else:
			# Outbox rows are durable even if Redis/queue submission is unavailable.
			frappe.db.after_commit.add(_enqueue_safely)
	except Exception as exc:
		_fail("change processing", exc)
	return key


def _enqueue_safely():
	try:
		frappe.enqueue("crm.touch_tracking.maintenance")
	except Exception:
		# A Redis failure after commit must not report a saved task as failed.
		# The scheduler still has the transactional source/Pending event to retry.
		touch._diagnose("queue submission")


def materialize_change(change):
	return touch._record_event(
		change.reference_doctype,
		change.reference_name,
		change.event_type,
		change.source_doctype,
		change.source_name,
		change.occurred_at,
		change.actor,
		frappe._dict(name=change.policy_revision),
		source_revision=change.source_revision,
		reasons=selections(change.reasons),
		origin=change.origin,
	)


def recover_changes(limit=100):
	if not frappe.db.table_exists(CHANGE):
		return 0
	rows = frappe.db.sql(
		"""SELECT c.name FROM `tabCRM Touch Change` c
		LEFT JOIN `tabCRM Touch Event` e ON e.name = c.name
		WHERE e.name IS NULL ORDER BY c.occurred_at, c.name LIMIT %s""",
		(cint(limit),),
		as_dict=True,
	)
	count = 0
	for row in rows:
		try:
			materialize_change(frappe.get_doc(CHANGE, row.name))
			count += 1
		except Exception as exc:
			_fail("change recovery", exc)
	return count


def _fail(operation, exc):
	if touch._transaction_failure(exc):
		raise exc
	touch._diagnose(operation)
