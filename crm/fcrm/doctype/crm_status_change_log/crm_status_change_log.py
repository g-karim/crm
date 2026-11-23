# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime


class CRMStatusChangeLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		duration: DF.Duration | None
		from_date: DF.Datetime | None
		from_type: DF.Data | None
		last_status_change_log: DF.Link | None
		log_owner: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		to: DF.Data | None
		to_date: DF.Datetime | None
		to_type: DF.Data | None
	# end: auto-generated types

	pass


def get_duration(from_date, to_date):
	if not isinstance(from_date, datetime):
		from_date = get_datetime(from_date)
	if not isinstance(to_date, datetime):
		to_date = get_datetime(to_date)
	duration = to_date - from_date
	return duration.total_seconds()


def add_status_change_log(doc, at=None, at_utc=None):
	change_time = get_datetime(at) if at else datetime.now()
	to_status_type = frappe.db.get_value("CRM Deal Status", doc.status, "type") if doc.status else None

	if not doc.is_new():
		previous_status = doc.get_doc_before_save().status if doc.get_doc_before_save() else None
		previous_status_type = (
			frappe.db.get_value("CRM Deal Status", previous_status, "type") if previous_status else None
		)
		if not doc.status_change_log and previous_status:
			now_minus_one_minute = add_to_date(change_time, minutes=-1)
			doc.append(
				"status_change_log",
				{
					"from": previous_status,
					"from_type": previous_status_type or "",
					"to": "",
					"to_type": "",
					"from_date": now_minus_one_minute,
					"to_date": "",
					"log_owner": frappe.session.user,
				},
			)
		last_status_change = doc.status_change_log[-1]
		last_status_change.to = doc.status
		last_status_change.to_type = to_status_type or ""
		last_status_change.to_date = change_time
		last_status_change.log_owner = frappe.session.user
		from crm.analytics.history import EVENT
		from crm.analytics.source_event_import import event_instant, utc_now
		absolute_now = at_utc
		if absolute_now is None and frappe.db.table_exists(EVENT):
			latest = frappe.get_all(EVENT, filters={"source_type": "CRM Deal", "source_name": doc.name},
				fields=["payload"], order_by="sequence desc", limit_page_length=1)
			if latest:
				payload = frappe.parse_json(latest[0].payload)
				if payload.get("occurred_at_utc") or (payload.get("source_event") or {}).get("occurred_at_utc"):
					absolute_now = utc_now()
		if absolute_now is not None:
			# Status log dates are Frappe local datetimes. During a repeated
			# hour, wall-clock subtraction can even yield a negative duration.
			rows = frappe.get_all(EVENT, filters={"source_type": "CRM Deal", "source_name": doc.name},
				fields=["occurred_at", "payload"], order_by="sequence desc", limit_page_length=0)
			previous_entry = next((row for row in rows if (
				(payload := frappe.parse_json(row.payload)).get("after") or {}).get("status") == previous_status
				and (payload.get("before") or {}).get("status") != previous_status), None)
			if previous_entry:
				last_status_change.duration = (absolute_now - event_instant(previous_entry)).total_seconds()
			else:
				# The old wall time cannot safely identify a fold. Leave an
				# unknown duration unknown instead of inventing one.
				last_status_change.duration = None
		else:
			last_status_change.duration = get_duration(last_status_change.from_date, last_status_change.to_date)

	doc.append(
		"status_change_log",
		{
			"from": doc.status,
			"from_type": to_status_type or "",
			"to": "",
			"to_type": "",
			"from_date": change_time,
			"to_date": "",
			"log_owner": frappe.session.user,
		},
	)
