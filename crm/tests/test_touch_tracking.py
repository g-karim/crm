import unittest
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime, now_datetime

from crm import touch_tracking as touch


class TestTouchPolicy(unittest.TestCase):
	def policy(self, **changes):
		return frappe._dict(
			enabled=1, track_leads=1, track_deals=1, lead_status_changes=1, deal_status_changes=1, **changes
		)

	def test_disabled_and_unrelated_events(self):
		policy = self.policy()
		for doctype, kind in (("CRM Task", "Created"), ("CRM Lead", "Email Sent")):
			self.assertFalse(touch.policy_accepts(policy, doctype, kind))
		policy.enabled = 0
		self.assertFalse(touch.policy_accepts(policy, "CRM Lead", "Created"))

	def test_lead_and_deal_rules_are_independent(self):
		policy = self.policy()
		policy.lead_status_changes = 0
		self.assertTrue(touch.policy_accepts(policy, "CRM Lead", "Created"))
		self.assertFalse(touch.policy_accepts(policy, "CRM Lead", "Status Changed"))
		self.assertTrue(touch.policy_accepts(policy, "CRM Deal", "Status Changed"))
		policy.track_deals = 0
		self.assertFalse(touch.policy_accepts(policy, "CRM Deal", "Created"))

	def test_settings_do_not_reinterpret_past_events(self):
		first, second, third = self.policy(), self.policy(), self.policy()
		first.effective_from = datetime(2026, 1, 1, 10)
		second.effective_from = datetime(2026, 1, 1, 11)
		third.effective_from = datetime(2026, 1, 1, 12)
		second.enabled = 0
		policies = [first, second, third]
		self.assertIsNone(touch.policy_at(policies, "2026-01-01 09:00:00"))
		self.assertIs(touch.policy_at(policies, "2026-01-01 10:30:00"), first)
		self.assertIs(touch.policy_at(policies, "2026-01-01 11:00:00"), second)
		self.assertIs(touch.policy_at(policies, "2026-01-01 12:00:00"), third)
		self.assertEqual(
			list(touch.eligible_intervals(policies, "CRM Lead", "Created")),
			[(first.effective_from, second.effective_from), (third.effective_from, None)],
		)

	def test_event_identity_does_not_include_retry_or_policy_version(self):
		identity = ("CRM Lead", "LEAD-1", "Status Changed", "CRM Status Change Log", "row-1")
		self.assertEqual(touch.event_key(*identity), touch.event_key(*identity))
		self.assertNotEqual(touch.event_key(*identity), touch.event_key(*(*identity[:-1], "row-2")))
		self.assertNotEqual(touch.event_key(*identity), touch.event_key("CRM Deal", *identity[1:]))


