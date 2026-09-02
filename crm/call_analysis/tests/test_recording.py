from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crm.call_analysis.recording import RecordingDownloadError, download_recording


class TestCallRecordingDownload(TestCase):
	def _response(self, chunks, *, content_type="audio/mpeg", content_length=None):
		response = MagicMock()
		response.headers = {"Content-Type": content_type}
		if content_length is not None:
			response.headers["Content-Length"] = str(content_length)
		response.iter_content.return_value = iter(chunks)
		return response

	@patch("crm.call_analysis.recording._get_recording_credentials", return_value=None)
	@patch("crm.call_analysis.recording._fetch_recording")
	def test_downloads_recording_with_bounded_stream(self, fetch, _credentials):
		fetch.return_value = self._response([b"one", b"two"])
		call_log = SimpleNamespace(
			recording_url="https://cdn.example.test/call.mp3",
			telephony_medium="Manual",
		)

		recording = download_recording(call_log, max_bytes=10)

		self.assertEqual(recording.data, b"onetwo")
		self.assertEqual(recording.filename, "call-recording.mp3")
		fetch.return_value.close.assert_called_once()

	@patch("crm.call_analysis.recording._get_recording_credentials", return_value=None)
	@patch("crm.call_analysis.recording._fetch_recording")
	def test_rejects_recording_above_stream_limit(self, fetch, _credentials):
		fetch.return_value = self._response([b"1234", b"5678"])
		call_log = SimpleNamespace(
			recording_url="https://cdn.example.test/call.ogg",
			telephony_medium="Manual",
		)

		with self.assertRaises(RecordingDownloadError):
			download_recording(call_log, max_bytes=6)

		fetch.return_value.close.assert_called_once()

	@patch("crm.call_analysis.recording.frappe.get_doc")
	@patch("crm.call_analysis.recording.frappe.db.get_value", return_value="test-file")
	def test_reads_private_file_attached_to_call_log(self, _get_value, get_doc):
		file_doc = get_doc.return_value
		file_doc.file_size = 5
		file_doc.get_content.return_value = b"audio"
		call_log = SimpleNamespace(
			name="test-call",
			recording_url="/private/files/test-call.mp3",
			telephony_medium="Manual",
		)

		recording = download_recording(call_log, max_bytes=10)

		self.assertEqual(recording.data, b"audio")
		self.assertEqual(recording.filename, "test-call.mp3")
		self.assertEqual(recording.content_type, "audio/mpeg")
