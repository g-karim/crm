"""Manager suggestions never override recipient ACLs, opt-outs or immutable requests."""

from uuid import uuid4

import frappe
from exp_theme.notifications import policy

from crm.notification_rules import api, templates
from crm.tests.test_notification_email_channel import TestCRMEmailChannel


class TestCRMTemplates(TestCRMEmailChannel):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		self.manager = f"templates-{uuid4().hex}@example.invalid"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.manager,
				"first_name": "Local template manager",
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales Manager"}, {"role": "Desk User"}],
			}
		).insert()
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser

	def template(self, **values):
		return {
			"id": uuid4().hex,
			"name": "Local team rule",
			"enabled": True,
			"roles": [],
			"recipients": [self.user],
			"rules": [self.rule()],
			**values,
		}

	def publish(self, value):
		frappe.set_user(self.manager)  # nosemgrep: frappe-setuser
		return templates.save_template(
			value, policy.load(self.manager, templates.SOURCE).revision, uuid4().hex, self.manager
		)

	def apply(self, value, revision, mutation=None, policy_revision=None):
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		if policy_revision is None:
			policy_revision = api.get_settings()["revision"]
		return templates.apply_template(
			self.manager, value["id"], revision, policy_revision, mutation or uuid4().hex, self.user
		)

	def test_only_manager_can_publish(self):
		with self.assertRaises(frappe.PermissionError):
			templates.save_template(self.template(), 0, uuid4().hex, self.user)

	def test_publication_does_not_change_recipient_settings(self):
		before = api.get_settings()
		self.publish(self.template())
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertEqual(api.get_settings(), before)

	def test_explicit_apply_preserves_all_channel_opt_outs(self):
		self.primary(False)
		self.one(False)
		self.mail_master(False)
		value = self.template(rules=[self.all_channels()])
		published = self.publish(value)
		result = self.apply(value, published["revision"])
		self.assertEqual(set(result["masters"].values()), {False})
		self.assertEqual(len(result["configuration"]["rules"]), 1)
		self.transition()
		self.assertEqual(self.rows(), [])
		self.assertEqual(self.mail_rows(), [])

	def test_apply_replay_survives_author_update_without_duplicates(self):
		value = self.template()
		published = self.publish(value)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		revision = api.get_settings()["revision"]
		mutation = uuid4().hex
		first = self.apply(value, published["revision"], mutation, revision)
		value["name"] = "Updated offer"
		self.publish(value)
		second = self.apply(value, published["revision"], mutation, revision)
		self.assertTrue(second["replayed"])
		self.assertEqual(first["revision"], second["revision"])
		self.assertEqual(len(second["configuration"]["rules"]), 1)

	def test_outside_audience_cannot_apply_template(self):
		value = self.template(recipients=[self.manager])
		published = self.publish(value)
		with self.assertRaises(frappe.PermissionError):
			self.apply(value, published["revision"])

	def test_catalog_hides_unavailable_selected_ids_and_apply_cannot_grant_access(self):
		value = self.template()
		published = self.publish(value)
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		frappe.db.set_value("CRM Lead", self.lead.name, {"lead_owner": "Administrator", "_assign": "[]"})
		frappe.db.delete("ToDo", {"reference_type": "CRM Lead", "reference_name": self.lead.name})
		frappe.clear_cache(user=self.user)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		item = templates.catalog(self.user)["offered"][0]
		self.assertEqual(item["rules"][0]["record_ids"], [])
		self.assertEqual(item["unavailable_selection_count"], 1)
		with self.assertRaises(frappe.PermissionError):
			self.apply(value, published["revision"])

	def test_author_edits_do_not_overwrite_applied_personal_rule(self):
		value = self.template()
		published = self.publish(value)
		first = self.apply(value, published["revision"])
		value["rules"][0]["name"] = "Author changed name"
		self.publish(value)
		frappe.set_user(self.user)  # nosemgrep: frappe-setuser
		self.assertEqual(api.get_settings()["configuration"]["rules"], first["configuration"]["rules"])
