from __future__ import annotations

import frappe
from frappe.utils import flt

from .config import CallAnalysisConfigurationError, get_config, get_user_analysis_language
from .tasks import enqueue_call_analysis

MIN_AUTO_ANALYSIS_SECONDS = 10


def should_auto_analyze(call_log) -> bool:
	if call_log.status != "Completed" or not call_log.recording_url:
		return False
	if call_log.ai_analysis_status:
		return False

	duration = flt(call_log.duration)
	return not duration or duration >= MIN_AUTO_ANALYSIS_SECONDS


def get_analysis_user(call_log) -> str:
	participants = (
		(call_log.receiver, call_log.caller)
		if call_log.type == "Incoming"
		else (call_log.caller, call_log.receiver)
	)
	for user in (*participants, call_log.owner):
		if user and user != "Guest":
			return user
	return "Administrator"


def maybe_enqueue_call_analysis(call_log, method: str | None = None):
	if not should_auto_analyze(call_log):
		return None

	try:
		user = get_analysis_user(call_log)
		language = get_user_analysis_language(user)
		get_config(language=language)
		return enqueue_call_analysis(call_log, user, language=language)
	except CallAnalysisConfigurationError:
		return None
	except Exception:
		frappe.log_error(
			title=f"Could not enqueue automatic call analysis: {call_log.name}",
			message=frappe.get_traceback(),
		)
		return None
