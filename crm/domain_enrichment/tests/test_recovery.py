"""Real database regression checks for failed crawls and missed realtime events."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from crm.domain_enrichment import api, tasks
from crm.domain_enrichment.extractors import READABILITY_MESSAGES
from crm.domain_enrichment.result import EnrichmentResult, Field


class TestEnrichmentRecovery(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.organization = frappe.get_doc(
			{
				"doctype": "CRM Organization",
				"organization_name": "Enrichment recovery " + frappe.generate_hash(length=8),
				"company_description": "Preserve my description",
				"organization_logo": "https://example.com/original-logo.png",
			}
		).insert()
		self.queued_at = str(add_to_date(now_datetime(), seconds=-1))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_unreachable_site_never_overwrites_previous_enrichment(self):
		for reason in ("unreachable", "blocked"):
			with self.subTest(reason=reason):
				result = EnrichmentResult(website="https://example.com")
				result.notes = [READABILITY_MESSAGES[reason]]
				with (
					patch.object(tasks, "run_pipeline", return_value=result),
					patch.object(tasks, "_publish"),
					patch.object(tasks, "capture"),
				):
					tasks.run_enrichment("CRM Organization", self.organization.name, result.website)
				self.organization.reload()
				self.assertEqual(self.organization.company_description, "Preserve my description")
				self.assertEqual(self.organization.organization_logo, "https://example.com/original-logo.png")
				latest = frappe.get_all(
					"CRM Enrichment Run",
					filters={"reference_name": self.organization.name},
					fields=["status"],
					order_by="creation desc",
					limit=1,
				)
				self.assertEqual(latest[0].status, "Failed")

	def test_progress_recovers_filled_fields_from_completed_run(self):
		result = EnrichmentResult(website="https://example.com", company_name=Field("Example"))
		tasks.write_run(
			"CRM Organization",
			self.organization.name,
			result.website,
			status="Completed",
			result=result,
			filled_fields=["Email"],
		)
		progress = api.get_progress("CRM Organization", self.organization.name, self.queued_at)
		self.assertEqual(progress["status"], "completed")
		self.assertEqual(progress["payload"]["filled_fields"], [frappe._("Email")])

	def test_progress_ignores_a_run_finished_before_the_current_request(self):
		tasks.write_run("CRM Organization", self.organization.name, "https://example.com", status="Completed")
		future = str(add_to_date(now_datetime(), seconds=5))
		self.assertEqual(
			api.get_progress("CRM Organization", self.organization.name, future), {"status": "running"}
		)

	def test_progress_requires_read_access_to_the_reference(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_progress("CRM Organization", self.organization.name, self.queued_at)

	def test_feature_switches_expose_no_admin_configuration(self):
		flags = api.get_settings_flags()
		self.assertEqual(set(flags), {"enabled", "doctypes"})
		self.assertEqual(set(flags["doctypes"]), {"CRM Lead", "CRM Deal", "CRM Organization"})

	def test_terminal_events_wait_for_commit(self):
		with patch.object(frappe, "publish_realtime") as publish:
			tasks._publish("CRM Organization", self.organization.name, "completed")
			self.assertTrue(publish.call_args.kwargs["after_commit"])
			tasks._publish("CRM Organization", self.organization.name, "running")
			self.assertFalse(publish.call_args.kwargs["after_commit"])
