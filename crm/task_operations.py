"""Private HTTP retry receipts. No task content or access grants."""
from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe.model.document import Document

_writing = ContextVar("crm_task_operation_write", default=False)


@contextmanager
def internal_write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class CRMTaskOperation(Document):
	def validate(self):
		if not _writing.get() or not self.is_new():
			frappe.throw(frappe._("Task operations are managed by CRM."), frappe.PermissionError)


def changed(doc, method=None):
	from crm.api.celio_tasks import readable

	users = set(frappe.get_all("Has Role", filters={"role": ["in", ["Sales User", "Sales Manager", "System Manager"]]}, pluck="parent", limit=0))
	users.add("Administrator")
	for user in users:
		if readable(doc, user):
			frappe.publish_realtime("crm_tasks_changed", {}, user=user, after_commit=True)
