"""Private retry receipts; native FCRM Note remains the content owner."""
from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe.model.document import Document

_writing = ContextVar("crm_note_operation_write", default=False)


@contextmanager
def internal_write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class CRMNoteOperation(Document):
	def validate(self):
		if not _writing.get() or not self.is_new():
			frappe.throw(frappe._("Note operations are managed by CRM."), frappe.PermissionError)
