"""Journal-equivalent server metrics and explicitly confirmed callback attempts."""

from collections import Counter, defaultdict
from statistics import median

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from crm.api import call_followups, call_work
from crm.api.telephony import filtered_query, get_call
from crm.call_work_storage import internal_write


def _seconds(value):
	try:
		return max(float(value or 0), 0)
	except (ValueError, TypeError):
		return 0


@frappe.whitelist()
def report(search="", view="all", period="30", mine=0, employee="", line="", outcome=""):
	from crm.api.telephony import MISSED_STATUSES

	rows = filtered_query(search, view, period, mine, employee, line, outcome).run(as_dict=True)
	names = [r.name for r in rows]
	groups = defaultdict(
		lambda: {"total": 0, "completed": 0, "missed": 0, "seconds": 0, "outcomes": Counter()}
	)
	days = defaultdict(lambda: {"total": 0, "completed": 0, "missed": 0})
	counts = Counter(total=len(rows), incoming=0, outgoing=0, completed=0, missed=0, recordings=0)
	seconds, durations = 0, []
	index = {r.name: r for r in rows}
	for row in rows:
		agent = row.receiver if row.type == "Incoming" else row.caller
		group = groups[agent or ""]
		day = str(row.start_time or row.creation)[:10]
		days[day]["total"] += 1
		group["total"] += 1
		counts["incoming" if row.type == "Incoming" else "outgoing"] += 1
		if row.status == "Completed":
			counts["completed"] += 1
			group["completed"] += 1
			days[day]["completed"] += 1
			duration = _seconds(row.duration)
			group["seconds"] += duration
			seconds += duration
			durations.append(duration)
		if row.type == "Incoming" and row.status in MISSED_STATUSES:
			counts["missed"] += 1
			group["missed"] += 1
			days[day]["missed"] += 1
		counts["recordings"] += bool(row.recording_url)
	t, task, link = (frappe.qb.DocType(n) for n in ("CRM Call Outcome", "CRM Task", "Dynamic Link"))
	calls = filtered_query(search, view, period, mine, employee, line, outcome, fields=["name"])
	reviews = (
		frappe.qb.from_(t)
		.select(t.star)
		.where(t.call_log.isin(calls) & t.name.isin(call_followups.review_query()))
		.run(as_dict=True)
	)
	outcomes, speeds = Counter(), []
	for review in reviews:
		outcomes[review.outcome] += 1
		row = index[review.call_log]
		agent = row.receiver if row.type == "Incoming" else row.caller
		groups[agent or ""]["outcomes"][review.outcome] += 1
		if review.callback_call and row.type == "Incoming" and row.status in MISSED_STATUSES:
			try:
				reply = get_call(review.callback_call)
				speed = (
					get_datetime(reply["timestamp"]) - get_datetime(row.start_time or row.creation)
				).total_seconds()
				if reply["type"] == "Outgoing" and speed >= 0:
					speeds.append(speed)
			except (frappe.PermissionError, frappe.DoesNotExistError):
				pass
	tasks = (
		frappe.qb.from_(link)
		.join(task)
		.on(link.link_name == task.name)
		.select(task.name, task.status, task.due_date)
		.where(
			(link.parenttype == "CRM Call Log")
			& (link.parentfield == "links")
			& (link.link_doctype == "CRM Task")
			& link.parent.isin(calls)
			& task.name.isin(call_followups.task_query())
		)
		.distinct()
		.run(as_dict=True)
	)
	task_counts = Counter(total=len(tasks), done=0, canceled=0, open=0, overdue=0)
	for item in tasks:
		key = "done" if item.status == "Done" else "canceled" if item.status == "Canceled" else "open"
		task_counts[key] += 1
		if key == "open" and item.due_date and get_datetime(item.due_date) < now_datetime():
			task_counts["overdue"] += 1
	return {
		"counts": dict(counts),
		"duration_seconds": seconds,
		"average_seconds": seconds / len(durations) if durations else None,
		"outcomes": dict(outcomes),
		"reviewed": len(reviews),
		"tasks": dict(task_counts),
		"callback_attempts": len(speeds),
		"callback_median_seconds": median(speeds) if speeds else None,
		"employees": [
			{
				"user": user,
				"label": frappe.db.get_value("User", user, "full_name") if user else _("Unassigned"),
				**value,
			}
			for user, value in sorted(groups.items(), key=lambda item: (-item[1]["total"], item[0]))
		],
		"days": [{"day": day, **value} for day, value in sorted(days.items())],
		"generated_at": str(now_datetime()),
		"scope": "permitted_imported_history",
		"matched_calls": len(names),
	}


