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


@frappe.whitelist()
def get_analysis_settings() -> dict:
	frappe.only_for("System Manager")
	config = get_config(require_enabled=False)
	return {
		"enabled": config.enabled,
		"api_base_url": config.api_base_url,
		"api_key_configured": bool(config.api_key),
		"transcription_model": config.transcription_model,
		"summary_model": config.summary_model,
		"language": config.language,
		"max_recording_mb": config.max_recording_bytes // (1024 * 1024),
	}


@frappe.whitelist(methods=["POST"])
def save_analysis_settings(
	enabled: int | str = 0,
	api_base_url: str = "",
	api_key: str = "",
	transcription_model: str = "",
	summary_model: str = "",
	language: str = "Auto",
	max_recording_mb: int | str = 25,
) -> dict:
	frappe.only_for("System Manager")
	settings = frappe.get_single("CRM Call Analysis Settings")
	settings.enabled = cint(enabled)
	settings.api_base_url = api_base_url
	settings.transcription_model = transcription_model
	settings.summary_model = summary_model
	settings.language = language if language in {"Auto", "Russian", "English"} else "Auto"
	settings.max_recording_mb = max(1, min(cint(max_recording_mb) or 25, 25))
	if api_key:
		settings.api_key = api_key
	settings.save()
	frappe.clear_document_cache("CRM Call Analysis Settings")
	return get_analysis_settings()


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
