# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.model.document import Document


class CRMCallAnalysisSettings(Document):
	def validate(self):
		self.api_base_url = (self.api_base_url or "").strip().rstrip("/")
		self.transcription_model = (self.transcription_model or "").strip()
		self.summary_model = (self.summary_model or "").strip()

		if not self.enabled:
			return

		if not self.api_base_url:
			frappe.throw(_("Set the AI service URL before enabling call analysis."))

		parsed = urlsplit(self.api_base_url)
		if parsed.scheme not in {"http", "https"} or not parsed.hostname:
			frappe.throw(_("Enter a valid AI service URL."))

		if parsed.scheme != "https" and not (
			frappe.conf.developer_mode and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
		):
			frappe.throw(_("The AI service URL must use HTTPS."))

		if not self.transcription_model:
			frappe.throw(_("Set a transcription model before enabling call analysis."))
		if not self.summary_model:
			frappe.throw(_("Set a summary model before enabling call analysis."))