@frappe.whitelist()
def callback_candidates(name):
	call = get_call(name)
	from crm.api.telephony import _base_query, _rows

	t = frappe.qb.DocType("CRM Call Log")
	# Candidates only; never auto-link by phone/time. The manager confirms identity.
	q = (
		_base_query()
		.where(
			(t.type == "Outgoing")
			& (t.name != name)
			& (t.to == call["number"])
			& (t.start_time >= call["timestamp"])
			& t.status.isin(call_followups.TERMINAL)
		)
		.orderby(t.start_time)
		.limit(20)
	)
	return _rows(q.run(as_dict=True))


@frappe.whitelist(methods=["POST"])
def link_callback(name, outgoing, expected_revision, expected_viewer):
	def action():
		call_work._require(expected_viewer)
		call_work._lock_author()
		from crm.integrations.exolve.api import _lock_call

		for identity in sorted({str(name), str(outgoing)}):
			_lock_call(identity)
		_call_doc, data = call_followups._call(name, write=True, lock=True)
		_reply_doc, reply_data = call_followups._call(outgoing, lock=True)
		review = call_followups._review(name, lock=True)
		call_followups._check_review_context(review, lock=True)
		if (
			not review
			or review.outcome != "Callback"
			or data["type"] != "Incoming"
			or data["status"] not in call_followups.TERMINAL[1:]
		):
			frappe.throw(_("Choose a missed call with a callback outcome."))
		if review.callback_call == outgoing:
			return {"linked": True}
		if str(review.revision) != str(expected_revision):
			frappe.throw(
				_("The call outcome changed in another window. Reload before saving."),
				frappe.TimestampMismatchError,
			)
		if (
			review.callback_call
			or reply_data["type"] != "Outgoing"
			or reply_data["status"] not in call_followups.TERMINAL
			or data["number"] != reply_data["number"]
			or get_datetime(reply_data["timestamp"]) < get_datetime(data["timestamp"])
		):
			frappe.throw(_("Choose an available later outgoing call to the same number."))
		review.callback_call, review.callback_linked_by, review.callback_linked_at = (
			outgoing,
			frappe.session.user,
			now_datetime(),
		)
		review.revision += 1
		with internal_write():
			review.save(ignore_permissions=True)
		return {"linked": True}

	return call_work._retry(action)


@frappe.whitelist()
def callback_status(name):
	data = get_call(name)
	review = call_followups._review(name)
	call_followups._check_review_context(review)
	applicable = bool(
		data["type"] == "Incoming"
		and data["status"] in call_followups.TERMINAL[1:]
		and review
		and review.outcome == "Callback"
	)
	result = {"applicable": applicable, "viewer": frappe.session.user}
	if not applicable:
		return result
	result.update(
		revision=review.revision,
		can_manage=frappe.has_permission("CRM Call Log", "write", frappe.get_doc("CRM Call Log", name)),
		linked="",
	)
	if review.callback_call:
		try:
			reply = get_call(review.callback_call)
			result["linked"] = str(reply["timestamp"])
		except (frappe.PermissionError, frappe.DoesNotExistError):
			result["linked"] = _("Linked call is no longer accessible.")
	else:
		result["candidates"] = callback_candidates(name)
	return result
