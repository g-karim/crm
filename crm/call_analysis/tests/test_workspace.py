"""Native local permission/budget/confirmation acceptance. No external requests."""

import json
from contextlib import ExitStack
from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.utils import now_datetime, today

from crm.api import call_followups, telephony
from crm.call_analysis import analytics, provider
from crm.call_analysis import workspace as w
from crm.call_work_storage import internal_write

TEXT = "Я отправлю счёт завтра. Да, согласен."
STT = {
	"text": TEXT,
	"segments": [
		{"start": 0, "end": 2, "text": "Я отправлю счёт завтра."},
		{"start": 2, "end": 4, "text": "Да, согласен."},
	],
	"usage": {"cost": 0.01},
	"id": "mock-stt-only",
}
SUMMARY = {
	"choices": [
		{
			"finish_reason": "stop",
			"message": {
				"content": json.dumps(
					{
						"summary": "Договорились о счёте",
						"agreements": ["Отправить счёт"],
						"tasks": [{"title": "Отправить счёт", "evidence": "Я отправлю счёт завтра."}],
					},
					ensure_ascii=False,
				)
			},
		}
	],
	"usage": {"cost": 0.02},
	"id": "mock-summary-only",
}


class TestCallAIWorkspace(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.stack = ExitStack()
		self.addCleanup(self.cleanup)
		self.stack.enter_context(patch.object(frappe.db, "commit"))
		self.stack.enter_context(
			patch.object(frappe.db, "rollback")
		)  # restore DB explicitly after stopping mocks
		self.stack.enter_context(
			patch(
				"crm.call_analysis.workspace.get_config",
				return_value=SimpleNamespace(api_key="mock-only", max_recording_bytes=1024),
			)
		)
		self.key = self.stack.enter_context(patch("crm.call_analysis.provider.check_key_budget"))
		self.stack.enter_context(
			patch("crm.call_analysis.provider.check_transcription_price", return_value=0.0001)
		)
		self.network = self.stack.enter_context(
			patch(
				"crm.call_analysis.provider._request",
				side_effect=AssertionError("External request forbidden in local QA"),
			)
		)
		self.download = self.stack.enter_context(
			patch(
				"crm.call_analysis.workspace.download_recording",
				return_value=SimpleNamespace(
					data=b"original-audio", filename="test.wav", content_type="audio/wav"
				),
			)
		)
		self.stack.enter_context(patch("crm.call_analysis.provider.audio_duration", return_value=4))
		self.stt = self.stack.enter_context(patch("crm.call_analysis.provider.transcribe", return_value=STT))
		self.summary = self.stack.enter_context(
			patch("crm.call_analysis.provider.summarize", return_value=SUMMARY)
		)
		self.tag = "Stage4QA" + uuid4().hex[:10]
		self.user = self.tag.lower() + "@example.invalid"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.user,
				"first_name": self.tag,
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert()
		self.lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": self.tag, "status": "New", "lead_owner": self.user}
		).insert()
		self.flag = frappe.flags.in_exolve_sync
		frappe.flags.in_exolve_sync = True
		control = w._control(True)
		control.enabled = 1
		control.daily_limit = 1
		control.run_reserve = 0.25
		w._save(control)
		frappe.set_user(self.user)
		self.call = self.make_call()

	def cleanup(self):
		self.stack.close()
		frappe.db.rollback()
		frappe.db.after_commit.reset()
		frappe.flags.in_exolve_sync = getattr(self, "flag", None)
		frappe.set_user("Administrator")

	def make_call(self, direction="Outgoing", status="Completed", minutes=0, recording=True):
		return frappe.get_doc(
			{
				"doctype": "CRM Call Log",
				"telephony_medium": "Manual",
				"type": direction,
				"status": status,
				"from": "79990000401" if direction == "Outgoing" else "79990000402",
				"to": "79990000402" if direction == "Outgoing" else "79990000401",
				"caller": self.user,
				"receiver": self.user,
				"reference_doctype": "CRM Lead",
				"reference_docname": self.lead.name,
				"start_time": now_datetime() + timedelta(minutes=minutes),
				"duration": 4 if status == "Completed" else 0,
				"recording_url": "https://media.example.invalid/fixture.wav" if recording else "",
			}
		).insert()

	def start(self, call=None, mutation=None, retry=0):
		return w.start((call or self.call).name, mutation or str(uuid4()), retry)

	def process(self):
		run = self.start()["result"]
		w.process_one(run["name"])
		return w.get(self.call.name)["result"]

	def test_raw_asr_original_audio_and_native_call_are_preserved(self):
		self.call.reload()
		before = json.loads(frappe.as_json(self.call.as_dict()))
		result = self.process()
		self.assertEqual(result["state"], "Completed")
		self.assertEqual(result["raw_transcript"], TEXT)
		self.assertNotIn("transcript", result["analysis"])
		self.assertEqual(result["actual_cost"], 0.03)
		self.assertEqual(result["budget_charge"], 0.03)
		self.assertEqual(result["segments"], STT["segments"])
		self.call.reload()
		self.assertEqual(json.loads(frappe.as_json(self.call.as_dict())), before)
		self.assertEqual(self.download.call_count, 1)
		self.network.assert_not_called()

	def test_saved_key_does_not_enable_ai_or_automatic_processing(self):
		control = w._control()
		control.enabled = 0
		w._save(control)
		with self.assertRaises(frappe.ValidationError):
			self.start()
		self.stt.assert_not_called()
		self.summary.assert_not_called()

	def test_exact_request_retry_and_active_call_do_not_duplicate_paid_work(self):
		mutation = str(uuid4())
		first = self.start(mutation=mutation)["result"]
		self.assertEqual(self.start(mutation=mutation)["result"]["name"], first["name"])
		self.assertEqual(self.start()["result"]["name"], first["name"])
		w.process_one(first["name"])
		w.process_one(first["name"])
		self.assertEqual(self.stt.call_count, 1)
		self.assertEqual(self.summary.call_count, 1)
		self.assertEqual(self.start()["result"]["state"], "Completed")

	def test_all_users_share_daily_reservations_before_network(self):
		control = w._control()
		control.daily_limit = 0.25
		w._save(control)
		self.start()
		second = self.make_call()
		with self.assertRaises(frappe.ValidationError):
			self.start(second)
		self.stt.assert_not_called()

	def test_unknown_paid_response_holds_budget_and_blocks_new_calls(self):
		self.stt.side_effect = provider.UnknownCharge("Response lost")
		result = self.process()
		self.assertEqual(result["state"], "Uncertain")
		self.assertEqual(result["budget_charge"], 0.25)
		self.summary.assert_not_called()
		with self.assertRaises(frappe.ValidationError):
			self.start(self.make_call())

	def test_missing_cost_retains_raw_transcript_without_summary(self):
		self.stt.return_value = {k: v for k, v in STT.items() if k != "usage"}
		result = self.process()
		self.assertEqual(result["state"], "Uncertain")
		self.assertEqual(result["raw_transcript"], TEXT)
		self.summary.assert_not_called()

	def test_known_bad_summary_retry_reuses_asr_and_counts_actual_charges(self):
		self.summary.return_value = {**SUMMARY, "choices": []}
		result = self.process()
		self.assertEqual(result["state"], "Failed")
		self.assertEqual(result["raw_transcript"], TEXT)
		self.assertEqual(result["budget_charge"], 0.03)
		self.summary.return_value = SUMMARY
		run = self.start(retry=1)["result"]
		w.process_one(run["name"])
		result = w.get(self.call.name)["result"]
		self.assertEqual(result["state"], "Completed")
		self.assertEqual(self.stt.call_count, 1)
		self.assertEqual(result["actual_cost"], 0.02)

	def test_worker_rechecks_user_and_current_customer_access_before_audio_leaves(self):
		run = self.start()["result"]
		frappe.set_user("Administrator")
		frappe.db.set_value("User", self.user, "enabled", 0)
		w.process_one(run["name"])
		self.stt.assert_not_called()
		self.download.assert_not_called()
		self.assertEqual(frappe.db.get_value(w.RUN, run["name"], "state"), "Failed")

	def test_worker_does_not_analyze_replaced_recording(self):
		run = self.start()["result"]
		frappe.db.set_value(
			"CRM Call Log", self.call.name, "recording_url", "https://media.example.invalid/changed.wav"
		)
		w.process_one(run["name"])
		self.download.assert_not_called()
		self.assertEqual(w.get(self.call.name)["result"]["state"], "Failed")

	def test_suggestions_only_create_native_tasks_after_explicit_confirmation(self):
		count = frappe.db.count("CRM Task")
		result = self.process()
		self.assertEqual(frappe.db.count("CRM Task"), count)
		values = {
			"title": "Проверенный счёт",
			"context_kind": "lead",
			"context_name": self.lead.name,
			"assigned_to": self.user,
			"due_date": today() + " 23:00:00",
		}
		mutation = str(uuid4())
		first = w.confirm_task(self.call.name, result["name"], 0, values, mutation, self.user)
		second = w.confirm_task(self.call.name, result["name"], 0, values, mutation, self.user)
		self.assertTrue(second["replayed"])
		self.assertEqual(first["task"]["name"], second["task"]["name"])
		self.assertEqual(frappe.db.count("CRM Task"), count + 1)
		task = frappe.get_doc("CRM Task", first["task"]["name"])
		self.assertEqual(task.reference_docname, self.lead.name)
		self.call.reload()
		self.assertTrue(self.call.has_link("CRM Task", str(task.name)))
		with self.assertRaises(frappe.ValidationError):
			w.confirm_task(self.call.name, result["name"], 0, values, str(uuid4()), self.user)

	def test_analysis_and_transcript_search_recheck_call_customer_permissions(self):
		self.process()
		self.assertEqual(
			[r["name"] for r in telephony.get_calls(search="отправлю")["calls"]], [self.call.name]
		)
		with patch("crm.api.telephony._reference_query", return_value=None):
			self.assertEqual(telephony.get_calls(search="отправлю")["calls"], [])
			with self.assertRaises(frappe.PermissionError):
				w.get(self.call.name)
			self.assertEqual(analytics.report(search="отправлю")["counts"]["total"], 0)

	def test_team_metrics_cover_full_history_not_first_page_and_agree_with_filters(self):
		for _ in range(42):
			self.make_call()
		self.make_call(direction="Incoming", status="No Answer", recording=False)
		page = telephony.get_calls(search=self.tag, page_length=2)
		self.assertTrue(page["has_more"])
		self.assertEqual(len(page["calls"]), 2)
		data = analytics.report(search=self.tag)
		self.assertEqual(data["counts"]["total"], 44)
		self.assertEqual(data["counts"]["completed"], 43)
		self.assertEqual(data["counts"]["missed"], 1)
		self.assertEqual(data["duration_seconds"], 172)
		self.assertEqual(analytics.report(search=self.tag, view="missed")["counts"]["total"], 1)
		self.assertEqual(analytics.report(search=self.tag, line="unknown")["counts"]["total"], 0)

	def test_callback_speed_needs_explicit_link_and_task_completion_is_not_a_call(self):
		missed = self.make_call(direction="Incoming", status="No Answer", minutes=-10, recording=False)
		review = call_followups.save_outcome(
			missed.name,
			"Callback",
			0,
			str(uuid4()),
			self.user,
			{
				"title": "Перезвонить",
				"context_kind": "lead",
				"context_name": self.lead.name,
				"assigned_to": self.user,
				"due_date": today() + " 23:00:00",
			},
		)
		self.assertEqual(analytics.report(search=self.tag)["callback_attempts"], 0)
		self.assertIn(self.call.name, [r["name"] for r in analytics.callback_candidates(missed.name)])
		analytics.link_callback(missed.name, self.call.name, review["review"]["revision"], self.user)
		data = analytics.report(search=self.tag)
		self.assertEqual(data["callback_attempts"], 1)
		self.assertGreater(data["callback_median_seconds"], 590)
		self.assertEqual(data["tasks"]["open"], 1)

	def test_ai_service_storage_has_no_direct_crud_permission(self):
		for dt in (w.RUN, w.CONTROL):
			self.assertFalse(frappe.has_permission(dt, "read"))
			self.assertFalse(frappe.has_permission(dt, "create"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": w.RUN, "name": "forged", "call_log": self.call.name}).insert(
				ignore_permissions=True
			)

	def test_manager_settings_use_cas_and_never_enable_without_key(self):
		with self.assertRaises(frappe.PermissionError):
			w.save_settings(1, 1, 0.25, 0)
		frappe.set_user("Administrator")
		control = w._control()
		with self.assertRaises(frappe.TimestampMismatchError):
			w.save_settings(1, 1, 0.25, 999)
		with patch("crm.call_analysis.workspace.get_config", return_value=SimpleNamespace(api_key="")):
			with self.assertRaises(frappe.ValidationError):
				w.save_settings(1, 1, 0.25, control.revision)

	def test_original_analysis_stays_immutable_even_during_an_internal_update(self):
		result = self.process()
		run = frappe.get_doc(w.RUN, result["name"])
		run.raw_transcript = "Rewritten by summary"
		with internal_write(), self.assertRaises(frappe.ValidationError):
			run.save(ignore_permissions=True)

	def test_old_customer_access_is_rechecked_after_call_is_relinked(self):
		result = self.process()
		frappe.set_user("Administrator")
		other = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": self.tag + " other",
				"status": "New",
				"lead_owner": self.user,
			}
		).insert()
		frappe.db.set_value("CRM Call Log", self.call.name, "reference_docname", other.name)
		frappe.db.set_value("CRM Lead", self.lead.name, "lead_owner", "Administrator")
		frappe.db.set_value(
			"ToDo",
			{"reference_type": "CRM Lead", "reference_name": self.lead.name, "allocated_to": self.user},
			"status",
			"Cancelled",
		)
		frappe.share.remove("CRM Lead", self.lead.name, self.user)
		frappe.clear_cache(user=self.user)
		frappe.set_user(self.user)
		self.assertEqual(telephony.get_call(self.call.name)["reference"]["name"], other.name)
		self.assertIsNone(w.get(self.call.name)["result"])
		with self.assertRaises(frappe.PermissionError):
			w.get(self.call.name, result["name"])
		self.assertEqual(telephony.get_calls(search="отправлю")["calls"], [])

	def test_reconciliation_records_verified_cost_and_keeps_ai_disabled(self):
		self.stt.side_effect = provider.UnknownCharge("Response lost")
		result = self.process()
		with self.assertRaises(frappe.PermissionError):
			w.reconcile(result["name"], 0.015, "provider-operation-123")
		frappe.set_user("Administrator")
		data = w.reconcile(result["name"], 0.015, "provider-operation-123")
		self.assertFalse(data["enabled"])
		self.assertFalse(data["blocked"])
		run = frappe.get_doc(w.RUN, result["name"])
		self.assertEqual(run.budget_charge, 0.015)
		self.assertEqual(run.reconciled_by, "Administrator")

	def test_pausing_ai_stops_an_admitted_run_before_transmission(self):
		run = self.start()["result"]
		control = w._control()
		control.enabled = 0
		w._save(control)
		w.process_one(run["name"])
		self.download.assert_not_called()
		self.stt.assert_not_called()
		self.summary.assert_not_called()

	def test_replaced_recording_gets_a_new_version_without_seeking_old_timestamps(self):
		previous = self.process()
		frappe.db.set_value(
			"CRM Call Log", self.call.name, "recording_url", "https://media.example.invalid/new.wav"
		)
		self.assertFalse(w.get(self.call.name)["result"]["recording_matches"])
		new = self.start()["result"]
		self.assertNotEqual(new["name"], previous["name"])
		self.assertEqual(new["state"], "Queued")
		self.assertEqual(w.get(self.call.name, previous["name"])["result"]["raw_transcript"], TEXT)

	def test_legacy_default_lead_without_name_is_read_as_unlinked_without_mutation(self):
		frappe.db.set_value("CRM Call Log", self.call.name, "reference_docname", None)
		self.assertIsNone(telephony.get_call(self.call.name)["reference"])
		result = self.process()
		self.assertEqual(result["state"], "Completed")
		self.call.reload()
		self.assertEqual(self.call.reference_doctype, "CRM Lead")
		self.assertIsNone(self.call.reference_docname)

	def test_inaccessible_exolve_recording_is_rejected_before_any_reservation(self):
		with patch("crm.call_analysis.workspace.recording_access", return_value=False):
			self.assertFalse(w.get(self.call.name)["can_start"])
			with self.assertRaises(frappe.PermissionError):
				self.start()
		self.stt.assert_not_called()
