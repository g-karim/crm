from __future__ import annotations

from typing import ClassVar

import requests


class ExolveError(RuntimeError):
	pass


class ExolveClient:
	"""Only the provider's read operations are available to this connector."""

	PATHS: ClassVar[dict[str, str]] = {
		"sips": "/number/customer/v1/GetSIPList",
		"sip": "/sip/v1/GetAttributes",
		"numbers": "/number/customer/v1/GetList",
		"calls": "/statistics/call-history/v2/GetList",
	}

	def __init__(self, api_key: str):
		self.api_key = api_key.removeprefix("Bearer ").strip()

	def read(self, operation: str, values: dict) -> dict:
		try:
			response = requests.post(
				"https://api.exolve.ru" + self.PATHS[operation],
				json=values,
				headers={"Authorization": "Bearer " + self.api_key},
				timeout=(5, 20),
				allow_redirects=False,
			)
			if response.status_code != 200:
				raise ExolveError(f"Exolve request failed (HTTP {response.status_code}).")
			data = response.json()
			if not isinstance(data, dict):
				raise ValueError
			return data
		except (requests.RequestException, ValueError):
			# Provider bodies, request headers and exception strings can contain secrets.
			raise ExolveError("Could not read Exolve. Check the connection and API key.") from None

	def recording(self, call_id: str, range_header: str | None = None):
		if not call_id.isdecimal() or len(call_id) > 20:
			raise ExolveError("Invalid Exolve call identifier.")
		headers = {"Authorization": "Bearer " + self.api_key}
		if range_header:
			headers["Range"] = range_header
		try:
			response = requests.get(
				f"https://api.exolve.ru/statistics/download/{call_id}",
				headers=headers,
				timeout=(5, 30),
				stream=True,
				allow_redirects=False,
			)
			if response.is_redirect:
				# Signed CDN URLs are fetched without the application Bearer key.
				from crm.integrations.api import _fetch_recording

				location = response.headers.get("Location", "")
				response.close()
				if not location.startswith("https://"):
					raise ExolveError("Invalid Exolve recording redirect.")
				response = _fetch_recording(location, None, {"Range": range_header} if range_header else {})
			if response.status_code not in (200, 206):
				response.close()
				raise ExolveError("The Exolve recording is not available yet.")
			return response
		except requests.RequestException:
			raise ExolveError("Could not download the Exolve recording.") from None
