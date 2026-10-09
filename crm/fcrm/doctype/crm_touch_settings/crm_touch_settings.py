from datetime import timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime

from crm.touch_tracking import POLICY
from crm.touch_tracking_internal import policy_values


class CRMTouchSettings(Document):
	def validate(self):
		if self.enabled and frappe.db.db_type != "mariadb":
			frappe.throw(frappe._("Touch tracking currently requires MariaDB"))
		previous = self.get_doc_before_save()
		if not self.flags.touch_migration:
			for field in ("legacy_sort_retired", "legacy_sort_migration_id", "legacy_sort_retired_at"):
				self.set(field, previous.get(field) if previous else None)
		values = policy_values(self)
		self.update(values)
		self.policy_revision = previous.policy_revision if previous else None
		if self.policy_revision and values == policy_values(previous, validate=False):
			return
		# Snapshots are transactional with settings and append-only. This also
		# supplies a durable decision for recovering a failed business-event insert.
		latest = frappe.get_all(POLICY, fields=["effective_from"], order_by="effective_from desc", limit=1)
		effective_from = get_datetime(self.modified)
		if latest and effective_from <= get_datetime(latest[0].effective_from):
			effective_from = get_datetime(latest[0].effective_from) + timedelta(microseconds=1)
		policy = frappe.get_doc(
			{
				"doctype": POLICY,
				"effective_from": effective_from,
				**values,
			}
		)
		policy.flags.touch_internal = True
		policy.insert(ignore_permissions=True)
		self.policy_revision = policy.name
