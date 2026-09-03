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
		file_doc.file_name = "test-call.mp3"
		file_doc.file_url = "/private/files/test-call.mp3"
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

	@patch("crm.call_analysis.recording.frappe.get_attr")
	@patch("crm.call_analysis.recording.frappe.get_doc")
	@patch("crm.call_analysis.recording.frappe.db.get_value", return_value="s3-file")
	def test_reads_s3_file_attached_to_call_log(self, _get_value, get_doc, get_attr):
		file_doc = get_doc.return_value
		file_doc.file_size = 5
		file_doc.file_name = "call.mp3"
		file_doc.file_url = "/api/method/frappe_s3.controller.generate_file?key=recording"

		body = MagicMock()
		body.read.return_value = b"audio"
		operations = MagicMock()
		operations.read_file_from_s3.return_value = {
			"Body": body,
			"ContentLength": 5,
			"ContentType": "audio/mpeg",
		}
		operations_class = MagicMock(return_value=operations)
		get_s3_key = MagicMock(return_value="safe-key-from-file-document")
		get_attr.side_effect = {
			"frappe_s3.controller.S3Operations": operations_class,
			"frappe_s3.controller.get_s3_key_from_file_doc": get_s3_key,
		}.get

		call_log = SimpleNamespace(
			name="test-call",
			recording_url=file_doc.file_url,
			telephony_medium="Beeline",
		)
		recording = download_recording(call_log, max_bytes=10)

		self.assertEqual(recording.data, b"audio")
		self.assertEqual(recording.filename, "call.mp3")
		self.assertEqual(recording.content_type, "audio/mpeg")
		get_s3_key.assert_called_once_with(file_doc)
		operations.read_file_from_s3.assert_called_once_with("safe-key-from-file-document")
		body.read.assert_called_once_with(11)
		body.close.assert_called_once()

	@patch("crm.call_analysis.recording.frappe.get_attr")
	@patch("crm.call_analysis.recording.frappe.get_doc")
	@patch("crm.call_analysis.recording.frappe.db.get_value", return_value="s3-file")
	def test_rejects_large_s3_file_before_reading_body(self, _get_value, get_doc, get_attr):
		file_doc = get_doc.return_value
		file_doc.file_size = None
		file_doc.file_name = "call.mp3"
		file_doc.file_url = "/api/method/frappe_s3.controller.generate_file?key=recording"

		body = MagicMock()
		operations = MagicMock()
		operations.read_file_from_s3.return_value = {
			"Body": body,
			"ContentLength": 11,
			"ContentType": "audio/mpeg",
		}
		get_attr.side_effect = {
			"frappe_s3.controller.S3Operations": MagicMock(return_value=operations),
			"frappe_s3.controller.get_s3_key_from_file_doc": MagicMock(return_value="safe-key"),
		}.get

		call_log = SimpleNamespace(
			name="test-call",
			recording_url=file_doc.file_url,
			telephony_medium="Beeline",
		)
		with self.assertRaises(RecordingDownloadError):
			download_recording(call_log, max_bytes=10)

		body.read.assert_not_called()
		body.close.assert_called_once()