class TestTouchTrackingDatabase(unittest.TestCase):
	"""Requires a disposable Frappe site with CRM installed. No external calls."""

	def setUp(self):
		if not getattr(frappe.local, "site", None):
			self.skipTest("Requires an initialized disposable Frappe site")
		frappe.set_user("Administrator")
		frappe.clear_cache()
		self.settings = frappe.get_doc(touch.SETTINGS)
		for field in touch.POLICY_FIELDS:
			self.settings.set(field, 1)
		self.settings.save()
		# Do not invoke providers or enrichment while creating test records.
		self.patches = [
			patch("crm.domain_enrichment.tasks.auto_enrich_on_create"),
			patch("frappe.enqueue"),
			patch("frappe.publish_realtime"),
		]
		for mock in self.patches:
			mock.start()
			self.addCleanup(mock.stop)

	def tearDown(self):
		if getattr(frappe.local, "site", None):
			frappe.set_user("Administrator")
			frappe.db.rollback()
			frappe.clear_cache()

	def create(self, doctype="CRM Lead"):
		values = {"doctype": doctype, "first_name": "Touch Stage 2 Test"}
		if doctype == "CRM Lead":
			values["status"] = "New"
		return frappe.get_doc(values).insert()

	def events(self, doc):
		return frappe.get_all(
			touch.EVENT,
			filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
			fields=["*"],
			order_by="occurred_at asc, name asc",
		)

	def change_status(self, doc):
		if doc.doctype == "CRM Lead":
			doc.status = "Contacted"
		else:
			doc.status = frappe.db.get_value(
				"CRM Deal Status",
				{"pipeline": doc.pipeline, "name": ["!=", doc.status], "type": "Ongoing"},
				"name",
			)
		doc.save()

	def pending_touch(self, doc, *, occurred_at=None):
		policy = touch._policies()[-1]
		return touch._record_event(
			doc.doctype,
			doc.name,
			"Status Changed",
			"CRM Status Change Log",
			"async-" + frappe.generate_hash(),
			occurred_at or now_datetime(),
			"Administrator",
			policy,
		)

	def test_disabled_site_preserves_original_behavior(self):
		self.settings.enabled = 0
		self.settings.save()
		for doctype in touch.TARGETS:
			doc = self.create(doctype)
			self.change_status(doc)
			self.assertIsNone(doc.last_touch_at)
			self.assertEqual(self.events(doc), [])
		self.assertEqual(touch.recover_missing(), 0)

	def test_creation_and_status_do_not_artificially_change_modified(self):
		for doctype in touch.TARGETS:
			doc = self.create(doctype)
			self.assertEqual(get_datetime(doc.last_touch_at), get_datetime(doc.creation))
			self.assertEqual(frappe.db.get_value(doctype, doc.name, "modified"), get_datetime(doc.modified))
			self.change_status(doc)
			events = self.events(doc)
			self.assertEqual([event.event_type for event in events], ["Created", "Status Changed"])
			self.assertTrue(all(event.state == "Applied" for event in events))
			self.assertEqual(get_datetime(doc.last_touch_at), get_datetime(events[-1].occurred_at))
			self.assertEqual(frappe.db.get_value(doctype, doc.name, "modified"), get_datetime(doc.modified))

	def test_noop_and_unselected_field_save_do_not_touch(self):
		for doctype in touch.TARGETS:
			doc = self.create(doctype)
			original = get_datetime(doc.last_touch_at)
			doc.save()
			doc.website = "https://example.invalid"
			doc.save()
			self.assertEqual(get_datetime(doc.last_touch_at), original)
			self.assertEqual(len(self.events(doc)), 1)

	def test_status_rules_are_separate(self):
		self.settings.lead_status_changes = 0
		self.settings.save()
		lead, deal = self.create(), self.create("CRM Deal")
		self.change_status(lead)
		self.change_status(deal)
		self.assertEqual(len(self.events(lead)), 1)
		self.assertEqual(len(self.events(deal)), 2)

	def test_client_cannot_overwrite_server_owned_date(self):
		doc = self.create()
		original = get_datetime(doc.last_touch_at)
		doc.last_touch_at = "2099-01-01 00:00:00"
		doc.save()
		self.assertEqual(get_datetime(doc.last_touch_at), original)

	def test_stale_open_card_preserves_background_touch(self):
		for doctype in touch.TARGETS:
			doc = self.create(doctype)
			opened = frappe.get_doc(doctype, doc.name)
			modified = get_datetime(opened.modified)
			event = self.pending_touch(doc)
			self.assertTrue(touch._apply_safely(event))
			latest = frappe.db.get_value(doctype, doc.name, touch.FIELD)
			self.assertEqual(frappe.db.get_value(doctype, doc.name, "modified"), modified)
			opened.website = "https://example.invalid/background"
			opened.save()
			self.assertEqual(get_datetime(opened.last_touch_at), latest)

	def test_original_concurrent_business_save_still_rejects_stale_document(self):
		doc = self.create()
		opened = frappe.get_doc(doc.doctype, doc.name)
		doc.website = "https://example.invalid/first"
		doc.save()
		opened.website = "https://example.invalid/stale"
		with self.assertRaises(frappe.TimestampMismatchError):
			opened.save()

	def test_repeated_event_and_old_event_do_not_regress_timestamp(self):
		doc = self.create()
		event = self.pending_touch(doc)
		touch._apply_safely(event)
		latest = frappe.db.get_value(doc.doctype, doc.name, touch.FIELD)
		touch._apply_safely(event)
		older = self.pending_touch(doc, occurred_at=doc.creation)
		touch._apply_safely(older)
		self.assertEqual(frappe.db.get_value(doc.doctype, doc.name, touch.FIELD), latest)
		self.assertEqual(frappe.db.get_value(touch.EVENT, event, "state"), "Applied")

	def test_apply_failure_keeps_business_save_and_retries_without_resaving(self):
		doc = self.create()
		with patch("crm.touch_tracking._apply_event", side_effect=RuntimeError("injected apply failure")):
			self.change_status(doc)
		modified = get_datetime(doc.modified)
		event = self.events(doc)[-1]
		self.assertEqual(event.state, "Pending")
		self.assertEqual(event.attempts, 1)
		self.assertEqual(frappe.db.get_value(doc.doctype, doc.name, "status"), doc.status)
		frappe.db.set_value(touch.EVENT, event.name, "next_retry_at", None)
		touch.process_pending()
		self.assertEqual(frappe.db.get_value(touch.EVENT, event.name, "state"), "Applied")
		self.assertEqual(frappe.db.get_value(doc.doctype, doc.name, "modified"), modified)
		self.assertEqual(len(self.events(doc)), 2)

	def test_capture_failure_recovers_from_native_sources(self):
		with patch("crm.touch_tracking._record_event", side_effect=RuntimeError("injected capture failure")):
			lead, deal = self.create(), self.create("CRM Deal")
			self.change_status(lead)
			self.change_status(deal)
		self.assertEqual(self.events(lead), [])
		self.assertEqual(touch.recover_missing(), 4)
		touch.process_pending()
		self.assertEqual(touch.recover_missing(), 0)
		for doc in (lead, deal):
			self.assertEqual(len(self.events(doc)), 2)
			self.assertEqual(
				get_datetime(doc.reload().last_touch_at), get_datetime(self.events(doc)[-1].occurred_at)
			)

	def test_transaction_rollback_removes_event_and_native_source(self):
		frappe.db.savepoint("touch_test_rollback")
		doc = self.create()
		self.assertEqual(len(self.events(doc)), 1)
		frappe.db.rollback(save_point="touch_test_rollback")
		self.assertFalse(frappe.db.exists(doc.doctype, doc.name))
		self.assertEqual(self.events(doc), [])
		self.assertEqual(touch.recover_missing(), 0)

	def test_policy_changes_and_reenable_do_not_replay_disabled_history(self):
		self.settings.enabled = 0
		self.settings.save()
		doc = self.create()
		self.change_status(doc)
		self.settings.enabled = 1
		self.settings.save()
		self.assertEqual(touch.recover_missing(), 0)
		self.assertIsNone(doc.reload().last_touch_at)
		self.change_status(doc)  # same status: still no event
		self.assertEqual(self.events(doc), [])

	def test_noop_settings_save_keeps_immutable_revision(self):
		revision = self.settings.policy_revision
		self.settings.policy_revision = "client-injected"
		self.settings.save()
		self.assertEqual(self.settings.policy_revision, revision)
		policy = frappe.get_doc(touch.POLICY, revision)
		policy.enabled = 0
		with self.assertRaises(frappe.PermissionError):
			policy.save()

	def test_insert_failure_does_not_abort_business_transaction(self):
		from crm.fcrm.doctype.crm_touch_event.crm_touch_event import CRMTouchEvent

		with patch.object(
			CRMTouchEvent, "validate", side_effect=RuntimeError("injected event insert failure")
		):
			doc = self.create()
			self.change_status(doc)
		self.assertTrue(frappe.db.exists(doc.doctype, doc.name))
		self.assertEqual(frappe.db.get_value(doc.doctype, doc.name, "status"), "Contacted")
		self.assertEqual(self.events(doc), [])
		self.assertEqual(touch.recover_missing(), 2)
		touch.process_pending()
		self.assertEqual(len(self.events(doc)), 2)

	def test_accepted_event_finishes_with_original_policy_after_disable(self):
		doc = self.create()
		event = self.pending_touch(doc)
		revision = frappe.db.get_value(touch.EVENT, event, "policy_revision")
		self.settings.enabled = 0
		self.settings.save()
		touch.process_pending()
		self.assertEqual(frappe.db.get_value(touch.EVENT, event, "state"), "Applied")
		self.assertEqual(frappe.db.get_value(touch.EVENT, event, "policy_revision"), revision)
		self.assertNotEqual(revision, self.settings.policy_revision)

	def test_new_event_does_not_reopen_deleted_target_or_block_deletion(self):
		doc = self.create()
		event = self.pending_touch(doc)
		frappe.delete_doc(doc.doctype, doc.name)
		touch.process_pending()
		self.assertFalse(frappe.db.exists(doc.doctype, doc.name))
		self.assertEqual(frappe.db.get_value(touch.EVENT, event, "state"), "Ignored")

	def test_sales_user_cannot_edit_settings_or_inject_events(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "touch-stage2-sales-user@example.invalid",
				"first_name": "Touch Sales User",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert()
		frappe.set_user(user.name)
		settings = frappe.get_doc(touch.SETTINGS)
		settings.enabled = 0
		with self.assertRaises(frappe.PermissionError):
			settings.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": touch.EVENT}).insert()

	def test_initial_defaults_do_not_enable_existing_sites(self):
		frappe.db.rollback()
		frappe.clear_cache()
		self.assertEqual(frappe.get_doc(touch.SETTINGS).enabled, 0)
		doc = self.create()
		self.assertIsNone(doc.last_touch_at)
		self.assertEqual(self.events(doc), [])

	def test_transaction_abort_is_not_reported_as_successful_save(self):
		from pymysql import OperationalError

		doc = self.create()
		for error in (
			OperationalError(1213, "injected deadlock"),
			frappe.QueryDeadlockError(OperationalError(1020, "snapshot conflict")),
		):
			with patch("crm.touch_tracking._apply_event", side_effect=error):
				with self.assertRaises(type(error)):
					self.change_status(doc)
			doc.reload()
			doc.status = "New"
			doc.save()

	def test_manual_maintenance_does_not_rollback_callers_transaction(self):
		doc = self.create()
		self.pending_touch(doc)
		with patch(
			"crm.touch_tracking._apply_event", side_effect=frappe.QueryDeadlockError("snapshot conflict")
		):
			with self.assertRaises(frappe.QueryDeadlockError):
				touch.maintenance()
		self.assertTrue(frappe.db.exists(doc.doctype, doc.name))
