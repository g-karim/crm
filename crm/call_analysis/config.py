from __future__ import annotations

import os
from dataclasses import dataclass

import frappe
from frappe.translate import get_user_lang

DEFAULTS = {
	"api_base_url": "https://openrouter.ai/api/v1",
	"transcription_model": "openai/whisper-large-v3",
	"summary_model": "google/gemini-3.1-flash-lite-preview",
	"max_recording_mb": 25,
}
API_KEY_ENV = "CRM_CALL_ANALYSIS_API_KEY"
API_KEY_CONFIG = "crm_call_analysis_api_key"
PROXY_URL_ENV = "CRM_CALL_ANALYSIS_PROXY_URL"
PROXY_URL_CONFIG = "crm_call_analysis_proxy_url"
VOICE_TRANSCRIPTION_PROXY_URL_CONFIG = "voice_transcription_proxy_url"


@dataclass(frozen=True)
class CallAnalysisConfig:
	api_base_url: str
	api_key: str
	proxy_url: str
	transcription_model: str
	summary_model: str
	language: str
	max_recording_bytes: int


def normalize_analysis_language(language: str | None) -> str:
	value = str(language or "").strip().lower().replace("_", "-")
	return "Russian" if value == "russian" or value.startswith("ru") else "English"


def get_user_analysis_language(user: str | None = None) -> str:
	return normalize_analysis_language(get_user_lang(user))


def get_config(*, language: str | None = None, require_api_key: bool = True) -> CallAnalysisConfig:
	api_key = os.getenv(API_KEY_ENV) or frappe.conf.get(API_KEY_CONFIG) or ""
	proxy_url = (
		os.getenv(PROXY_URL_ENV)
		or frappe.conf.get(PROXY_URL_CONFIG)
		or frappe.conf.get(VOICE_TRANSCRIPTION_PROXY_URL_CONFIG)
		or ""
	)
	config = CallAnalysisConfig(
		api_base_url=DEFAULTS["api_base_url"],
		api_key=str(api_key).strip(),
		proxy_url=str(proxy_url).strip(),
		transcription_model=DEFAULTS["transcription_model"],
		summary_model=DEFAULTS["summary_model"],
		language=normalize_analysis_language(language),
		max_recording_bytes=DEFAULTS["max_recording_mb"] * 1024 * 1024,
	)

	if require_api_key and not config.api_key:
		raise CallAnalysisConfigurationError("The AI service API key is not configured.")
	return config


def get_public_status() -> dict:
	config = get_config(require_api_key=False)
	return {
		"enabled": True,
		"configured": bool(config.api_key),
	}


class CallAnalysisConfigurationError(RuntimeError):
	pass
