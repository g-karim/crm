"""Workspace permissions/filtering against native CRM documents; rollback only."""
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import frappe

from crm.api.telephony import get_call, get_calls, search_customers
from crm.integrations.api import get_recording_url


class TestTelephonyWorkspace(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = "Telephony" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		frappe.get_doc({"doctype": "User", "email": self.user, "first_name": self.tag,
			"user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": "Sales User"}]}).insert()
		self.visible = frappe.get_doc({"doctype": "CRM Lead", "first_name": self.tag + " Public",
			"status": "New", "lead_owner": self.user, "mobile_no": "+70000000001"}).insert()
		self.hidden = frappe.get_doc({"doctype": "CRM Lead", "first_name": self.tag + " Private",
			"status": "New", "lead_owner": "Administrator", "mobile_no": "+70000000002"}).insert()
		frappe.flags.in_exolve_sync = True  # Never start optional paid analysis for fixtures.
		self.incoming = self.make_call(self.visible, "Incoming", "No Answer")
		self.outgoing = self.make_call(self.visible, "Outgoing", "No Answer")
		self.recorded = self.make_call(self.visible, "Outgoing", "Completed", recording=True)
		self.private_call = self.make_call(self.hidden, "Incoming", "Completed", recording=True)

	def make_call(self, lead, direction, status, recording=False):
		return frappe.get_doc({"doctype": "CRM Call Log", "telephony_medium": "Manual",
			"type": direction, "status": status, "from": "+70000000001", "to": "+70000000002",
			"caller": self.user, "receiver": self.user, "duration": 30 if recording else 0,
			"reference_doctype": lead.doctype, "reference_docname": lead.name,
			"recording_url": "https://recordings.example.invalid/fixture.wav" if recording else ""}).insert()

	def tearDown(self):
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.flags.in_exolve_sync = False
		frappe.set_user("Administrator")

	def test_missed_filter_excludes_unanswered_outgoing_attempts(self):
		calls = get_calls(search=self.tag, view="missed", period="all")["calls"]
		self.assertEqual([row["name"] for row in calls], [self.incoming.name])

	def test_recording_filter_and_details_do_not_return_provider_urls(self):
		frappe.set_user(self.user)
		calls = get_calls(search=self.tag, view="recorded", period="all")["calls"]
		self.assertEqual([row["name"] for row in calls], [self.recorded.name])
		detail = get_call(self.recorded.name)
		self.assertIn("get_recording_url", detail["recording_path"])
		self.assertNotIn("recording_url", detail)
		self.assertNotIn("recordings.example.invalid", frappe.as_json(detail))

	def test_context_permissions_apply_before_pagination_and_customer_search(self):
		frappe.set_user(self.user)
		self.assertTrue(frappe.has_permission("CRM Call Log", "read"))
		self.assertFalse(frappe.has_permission("CRM Lead", "read", self.hidden.name))
		seen = []
		for offset in range(3):
			page = get_calls(search=self.tag, period="all", offset=offset, page_length=1)
			self.assertEqual(page["has_more"], offset < 2)
			seen.extend(row["name"] for row in page["calls"])
		self.assertEqual(set(seen), {self.incoming.name, self.outgoing.name, self.recorded.name})
		formatted = get_calls(search="8 (000) 000-00-01", period="all")["calls"]
		self.assertEqual({row["name"] for row in formatted}, set(seen))
		self.assertEqual(get_calls(search=self.tag + " Private", period="all")["calls"], [])
		customers = search_customers(self.tag)
		self.assertIn(self.visible.name, [row["name"] for row in customers])
		self.assertNotIn(self.hidden.name, [row["name"] for row in customers])

	def test_direct_call_link_cannot_read_an_inaccessible_customer(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			get_call(self.private_call.name)

	def test_recording_rechecks_customer_permission_before_provider_fetch(self):
		frappe.set_user(self.user)
		with patch("crm.integrations.api._fetch_recording") as fetch:
			with self.assertRaises(frappe.PermissionError):
				get_recording_url(self.private_call.name)
			fetch.assert_not_called()

	def test_revocation_hides_previously_visible_call_and_recording(self):
		frappe.set_user(self.user)
		get_call(self.recorded.name)
		frappe.set_user("Administrator")
		frappe.db.set_value("CRM Lead", self.visible.name, "lead_owner", "Administrator", update_modified=False)
		frappe.db.set_value("ToDo", {"reference_type": "CRM Lead", "reference_name": self.visible.name,
			"allocated_to": self.user}, "status", "Cancelled", update_modified=False)
		frappe.share.remove("CRM Lead", self.visible.name, self.user)
		frappe.set_user(self.user)
		self.assertEqual(get_calls(search=self.tag, period="all")["calls"], [])
		with self.assertRaises(frappe.PermissionError): get_call(self.recorded.name)
		with self.assertRaises(frappe.PermissionError): get_recording_url(self.recorded.name)

	def test_guest_cannot_use_workspace_endpoints(self):
		frappe.set_user("Guest")
		for action in (lambda: get_calls(), lambda: get_call(self.recorded.name), lambda: search_customers(self.tag)):
			with self.assertRaises(frappe.PermissionError): action()

	def test_invalid_filters_are_rejected(self):
		with self.assertRaises(frappe.ValidationError): get_calls(view="private")
		with self.assertRaises(frappe.ValidationError): get_calls(period="365")

	def make_deal_with_contact(self):
		contact = frappe.get_doc({"doctype": "Contact", "first_name": self.tag + " Person",
			"phone_nos": [{"phone": "+70000000003", "is_primary_mobile_no": 1}]}).insert()
		deal = frappe.get_doc({"doctype": "CRM Deal", "deal_name": self.tag + " Opportunity",
			"currency": frappe.db.get_single_value("FCRM Settings", "currency") or "USD",
			"status": frappe.db.get_value("CRM Deal Status", {"type": "Open"}, "name"), "deal_owner": self.user,
			"contacts": [{"contact": contact.name, "is_primary": 1}]}).insert(ignore_mandatory=True)
		return deal, contact, self.make_call(deal, "Outgoing", "Completed")

	def test_explicit_deal_contact_supplies_customer_name_and_search(self):
		deal, contact, call = self.make_deal_with_contact()
		frappe.set_user(self.user)
		self.assertEqual(get_call(call.name)["client_name"], contact.full_name)
		found = get_calls(search=contact.full_name, period="all")["calls"]
		self.assertEqual([row["name"] for row in found], [call.name])
		self.assertEqual(found[0]["reference"]["title"], deal.deal_name)

	def test_private_contact_name_is_not_exposed_through_readable_deal(self):
		deal, contact, call = self.make_deal_with_contact()
		other = frappe.get_doc({"doctype": "Contact", "first_name": self.tag + " Allowed"}).insert()
		frappe.get_doc({"doctype": "User Permission", "user": self.user,
			"allow": "Contact", "for_value": other.name, "apply_to_all_doctypes": 0, "applicable_for": "Contact"}).insert()
		frappe.set_user(self.user)
		self.assertFalse(frappe.has_permission("Contact", "read", contact.name))
		detail = get_call(call.name)
		self.assertEqual(detail["client_name"], deal.deal_name)
		self.assertNotIn(contact.full_name, frappe.as_json(detail))
		self.assertEqual(get_calls(search=contact.full_name, period="all")["calls"], [])
