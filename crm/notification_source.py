"""CRM-owned projection and native read state for the optional EXP service."""

import json
from hashlib import sha256
from urllib.parse import quote

import frappe
from frappe.utils import cint, strip_html_tags

from crm.fcrm.doctype.crm_notification.crm_notification import can_access_notification


class CRMNotifications:
	key = "crm"
	label = "EXP CRM"

	def _record(self, name, user, for_update=False):
		row = frappe.db.get_value(
			"CRM Notification", {"name": name, "to_user": user}, "*", as_dict=True, for_update=for_update
		)
		if not row or not frappe.db.get_value("User", user, "enabled"):
			return None
		return row if can_access_notification(row, user=user) else None

	def get(self, name, user):
		from exp_theme.notifications.access import event_time

		row = self._record(name, user)
		if not row:
			return None
		facts = json.loads(row.exp_notification_snapshot) if row.get("exp_notification_snapshot") else None
		return {
			"id": f"crm:{row.name}",
			"source": self.key,
			"source_label": self.label,
			"record_id": row.name,
			"event_id": row.last_event_id or row.name,
			"head": notification_head(row),
			"event_type": facts["event"]
			if facts and facts["event"] != "task_assigned"
			else "assignment"
			if row.type == "Assignment"
			else "other",
			"_crm_snapshot": facts,
			"one_push_permitted": self._one_push(facts, user),
			"recipient": row.to_user,
			"actor": row.from_user,
			"occurred_at": event_time(row.last_event_at or row.creation).isoformat(),
			"is_read": bool(row.read),
			"event_count": max(cint(row.event_count), 1) if row.type == "Messenger" else 1,
			"title": " ".join(
				strip_html_tags(row.notification_text or row.message or frappe._("Notification")).split()
			),
			"presentation": self._presentation(row, user),
			"route": notification_route(row),
			"push_route": "/crm/tasks?open=" + quote(str(row.notification_type_doc), safe="")
			if row.notification_type_doctype == "CRM Task"
			else notification_route(row),
		}

	def _presentation(self, row, user):
		from exp_theme.notifications.presentation import person_name, plain

		if user != frappe.session.user:
			return {}  # Background transports do not need private display fields.
		data = {"actor_name": person_name(row.from_user), "fields": []}
		language = frappe.get_cached_value("User", user, "language")
		if row.notification_type_doctype == "CRM Task":
			task = frappe.get_doc("CRM Task", row.notification_type_doc)
			task.apply_fieldlevel_read_permissions()
			data.update(subject=plain(task.get("title"), 240), preview=plain(task.get("description")))
			data["fields"].append(
				{
					"label": frappe._("Task status", lang=language),
					"value": frappe._(task.get("status") or "", lang=language),
				}
			)
		if row.reference_doctype in {"CRM Lead", "CRM Deal"} and row.reference_name:
			reference = frappe.get_doc(row.reference_doctype, row.reference_name)
			reference.apply_fieldlevel_read_permissions()
			data["context"] = plain(reference.get(reference.meta.title_field), 160)
			data["fields"].append({"label": frappe._("Related to", lang=language), "value": data["context"]})
		return data

	def list(self, user):
		rows = frappe.get_all("CRM Notification", filters={"to_user": user}, pluck="name", limit=0)
		return [item for name in rows if (item := self.get(name, user))]

	def mark_read(self, name, user, observed_head):
		from crm.api.notifications import _mark_locked_notification_read

		row = self._record(name, user, for_update=True)
		if not row or row.read or notification_head(row) != observed_head:
			return False
		_mark_locked_notification_read(name)
		return True

	def delivery_allowed(self, item, user):
		row = self._record(item["record_id"], user)
		assignment = bool(
			row
			and row.type == "Assignment"
			and row.notification_type_doctype in {"CRM Lead", "CRM Deal", "CRM Task"}
			and (row.last_event_id or "").startswith("crm-assignment:")
			and row.last_event_id.endswith(":assigned")
		)
		transition = bool(
			row
			and row.type == "Status Change"
			and row.notification_type_doctype in {"CRM Lead", "CRM Deal"}
			and (row.last_event_id or "").startswith(("crm-lead-status:", "crm-deal-stage:"))
			and item.get("_crm_snapshot")
		)
		reminder = bool(
			row
			and row.type == "Reminder"
			and row.notification_type_doctype == "CRM Task"
			and (row.last_event_id or "").startswith(("crm-task-reminder:", "crm-personal-reminder:"))
			and item.get("_crm_snapshot")
		)
		discussion = bool(
			row
			and row.type in {"Mention", "Comment"}
			and row.notification_type_doctype == "Comment"
			and (row.last_event_id or "").startswith("crm-comment:")
			and item.get("_crm_snapshot")
		)
		incoming = bool(
			row
			and row.type == "Message"
			and row.notification_type_doctype == "Communication"
			and (row.last_event_id or "").startswith("crm-incoming:Communication:")
			and item.get("_crm_snapshot")
		)
		idle = bool(
			row
			and row.type == "Reminder"
			and row.notification_type_doctype in {"CRM Lead", "CRM Deal"}
			and (row.last_event_id or "").startswith("crm-inactivity:")
			and item.get("_crm_snapshot")
		)
		return assignment or transition or reminder or discussion or incoming or idle

	def channel_delivery_allowed(self, item, user, channel):
		from crm.notification_rules.engine import permitted

		return permitted(item, user, channel, lock=True)

	def allows_self(self, item, user):
		return any(
			self.channel_delivery_allowed(item, user, channel)
			for channel in ("source_push", "one_message", "email")
		)

	def _one_push(self, facts, user):
		from crm.notification_rules.engine import permitted

		return permitted({"_crm_snapshot": facts}, user, "one_message_push") if facts else True


