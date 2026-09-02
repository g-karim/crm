from __future__ import annotations

import os
from dataclasses import dataclass

import frappe

DEFAULTS = {
	"api_base_url": "https://openrouter.ai/api/v1",
	"transcription_model": "openai/whisper-large-v3",
	"summary_model": "google/gemini-3.1-flash-lite-preview",
	"language": "Auto",
	"max_recording_mb": 25,
}
API_KEY_ENV = "CRM_CALL_ANALYSIS_API_KEY"
API_KEY_CONFIG = "crm_call_analysis_api_key"


@dataclass(frozen=True)
class CallAnalysisConfig:
	api_base_url: str
	api_key: str
	transcription_model: str
	summary_model: str
	language: str
	max_recording_bytes: int


def get_config(*, require_api_key: bool = True) -> CallAnalysisConfig:
	api_key = os.getenv(API_KEY_ENV) or frappe.conf.get(API_KEY_CONFIG) or ""
	config = CallAnalysisConfig(
		api_base_url=DEFAULTS["api_base_url"],
		api_key=str(api_key).strip(),
		transcription_model=DEFAULTS["transcription_model"],
		summary_model=DEFAULTS["summary_model"],
		language=DEFAULTS["language"],
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
