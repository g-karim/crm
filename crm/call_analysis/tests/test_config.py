import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from crm.call_analysis import config


class TestCallAnalysisConfig(TestCase):
	@patch.dict(os.environ, {config.API_KEY_ENV: "environment-key"})
	def test_environment_key_takes_precedence_over_common_bench_config(self):
		with patch.object(config, "frappe", SimpleNamespace(conf={config.API_KEY_CONFIG: "bench-key"})):
			result = config.get_config()

		self.assertEqual(result.api_key, "environment-key")
		self.assertEqual(result.api_base_url, "https://openrouter.ai/api/v1")

	@patch.dict(os.environ, {}, clear=True)
	def test_common_bench_config_is_shared_fallback(self):
		with patch.object(config, "frappe", SimpleNamespace(conf={config.API_KEY_CONFIG: "bench-key"})):
			result = config.get_config()

		self.assertEqual(result.api_key, "bench-key")

	@patch.dict(os.environ, {}, clear=True)
	def test_feature_is_always_enabled_but_reports_missing_key(self):
		with patch.object(config, "frappe", SimpleNamespace(conf={})):
			self.assertEqual(config.get_public_status(), {"enabled": True, "configured": False})
			with self.assertRaises(config.CallAnalysisConfigurationError):
				config.get_config()