def make_source():
	return CRMNotifications()


def notification_head(row):
	# The head changes when an aggregate receives a new event, not when it is read.
	parts = [
		row.name,
		row.get("last_event_id"),
		row.get("last_event_at"),
		max(cint(row.get("event_count")), 1),
		row.get("creation"),
	]
	return sha256("\0".join(str(part or "") for part in parts).encode()).hexdigest()


def notification_route(row):
	from crm.api.notifications import get_hash

	if row.notification_type_doctype == "CRM Task":
		return "/crm/tasks?open=" + quote(str(row.notification_type_doc), safe="")

	if row.reference_doctype in {"CRM Lead", "CRM Deal"} and row.reference_name:
		route = "leads" if row.reference_doctype == "CRM Lead" else "deals"
		path = f"/crm/{route}/{quote(str(row.reference_name), safe='')}{get_hash(row)}"
		if row.type == "Messenger" and row.notification_type_doc:
			path = path.replace(
				"#messenger",
				"?messenger_conversation=" + quote(str(row.notification_type_doc), safe="") + "#messenger",
			)
		return path
	return "/crm/tasks" if row.notification_type_doctype == "CRM Task" else "/crm"


def changed(doc, method=None):
	if (doc.to_user and "exp_theme" in frappe.get_installed_apps()
		and frappe.db.table_exists("EXP Notification Subscription")):
		from exp_theme.notifications.access import changed as notify_changed

		notify_changed(doc.to_user)


def publish(doc, method=None):
	if "exp_theme" not in frappe.get_installed_apps():
		return
	if doc.type in {"Assignment", "Status Change", "Reminder", "Mention", "Comment", "Message"}:
		if frappe.db.table_exists("EXP Notification Delivery"):
			from exp_theme.notifications.delivery import publish as publish_delivery

			publish_delivery("crm", doc.name, doc.to_user)
		if frappe.db.table_exists("EXP Push Delivery"):
			from exp_theme.notifications.push.delivery import publish as publish_push

			publish_push("crm", doc.name, doc.to_user)
		from exp_theme.notifications.email_channel import publish as publish_email

		publish_email("crm", doc.name, doc.to_user)
