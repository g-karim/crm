# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from crm.api.notifications import get_hash
from crm.fcrm.doctype.crm_notification.crm_notification import CRMNotification


class TestCRMNotification(UnitTestCase):
	def test_messenger_hash_opens_conversation_tab(self):
		self.assertEqual(get_hash(frappe._dict(type="Messenger")), "#messenger")

	def test_realtime_notification_is_published_after_commit(self):
		doc = frappe._dict(
			name="NOTIFICATION-1",
			type="Messenger",
			to_user="manager@example.com",
			reference_name="LEAD-1",
		)
		with patch.object(frappe, "publish_realtime") as publish:
			CRMNotification.on_update(doc)

		publish.assert_called_once_with(
			"crm_notification",
			{"name": "NOTIFICATION-1", "type": "Messenger", "reference_name": "LEAD-1"},
			user="manager@example.com",
			after_commit=True,
		)
