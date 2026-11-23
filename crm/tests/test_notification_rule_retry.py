"""Settings retry boundaries: HTTP ownership, bounded attempts and unchanged actor."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from crm.notification_rules.mutation import rpc


class TestNotificationRuleRetry(unittest.TestCase):
	def setUp(self):
		self.request = getattr(frappe.local, "request", None)
		self.form = frappe.local.form_dict
		self.actor = frappe.session.user
		frappe.local.request = SimpleNamespace(method="POST")
		self.action = Mock()

		@rpc
		def operation():
			return self.action()

		self.operation = operation
		frappe.local.form_dict = frappe._dict(cmd=operation.__module__ + "." + operation.__name__)

	def tearDown(self):
		frappe.local.request = self.request
		frappe.local.form_dict = self.form
		frappe.session.user = self.actor
		frappe.db.rollback()

	def test_two_conflicts_retry_the_complete_operation_three_times(self):
		self.action.side_effect = [
			frappe.QueryDeadlockError("private"),
			frappe.QueryTimeoutError("private"),
			"saved",
		]
		with patch.object(frappe.db, "rollback", wraps=frappe.db.rollback) as rollback:
			self.assertEqual(self.operation(), "saved")
			self.assertEqual(rollback.call_count, 2)
		self.assertEqual(self.action.call_count, 3)
		self.assertEqual(frappe.session.user, self.actor)

	def test_embedded_call_never_rolls_back_its_callers_transaction(self):
		frappe.local.form_dict.cmd = "another.business_operation"
		self.action.side_effect = frappe.QueryDeadlockError("private")
		with patch.object(frappe.db, "rollback") as rollback:
			with self.assertRaises(frappe.QueryDeadlockError):
				self.operation()
			rollback.assert_not_called()
		self.assertEqual(self.action.call_count, 1)

	def test_permanent_conflict_stops_at_three_attempts(self):
		self.action.side_effect = frappe.QueryTimeoutError("private")
		with self.assertRaises(frappe.QueryTimeoutError):
			self.operation()
		self.assertEqual(self.action.call_count, 3)

	def test_non_database_error_does_not_retry(self):
		self.action.side_effect = ValueError("private")
		with self.assertRaises(ValueError):
			self.operation()
		self.assertEqual(self.action.call_count, 1)

	def test_actor_change_stops_without_impersonating_the_original_user(self):
		def change_actor():
			frappe.session.user = "Guest"
			raise frappe.QueryDeadlockError("private")

		self.action.side_effect = change_actor
		with self.assertRaises(frappe.AuthenticationError):
			self.operation()
		self.assertEqual(self.action.call_count, 1)
		self.assertEqual(frappe.session.user, "Guest")
