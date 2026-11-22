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

	previous = doc.get_doc_before_save()
	users = {frappe.session.user, doc.assigned_to, previous.assigned_to if previous else None}
	for user in users - {None, ""}:
		if readable(doc, user):
			frappe.publish_realtime("crm_tasks_changed", {}, user=user, after_commit=True)
