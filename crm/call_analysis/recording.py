from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

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
