import frappe

from crm.call_work_storage import PrivateCallStorage


class CRMCallAnalysis(PrivateCallStorage):
	def validate(self):
		super().validate()
		old = self.get_doc_before_save()
		if not old:
			return
		identity = (
			"call_log",
			"requested_by",
			"mutation_id",
			"recording_source",
			"reference_doctype",
			"reference_docname",
		)
		once = (
			"raw_transcript",
			"segments",
			"stt_response",
			"recording_hash",
			"summary_response",
			"summary_json",
		)
		for field in (*identity, *(key for key in once if old.get(key))):
			if self.get(field) != old.get(field):
				frappe.throw(frappe._("Original call analysis is immutable. Create a new analysis version."))
