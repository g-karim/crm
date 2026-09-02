from __future__ import annotations

from dataclasses import dataclass

import frappe

DEFAULTS = {
	"api_base_url": "https://openrouter.ai/api/v1",
	"transcription_model": "openai/whisper-large-v3",
	"summary_model": "google/gemini-3.1-flash-lite-preview",
	"language": "Auto",
	"max_recording_mb": 25,
}


@dataclass(frozen=True)
class CallAnalysisConfig:
	enabled: bool
	api_base_url: str
	api_key: str
	transcription_model: str
	summary_model: str
	language: str
	max_recording_bytes: int


def get_settings():
	return frappe.get_cached_doc("CRM Call Analysis Settings")


def _value(settings, fieldname):
	value = settings.get(fieldname)
	return DEFAULTS.get(fieldname) if value in (None, "") else value


def get_config(*, require_enabled: bool = True) -> CallAnalysisConfig:
	settings = get_settings()
	api_key = settings.get_password("api_key", raise_exception=False) or ""
	config = CallAnalysisConfig(
		enabled=bool(settings.enabled),
		api_base_url=str(_value(settings, "api_base_url")).strip().rstrip("/"),
		api_key=api_key.strip(),
		transcription_model=str(_value(settings, "transcription_model")).strip(),
		summary_model=str(_value(settings, "summary_model")).strip(),
		language=str(_value(settings, "language")).strip() or "Auto",
		max_recording_bytes=max(1, min(int(_value(settings, "max_recording_mb")), 25)) * 1024 * 1024,
	)

	if require_enabled and not config.enabled:
		raise CallAnalysisConfigurationError("Call analysis is disabled.")
	if require_enabled and not config.api_key:
		raise CallAnalysisConfigurationError("The AI service API key is not configured.")
	return config


def get_public_status() -> dict:
	config = get_config(require_enabled=False)
	return {
		"enabled": config.enabled,
		"configured": bool(
			config.enabled
			and config.api_key
			and config.api_base_url
			and config.transcription_model
			and config.summary_model
		),
	}


class CallAnalysisConfigurationError(RuntimeError):
	pass
