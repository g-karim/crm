from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from .config import CallAnalysisConfigurationError, get_config, get_public_status
from .tasks import enqueue_call_analysis


@frappe.whitelist()
def get_runtime_status() -> dict:
	return get_public_status()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60)
def start_analysis(call_log_name: str, force: int | str = 0) -> dict:
	call_log = frappe.get_doc("CRM Call Log", call_log_name)
	call_log.check_permission("write")
	if not call_log.recording_url:
		frappe.throw(_("This call has no recording to analyze."), frappe.ValidationError)

	try:
		get_config()
	except CallAnalysisConfigurationError as exc:
		frappe.throw(_(str(exc)), frappe.ValidationError)

	active = call_log.ai_analysis_status in {"Queued", "Processing"}
	if active:
		return {"queued": False, "status": call_log.ai_analysis_status}
	if call_log.ai_analysis_status == "Completed" and not cint(force):
		return {"queued": False, "status": "Completed"}

	return enqueue_call_analysis(call_log, frappe.session.user)
