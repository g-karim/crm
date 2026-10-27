"""Service-only storage; personal drafts never become ordinary CRM activities."""

from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe.model.document import Document

_writing = ContextVar("crm_call_work_storage", default=False)


@contextmanager
def internal_write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class PrivateCallStorage(Document):
	def validate(self):
		if not _writing.get():
			frappe.throw(frappe._("Call workspace storage is managed by CRM."), frappe.PermissionError)

	def on_trash(self):
		if not _writing.get():
			frappe.throw(frappe._("Call workspace storage is managed by CRM."), frappe.PermissionError)
