import uuid

import frappe
from frappe import _
from frappe.model.document import Document


class CRMExolveSettings(Document):
	def validate(self):
		if self.get("history_start") and frappe.utils.getdate(self.history_start) > frappe.utils.getdate():
			frappe.throw(_("History start date cannot be in the future."))
		if self.application_id:
			try:
				self.application_id = str(uuid.UUID(self.application_id))
			except (ValueError, TypeError):
				frappe.throw(_("Enter a valid Exolve application ID."))
		if self.enabled and (
			not self.application_id or not self.get_password("api_key", raise_exception=False)
		):
			frappe.throw(_("Enter the Exolve application ID and API key."))
		users, sips = set(), set()
		for agent in self.agents:
			if not agent.user or not str(agent.sip_resource_id or "").isdecimal():
				frappe.throw(_("Select a user and a valid SIP resource ID."))
			if agent.user in users or agent.sip_resource_id in sips:
				frappe.throw(_("Each user and SIP resource can be mapped only once."))
			if not frappe.db.get_value("User", agent.user, "enabled"):
				frappe.throw(_("Select an enabled user."))
			users.add(agent.user)
			sips.add(agent.sip_resource_id)
