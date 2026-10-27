from unittest import TestCase
from unittest.mock import patch

from crm.call_analysis.tasks import run_call_analysis


class TestRetiredWorker(TestCase):
	@patch("crm.call_analysis.provider._request")
	def test_old_queued_job_cannot_bypass_budget_or_send_audio(self, request):
		self.assertEqual(run_call_analysis("old-job")["status"], "Failed")
		request.assert_not_called()
