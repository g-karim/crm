from unittest.mock import patch

from frappe.tests import UnitTestCase

from crm.api.messenger import is_messenger_installed


class TestMessengerIntegrationDetection(UnitTestCase):
	def test_returns_true_when_messenger_doctype_exists(self):
		with patch("crm.api.messenger.frappe.db.exists", return_value="Messenger Settings"):
			self.assertTrue(is_messenger_installed())

	def test_returns_false_when_messenger_doctype_is_missing(self):
		with patch("crm.api.messenger.frappe.db.exists", return_value=None):
			self.assertFalse(is_messenger_installed())
