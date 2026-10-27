"""An older installed theme must not break native CRM notification saves."""
import sys
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from crm.notification_source import changed


class TestNotificationThemeCompatibility(TestCase):
	def service(self, installed=True, schema=True):
		return SimpleNamespace(
			get_installed_apps=Mock(return_value=["frappe", "crm", "exp_theme"] if installed else ["frappe", "crm"]),
			db=SimpleNamespace(table_exists=Mock(return_value=schema)),
		)

	def test_installed_production_theme_without_notification_schema_is_optional(self):
		frappe = self.service(schema=False)
		# The real production theme intentionally has no exp_theme.notifications module.
		with patch("crm.notification_source.frappe", frappe):
			changed(SimpleNamespace(to_user="Administrator"))
		frappe.db.table_exists.assert_called_once_with("EXP Notification Subscription")

	def test_absent_theme_keeps_native_notification_path(self):
		frappe = self.service(installed=False)
		with patch("crm.notification_source.frappe", frappe):
			changed(SimpleNamespace(to_user="Administrator"))
		frappe.db.table_exists.assert_not_called()

	def test_missing_recipient_does_not_load_optional_service(self):
		frappe = self.service()
		with patch("crm.notification_source.frappe", frappe):
			changed(SimpleNamespace(to_user=None))
		frappe.get_installed_apps.assert_not_called()

	def test_ready_notification_service_receives_original_recipient(self):
		access = ModuleType("exp_theme.notifications.access")
		access.changed = Mock()
		with (
			patch("crm.notification_source.frappe", self.service()),
			patch.dict(sys.modules, {"exp_theme.notifications.access": access}),
		):
			changed(SimpleNamespace(to_user="recipient@example.invalid"))
		access.changed.assert_called_once_with("recipient@example.invalid")
