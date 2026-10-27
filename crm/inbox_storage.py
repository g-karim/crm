"""Private inbox state is accessible only through its permission checked service."""

from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe.model.document import Document

_writing = ContextVar("crm_inbox_writing", default=False)


@contextmanager
def internal_write():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


class InboxStorage(Document):
	def validate(self):
		if not _writing.get():
			frappe.throw("Inbox state is managed by CRM.", frappe.PermissionError)

	def on_trash(self):
		self.validate()
