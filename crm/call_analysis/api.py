"""Legacy route uses the same opt-in and budget gate as the Telephony workspace."""

from uuid import uuid4

import frappe
from frappe.rate_limiter import rate_limit

from .config import get_public_status


@frappe.whitelist()
def get_runtime_status():
	return get_public_status()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60)
def start_analysis(call_log_name, force=0):
	from .workspace import start

	data = start(call_log_name, str(uuid4()), retry=force)
	return {"queued": data["result"]["state"] == "Queued", "status": data["result"]["state"]}
