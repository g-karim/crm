"""Advanced filters, delivery-time revocation and immutable legacy request replay."""

from unittest.mock import patch
from uuid import uuid4

import frappe

from crm.notification_rules import api, conditions, schema
from crm.tests.test_notification_email_channel import TestCRMEmailChannel


class TestCRMConditions(TestCRMEmailChannel):
	def condition(self, field="annual_revenue", operator="gte", value="10000"):
		return {"field": field, "operator": operator, "value": value}

	def test_numeric_condition_delivers_all_selected_channels(self):
		self.mail_master()
		frappe.db.set_value("CRM Lead", self.lead.name, "annual_revenue", 15000)
		self.save(self.all_channels(conditions=[self.condition()]))
		self.transition()
		self.assertIsNotNone(self.notice)
		self.assertIsNotNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		self.assertEqual({r.status for r in self.rows()}, {"Test Accepted"})
		self.assertEqual({r.status for r in self.mail_rows()}, {"Test Accepted"})

	def test_non_matching_number_is_silent(self):
		frappe.db.set_value("CRM Lead", self.lead.name, "annual_revenue", 500)
		self.save(self.rule(conditions=[self.condition()]))
		self.transition()
		self.assertIsNone(self.notice)

	def test_current_field_change_cancels_previously_queued_delivery(self):
		self.mail_master()
		frappe.db.set_value("CRM Lead", self.lead.name, "annual_revenue", 15000)
		self.save(self.all_channels(conditions=[self.condition()]))
		self.transition()
		frappe.db.set_value("CRM Lead", self.lead.name, "annual_revenue", 200)
		self.assertIsNone(self.deliver_bot())
		self.drain()
		self.drain_mail()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})
		self.assertEqual({r.status for r in self.mail_rows()}, {"Cancelled"})

	def test_tag_filter_requires_all_requested_tags(self):
		frappe.db.set_value("CRM Lead", self.lead.name, "_user_tags", ",VIP,Renewal")
		self.save(self.rule(conditions=[self.condition("_user_tags", "contains_all", ["VIP", "Renewal"])]))
		self.transition()
		self.assertIsNotNone(self.notice)

	def test_invalid_fields_operators_and_non_finite_numbers_are_rejected(self):
		for item in [
			self.condition("password"),
			self.condition("_assign"),
			self.condition(operator="eval"),
			self.condition(value="NaN"),
			self.condition(value=True),
			self.condition(value="Infinity"),
		]:
			with self.subTest(condition=item), self.assertRaises(frappe.ValidationError):
				schema.validate(self.rule(conditions=[item]), self.user)

	def test_filter_count_is_bounded_and_values_cannot_be_expressions(self):
		for values in [[self.condition()] * 13, [self.condition(value="__import__('os').system('id')")]]:
			with self.assertRaises(frappe.ValidationError):
				schema.validate(self.rule(conditions=values), self.user)

	def test_hidden_or_revoked_field_fails_closed_at_delivery(self):
		frappe.db.set_value("CRM Lead", self.lead.name, "annual_revenue", 15000)
		self.save(self.rule(conditions=[self.condition()]))
		self.transition()
		with patch.object(conditions, "fields", return_value=[]):
			self.assertIsNone(self.deliver_bot())
			self.drain()
		self.assertEqual({r.status for r in self.rows()}, {"Cancelled"})

	def test_old_rule_without_conditions_replays_with_original_hash(self):
		rule = self.rule()
		mutation = uuid4().hex
		revision = api.get_settings()["revision"]
		first = self.save(rule, revision=revision, mutation=mutation)
		second = self.save(rule, revision=revision, mutation=mutation)
		self.assertTrue(second["replayed"])
		self.assertEqual(first["revision"], second["revision"])
		self.assertNotIn("conditions", second["configuration"]["rules"][0])
