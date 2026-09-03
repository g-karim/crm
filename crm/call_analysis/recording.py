from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import frappe

from crm.integrations.api import _fetch_recording, _get_recording_credentials


class RecordingDownloadError(RuntimeError):
	pass


@dataclass(frozen=True)
class Recording:
	data: bytes
	filename: str
	content_type: str


_CONTENT_TYPE_EXTENSIONS = {
	"audio/aac": ".aac",
	"audio/flac": ".flac",
	"audio/mp4": ".m4a",
	"audio/mpeg": ".mp3",
	"audio/ogg": ".ogg",
	"audio/wav": ".wav",
	"audio/webm": ".webm",
	"video/mp4": ".m4a",
}
_ALLOWED_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".webm"}


def download_recording(call_log, *, max_bytes: int) -> Recording:
	if not call_log.recording_url:
		raise RecordingDownloadError("Recording URL not found")

	file_doc = _get_attached_recording_file(call_log)
	if file_doc:
		return _download_attached_recording(file_doc, max_bytes=max_bytes)
	if _local_file_url(call_log.recording_url):
		raise RecordingDownloadError("The call recording file could not be found.")

	auth = _get_recording_credentials(call_log.telephony_medium)
	upstream = None
	content_type = ""
	try:
		upstream = _fetch_recording(call_log.recording_url, auth, {})
		upstream.raise_for_status()
		content_type = str(upstream.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
		content_length = _content_length(upstream.headers.get("Content-Length"))
		if content_length and content_length > max_bytes:
			raise RecordingDownloadError("The call recording is too large to analyze.")

		chunks = []
		total = 0
		for chunk in upstream.iter_content(chunk_size=64 * 1024):
			if not chunk:
				continue
			total += len(chunk)
			if total > max_bytes:
				raise RecordingDownloadError("The call recording is too large to analyze.")
			chunks.append(chunk)
	finally:
		if upstream is not None:
			upstream.close()
			session = getattr(upstream, "_pinned_session", None)
			if session is not None:
				session.close()

	data = b"".join(chunks)
	if not data:
		raise RecordingDownloadError("The call recording is empty.")

	filename = _recording_filename(call_log.recording_url, content_type)
	if not content_type.startswith("audio/") and content_type not in {
		"application/octet-stream",
		"video/mp4",
	}:
		raise RecordingDownloadError("The call recording has an unsupported format.")
	return Recording(data=data, filename=filename, content_type=content_type or "audio/mpeg")


def _get_attached_recording_file(call_log):
	if not getattr(call_log, "name", None):
		return None

	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": call_log.recording_url,
			"attached_to_doctype": "CRM Call Log",
			"attached_to_name": call_log.name,
		},
		"name",
	)
	return frappe.get_doc("File", file_name) if file_name else None


def _download_attached_recording(file_doc, *, max_bytes: int) -> Recording:
	if file_doc.file_size and int(file_doc.file_size) > max_bytes:
		raise RecordingDownloadError("The call recording is too large to analyze.")
	if _s3_file_url(file_doc.file_url):
		return _download_s3_recording(file_doc, max_bytes=max_bytes)

	data = file_doc.get_content()
	return _recording_from_file_doc(file_doc, data, max_bytes=max_bytes)


def _download_s3_recording(file_doc, *, max_bytes: int) -> Recording:
	try:
		operations_class = frappe.get_attr("frappe_s3.controller.S3Operations")
		get_s3_key = frappe.get_attr("frappe_s3.controller.get_s3_key_from_file_doc")
		key = get_s3_key(file_doc)
		if not key:
			raise RecordingDownloadError("The call recording file could not be found.")
		response = operations_class().read_file_from_s3(key)
	except RecordingDownloadError:
		raise
	except Exception as exc:
		raise RecordingDownloadError("The call recording could not be read from file storage.") from exc

	body = response.get("Body")
	if body is None:
		raise RecordingDownloadError("The call recording is empty.")

	try:
		content_length = _content_length(response.get("ContentLength"))
		if content_length and content_length > max_bytes:
			raise RecordingDownloadError("The call recording is too large to analyze.")
		data = body.read(max_bytes + 1)
	finally:
		body.close()

	content_type = str(response.get("ContentType") or "").split(";", 1)[0].strip().lower()
	return _recording_from_file_doc(
		file_doc,
		data,
		max_bytes=max_bytes,
		content_type=content_type,
	)


def _recording_from_file_doc(
	file_doc,
	data,
	*,
	max_bytes: int,
	content_type: str | None = None,
) -> Recording:
	if isinstance(data, str):
		data = data.encode()
	if not data:
		raise RecordingDownloadError("The call recording is empty.")
	if len(data) > max_bytes:
		raise RecordingDownloadError("The call recording is too large to analyze.")

	filename = file_doc.file_name or PurePosixPath(urlsplit(file_doc.file_url).path).name
	filename = filename or "call-recording.mp3"
	guessed_content_type = mimetypes.guess_type(filename)[0] or "audio/mpeg"
	if not content_type or content_type == "application/octet-stream":
		content_type = guessed_content_type
	if not content_type.startswith("audio/"):
		raise RecordingDownloadError("The call recording has an unsupported format.")
	return Recording(data=data, filename=filename, content_type=content_type)


def _local_file_url(url: str) -> bool:
	parsed = urlsplit(str(url or ""))
	return not parsed.scheme and not parsed.netloc and parsed.path.startswith(("/files/", "/private/files/"))


def _s3_file_url(url: str) -> bool:
	path = urlsplit(str(url or "")).path
	return path.startswith("/api/method/frappe_s3.")


def _content_length(value: object) -> int:
	try:
		return max(0, int(value or 0))
	except (TypeError, ValueError):
		return 0


def _recording_filename(url: str, content_type: str) -> str:
	extension = PurePosixPath(urlsplit(url).path).suffix.lower()
	if extension not in _ALLOWED_EXTENSIONS:
		extension = _CONTENT_TYPE_EXTENSIONS.get(content_type)
	if not extension:
		extension = mimetypes.guess_extension(content_type) or ".mp3"
	if extension not in _ALLOWED_EXTENSIONS:
		extension = ".mp3"
	return f"call-recording{extension}"
