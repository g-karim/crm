"""Private, permission-checked PCM preview for Exolve's ADPCM WAV recordings."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import frappe
from frappe import _
from werkzeug.utils import send_file

from .api import check_recording_access, fetch_recording

MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_PREVIEW_BYTES = 100 * 1024 * 1024


def _cache_directory():
	return Path(frappe.get_site_path("private", "exolve_recordings"))


def browser_recording(log):
	# Recheck current participant, mapping, application and identity on every
	# request, including cache hits and byte-range requests.
	check_recording_access(log)
	directory = _cache_directory()
	directory.mkdir(mode=0o700, parents=True, exist_ok=True)
	preview = directory / f"{log.name}-pcm-v1.wav"
	with frappe.cache.lock(f"exolve-preview:{log.name}", timeout=120, blocking_timeout=65):
		if not preview.is_file():
			_prepare(log, directory, preview)
	response = send_file(
		preview.resolve(),
		frappe.local.request.environ,
		mimetype="audio/wav",
		download_name="exolve-call.wav",
		conditional=True,
		max_age=0,
	)
	response.headers["Cache-Control"] = "private, no-store"
	return response


def _prepare(log, directory, preview):
	ffmpeg = shutil.which("ffmpeg")
	if not ffmpeg:
		frappe.throw(_("Exolve recording playback requires ffmpeg on this CRM server."))
	with TemporaryDirectory(prefix="prepare-", dir=directory) as work:
		source = Path(work) / "source.wav"
		output = Path(work) / "preview.wav"
		upstream = fetch_recording(log)
		try:
			size = 0
			with source.open("wb") as target:
				for chunk in upstream.iter_content(chunk_size=64 * 1024):
					size += len(chunk)
					if size > MAX_SOURCE_BYTES:
						frappe.throw(_("Exolve recording exceeds the local preview limit."))
					target.write(chunk)
		finally:
			upstream.close()
			session = getattr(upstream, "_pinned_session", None)
			if session is not None:
				session.close()
		# The provider's observed format is WAV. Force its demuxer and local-file
		# protocol rather than letting an unexpected playlist fetch other resources.
		with source.open("rb") as data:
			header = data.read(12)
		if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
			frappe.throw(_("Unsupported Exolve recording format."))
		try:
			subprocess.run(
				[
					ffmpeg,
					"-nostdin",
					"-hide_banner",
					"-loglevel",
					"error",
					"-protocol_whitelist",
					"file,pipe",
					"-f",
					"wav",
					"-i",
					str(source),
					"-map",
					"0:a:0",
					"-c:a",
					"pcm_s16le",
					"-fs",
					str(MAX_PREVIEW_BYTES),
					"-f",
					"wav",
					str(output),
				],
				check=True,
				timeout=60,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.PIPE,
			)
		except (subprocess.SubprocessError, OSError):
			frappe.throw(_("Could not prepare the Exolve recording for playback."))
		if not 44 < output.stat().st_size < MAX_PREVIEW_BYTES:
			frappe.throw(_("Exolve recording exceeds the local preview limit."))
		# Preserve source sample rate/channels. This changes the browser's codec,
		# not the telephone recording's original bandwidth or quality.
		output.chmod(0o600)
		os.replace(output, preview)
