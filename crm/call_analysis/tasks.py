from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from .client import summarize_transcript, transcribe_recording
from .config import (
	CallAnalysisConfigurationError,
	get_config,
	get_user_analysis_language,
	normalize_analysis_language,
)
from .recording import RecordingDownloadError, download_recording

PROGRESS_EVENT = "crm_call_analysis_update"


def enqueue_call_analysis(call_log, user: str, *, language: str) -> dict:
	requested_on = now_datetime()
	call_log.db_set(
		{
			"ai_analysis_status": "Queued",
			"ai_analysis_requested_on": requested_on,
			"ai_analysis_started_on": None,
			"ai_analysis_requested_by": user,
			"ai_analysis_error": "",
		},
		update_modified=False,
	)
	job_id = f"crm-call-analysis-{call_log.name}"
	frappe.enqueue(
		"crm.call_analysis.tasks.run_call_analysis",
		queue="long",
		timeout=600,
		job_id=job_id,
		deduplicate=True,
		enqueue_after_commit=True,
		call_log_name=call_log.name,
		user=user,
		language=normalize_analysis_language(language),
	)
	return {"queued": True, "status": "Queued", "job_id": job_id}


def run_call_analysis(call_log_name: str, user: str | None = None, language: str | None = None):
	call_log = frappe.get_doc("CRM Call Log", call_log_name)
	_publish(call_log_name, "Processing", user)
	call_log.db_set(
		{
			"ai_analysis_status": "Processing",
			"ai_analysis_started_on": now_datetime(),
			"ai_analysis_error": "",
		},
		update_modified=False,
	)

	try:
		language = normalize_analysis_language(language) if language else get_user_analysis_language(user)
		config = get_config(language=language)
		recording = download_recording(call_log, max_bytes=config.max_recording_bytes)
		raw_transcript = transcribe_recording(
			recording.data,
			filename=recording.filename,
			content_type=recording.content_type,
			config=config,
		)
		call_log.db_set("ai_transcript", raw_transcript, update_modified=False)

		analysis = summarize_transcript(raw_transcript, config=config)
		call_log.db_set(
			{
				"ai_analysis_status": "Completed",
				"ai_analyzed_on": now_datetime(),
				"ai_analysis_language": config.language,
				"ai_transcription_model": config.transcription_model,
				"ai_summary_model": config.summary_model,
				"ai_transcript": analysis.transcript,
				"ai_summary": analysis.summary,
				"ai_key_points": frappe.as_json(analysis.key_points),
				"ai_next_steps": frappe.as_json(analysis.next_steps),
				"ai_sentiment": analysis.sentiment,
				"ai_analysis_error": "",
			},
			update_modified=False,
		)
		_publish(call_log_name, "Completed", user)
		return {"status": "Completed"}
	except Exception as exc:
		message = _safe_user_error(exc)
		call_log.db_set(
			{"ai_analysis_status": "Failed", "ai_analysis_error": message},
			update_modified=False,
		)
		frappe.log_error(
			title=f"CRM call analysis failed: {call_log_name}",
			message=f"{type(exc).__name__}: {message}",
		)
		_publish(call_log_name, "Failed", user)
		return {"status": "Failed"}


def _safe_user_error(exc: Exception) -> str:
	if isinstance(exc, (CallAnalysisConfigurationError, RecordingDownloadError)):
		message = str(exc or "").strip()
		if message:
			return message
	return "The AI service could not analyze this recording. Please try again."


def _publish(call_log_name: str, status: str, user: str | None):
	try:
		frappe.publish_realtime(
			PROGRESS_EVENT,
			{"call_log_name": call_log_name, "status": status},
			user=user,
		)
	except Exception:
		pass
