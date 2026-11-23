"""Explicit synthetic fixtures for disposable local analytics acceptance only."""

from contextlib import ExitStack, contextmanager
from datetime import datetime
from unittest.mock import patch

import frappe

from crm.analytics.fixtures import acceptance_data


@contextmanager
def clock(value):
	when = datetime.fromisoformat(value)
	class FrozenDateTime(datetime):
		@classmethod
		def now(cls, tz=None):
			return when if tz is None else when.replace(tzinfo=tz)
	with ExitStack() as stack:
		for target in ["frappe.utils.data.now_datetime", "frappe.utils.now_datetime", "crm.analytics.history.now_datetime", "crm.analytics.service.now_datetime"]:
			stack.enter_context(patch(target, return_value=when))
		stack.enter_context(patch("crm.fcrm.doctype.crm_status_change_log.crm_status_change_log.datetime", FrozenDateTime))
		yield


def seed(prefix="analytics-demo", *, transactional=False):
	shared_transaction = (transactional and frappe.local.site in {"analytics.localhost", "analytics-qa.localhost"}
		and frappe.flags.analytics_local_validation is True)
	if not shared_transaction and (frappe.local.site != "crm-analytics-acceptance.localhost"
		or not frappe.conf.developer_mode):
		raise RuntimeError("Analytics fixtures require an isolated site or the guarded rollback validator")
	if frappe.session.user != "Administrator":
		raise RuntimeError("Fixture administration is restricted to the local test account")
	if frappe.db.exists("CRM Deal", prefix + "-D1"):
		raise RuntimeError("Fixture exists; do not overwrite user changes or learning data")
	frappe.db.set_single_value("FCRM Settings", "currency", "RUB")
	frappe.db.set_single_value("FCRM Settings", "enable_forecasting", 0)
	frappe.db.set_single_value("FCRM Settings", "auto_update_expected_deal_value", 0)
	users = {"A": "analytics.a@example.invalid", "B": "analytics.b@example.invalid", "manager": "analytics.manager@example.invalid"}
	for key, name in users.items():
		if not frappe.db.exists("User", name):
			frappe.get_doc({"doctype": "User", "email": name, "first_name": "Analytics " + key,
				"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
				"roles": [{"role": "Sales Manager" if key == "manager" else "Sales User"}],
			}).insert()
	pipelines = {}
	stages = {}
	for key in ["Main", "Extra"]:
		name = prefix + " " + key
		pipelines[key] = frappe.get_doc({"doctype": "CRM Sales Pipeline", "pipeline_name": name, "enabled": 1}).insert().name
		for label, kind, probability, position in [("Qualification", "Open", 0, 1), ("Proposal", "Ongoing", 50, 2), ("Won", "Won", 100, 3), ("Lost", "Lost", 0, 4)]:
			stage = frappe.get_doc({"doctype": "CRM Deal Status", "pipeline": pipelines[key], "deal_status": label,
				"type": kind, "probability": probability, "position": position, "color": "gray"}).insert()
			stages[(key, label)] = stage.name
	for source in ["Web", "Referral"]:
		if not frappe.db.exists("CRM Lead Source", source):
			frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source}).insert()
	if not frappe.db.exists("CRM Lost Reason", "Analytics Price"):
		frappe.get_doc({"doctype": "CRM Lost Reason", "lost_reason": "Analytics Price"}).insert()
	data = acceptance_data()
	leads, deals, tasks = {}, {}, {}
	for row in data["leads"]:
		with clock(row["creation"]):
			leads[row["name"]] = frappe.get_doc({"doctype": "CRM Lead", "first_name": "Контрольный лид " + row["name"],
				"status": "New", "lead_owner": users[row["owner"]], "source": row["source"],
				"planned_deal_pipeline": pipelines[row["pipeline"]]}).insert(set_name=prefix + "-" + row["name"]).name
	with patch("crm.fcrm.doctype.crm_deal.crm_deal.get_exchange_rate", side_effect=lambda source, target: 100 if source == "EUR" and target == "RUB" else 1):
		for row in data["deals"]:
			with clock(row["creation"]):
				doc = frappe.get_doc({"doctype": "CRM Deal", "deal_name": "Контрольная сделка " + row["name"],
					"pipeline": pipelines[row["pipeline"]], "status": stages[(row["pipeline"], "Qualification")],
					"deal_owner": users[row["owner"]], "source": row["source"], "lead": leads.get(row.get("lead")),
					"deal_value": row["value"], "expected_deal_value": row["expected_value"], "probability": row["probability"],
					"currency": row["currency"], "expected_closure_date": row["expected_date"],
				}).insert(set_name=prefix + "-" + row["name"])
				deals[row["name"]] = doc.name
			if row.get("lead"):
				with clock(row["creation"]):
					lead = frappe.get_doc("CRM Lead", leads[row["lead"]])
					lead.converted = 1
					lead.save()
			if row["status_type"] in {"Won", "Lost"}:
				when = row["closed_date"] or row["lost_date"]
				with clock(when + " 12:00:00"):
					doc.reload()
					doc.status = stages[(row["pipeline"], row["status_type"])]
					if row["status_type"] == "Lost":
						doc.lost_reason = "Analytics Price"
					doc.save()
			elif row["status"] == "Proposal":
				with clock(row["stage_entered_at"]):
					doc.reload(); doc.status = stages[(row["pipeline"], "Proposal")]; doc.save()
	for row in data["tasks"]:
		with clock("2026-10-25 12:00:00"):
			task = frappe.get_doc({"doctype": "CRM Task", "title": "Контрольная задача " + row["reference_name"],
				"status": row["status"], "due_date": row["due_date"], "reference_doctype": "CRM Deal",
				"reference_docname": deals[row["reference_name"]],
				"assigned_to": users[next(d["owner"] for d in data["deals"] if d["name"] == row["reference_name"])]}).insert()
			tasks[row["name"]] = task.name
	frappe.clear_cache()
	return {"prefix": prefix, "users": users, "pipelines": pipelines,
		"stages": {key + ":" + label: value for (key, label), value in stages.items()},
		"leads": leads, "deals": deals, "tasks": tasks}
