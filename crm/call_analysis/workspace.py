"""Permission-scoped analysis runs; no writes to notes, audio or provider call facts.

Only this service can write storage. Every external request has a durable intent.
Unknown charges retain their reservation and suspend new AI work until reconciled.
"""

import math
from hashlib import sha256
from html import escape

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import get_datetime, now_datetime, today

from crm.api import call_work, celio_tasks
from crm.call_work_storage import internal_write

from . import provider
from .config import get_config
from .recording import download_recording

RUN = "CRM Call Analysis"
CONTROL = "CRM Call AI Control"
ACTIVE = ("Queued", "Processing")


def manager():
	return bool({"System Manager", "Sales Manager"} & set(frappe.get_roles()))


def shared_key_allowed():
	return frappe.conf.get("crm_call_analysis_allow_shared_key") is True


def _control(lock=False):
	return frappe.get_doc(CONTROL, "global", for_update=lock)


def _save(doc):
	with internal_write():
		doc.save(ignore_permissions=True)


def install():
	"""Idempotent site setup; never enables AI or installs a key."""
	if not frappe.db.exists(CONTROL, "global"):
		_save(
			frappe.get_doc(
				{
					"doctype": CONTROL,
					"name": "global",
					"__islocal": 1,
					"enabled": 0,
					"daily_limit": 1,
					"run_reserve": 0.25,
					"revision": 0,
				}
			)
		)

	frappe.db.add_index(RUN, ["call_log", "creation"], "call_analysis_versions")
	frappe.db.add_index(RUN, ["budget_day"], "call_analysis_budget_day")
	frappe.db.add_index(RUN, ["state"], "call_analysis_queue")


def _call(name, write=False, lock=False):
	if frappe.session.user == "Guest" or not frappe.db.get_value("User", frappe.session.user, "enabled"):
		frappe.throw(_("The requesting CRM account is disabled."), frappe.PermissionError)
	from crm.api.telephony import get_call, has_customer_reference

	get_call(name)
	doc = frappe.get_doc("CRM Call Log", name, for_update=lock)
	doc.check_permission("write" if write else "read")
	if has_customer_reference(doc) and lock:
		frappe.get_doc(doc.reference_doctype, doc.reference_docname, for_update=True).check_permission("read")
	return doc


def run_query(fields=None):
	from frappe.query_builder.functions import Coalesce

	from crm.api.telephony import REFERENCES, _reference_query, unlinked_condition

	t = frappe.qb.DocType(RUN)
	allowed = unlinked_condition(t)
	for dt in REFERENCES:
		if (permitted := _reference_query(dt)) is not None:
			allowed |= (t.reference_doctype == dt) & t.reference_docname.isin(permitted)
	return frappe.qb.from_(t).select(*(fields or [t.name])).where(allowed)


def recording_access(call):
	if not call.recording_url:
		return False
	if call.telephony_medium == "Exolve":
		from crm.integrations.exolve.api import check_recording_access

		try:
			check_recording_access(call)
		except (frappe.PermissionError, frappe.ValidationError):
			return False
	return True


def _latest(call, permitted=False, current=False):
	t = frappe.qb.DocType(RUN)
	q = run_query() if permitted else frappe.qb.from_(t).select(t.name)

	if current:
		q = q.for_update()
	rows = (
		q.where(t.call_log == call)
		.orderby(t.creation, order=Order.desc)
		.orderby(t.name, order=Order.desc)
		.limit(1)
		.run(as_dict=True)
	)
	return frappe.get_doc(RUN, rows[0].name, for_update=current) if rows else None


def _check_run(run):
	t = frappe.qb.DocType(RUN)
	if not run_query().where(t.name == run.name).limit(1).run():
		frappe.throw(_("This call analysis is not available."), frappe.PermissionError)
	from crm.api.telephony import has_customer_reference

	if has_customer_reference(run):
		frappe.get_doc(run.reference_doctype, run.reference_docname).check_permission("read")


def _used(day=None, current=False):
	t = frappe.qb.DocType(RUN)
	query = frappe.qb.from_(t).select(t.budget_charge).where(t.budget_day == (day or today()))
	if current:
		query = query.for_update()
	return sum(float(row[0] or 0) for row in query.run())


@frappe.whitelist()
def settings():
	from crm.api.telephony import _check_read

	_check_read()
	control = _control()
	data = {
		"enabled": bool(control.enabled),
		"configured": bool(get_config(require_api_key=False).api_key),
		"can_manage": manager(),
		"daily_limit": control.daily_limit,
		"run_reserve": control.run_reserve,
		"used": round(_used(), 6),
		"revision": control.revision,
		"blocked": bool(frappe.db.exists(RUN, {"state": "Uncertain"})),
		"provider": "OpenRouter",
		"shared_key": shared_key_allowed(),
		"transcription_model": provider.STT_MODEL,
		"summary_model": provider.SUMMARY_MODEL,
	}
	if data["can_manage"]:
		data["uncertain"] = frappe.get_all(
			RUN,
			filters={"state": "Uncertain"},
			fields=["name", "creation", "budget_charge", "actual_cost", "provider_ids"],
			limit=20,
		)
	return data


@frappe.whitelist(methods=["POST"])
def save_settings(enabled, daily_limit, run_reserve, expected_revision):
	if not manager():
		frappe.throw(_("Only a telephony manager can change AI spending settings."), frappe.PermissionError)
	try:
		daily, reserve = float(daily_limit), float(run_reserve)
		if not math.isfinite(daily) or not math.isfinite(reserve) or not 0.25 <= reserve <= daily <= 100:
			raise ValueError
	except (ValueError, TypeError):
		frappe.throw(_("Set a daily USD budget from 0.25 to 100 and a per-run reserve within it."))
	control = _control(True)
	if str(control.revision or 0) != str(expected_revision):
		frappe.throw(_("AI settings changed. Reload before saving."), frappe.TimestampMismatchError)
	# Configuration is separate from authorization. A saved key never enables AI.
	if str(enabled) in ("1", "True", "true"):
		if not get_config(require_api_key=False).api_key:
			frappe.throw(_("The AI service API key is not configured."))
		control.enabled = 1
	else:
		control.enabled = 0
	control.daily_limit, control.run_reserve = daily, reserve
	control.revision = (control.revision or 0) + 1
	_save(control)
	return settings()


def _gate(control):
	if not control.enabled:
		frappe.throw(_("Call AI is disabled. Enable it separately in AI budget settings."))
	get_config()
	t = frappe.qb.DocType(RUN)
	if frappe.qb.from_(t).select(t.name).where(t.state == "Uncertain").for_update().limit(1).run():
		frappe.throw(_("AI spending needs reconciliation before more calls can be processed."))


@frappe.whitelist(methods=["POST"])
def start(name, mutation_id, retry=0):
	return call_work._retry(lambda: _start(name, mutation_id, retry))


def _start(name, mutation_id, retry=0):
	if not isinstance(mutation_id, str) or not 16 <= len(mutation_id) <= 80:
		frappe.throw(_("Invalid analysis request."))
	_call(name, write=True)
	control = _control(True)  # serialize budget admission across all users/calls
	call = _call(name, write=True, lock=True)
	identity = sha256(f"{name}\0{frappe.session.user}\0{mutation_id}".encode()).hexdigest()
	if frappe.db.get_value(RUN, identity, "name", for_update=True, order_by=None):
		if not frappe.db.exists(RUN, identity):
			raise frappe.QueryDeadlockError
		return get(name)
	latest = _latest(name, current=True)
	if latest and not frappe.db.exists(RUN, latest.name):
		raise frappe.QueryDeadlockError
	if (
		latest
		and latest.state not in ACTIVE
		and (
			(latest.reference_doctype, latest.reference_docname)
			!= (call.reference_doctype, call.reference_docname)
			or latest.recording_source != call.recording_url
		)
	):
		latest = None
	if latest and latest.state in (*ACTIVE, "Completed", "Uncertain"):
		return get(name)
	if latest and not frappe.utils.cint(retry):
		frappe.throw(_("Review the error before explicitly retrying analysis."))
	_gate(control)
	if not recording_access(call):
		frappe.throw(
			_("Call recording is not available to the requesting CRM account."), frappe.PermissionError
		)
	if call.status not in ("Completed", "No Answer", "Busy", "Failed", "Canceled") or not call.recording_url:
		frappe.throw(_("Finish the call and wait for its recording before analysis."))
	if _used(current=True) + control.run_reserve > control.daily_limit + 0.00000001:
		frappe.throw(_("The daily AI budget is exhausted."))
	run = frappe.get_doc(
		{
			"doctype": RUN,
			"name": identity,
			"__islocal": 1,
			"call_log": name,
			"requested_by": frappe.session.user,
			"mutation_id": mutation_id,
			"state": "Queued",
			"budget_day": today(),
			"budget_charge": control.run_reserve,
			"actual_cost": 0,
			"recording_source": call.recording_url,
			"reference_doctype": call.reference_doctype,
			"reference_docname": call.reference_docname,
			"task_receipts": "{}",
			"stage": "queued",
		}
	)
	# A known failed summary reuses immutable raw output; no second transcription bill.
	if latest and latest.raw_transcript and latest.recording_source == call.recording_url:
		for field in ("raw_transcript", "segments", "stt_response", "recording_hash", "audio_seconds"):
			run.set(field, latest.get(field))
	_save(run)
	return get(name)


def error_label(message):
	labels = {
		"AI response was not received. Check provider usage before retrying.": "Ответ AI не получен. Сверьте расходы у провайдера перед повтором.",
		"AI cost is unknown. Reconcile provider usage before processing more calls.": "Стоимость AI неизвестна. Сверьте расходы перед обработкой следующих звонков.",
		"AI worker was interrupted. Reconcile provider usage before retrying.": "Обработка прервалась. Сверьте расходы AI перед повтором.",
		"Use a dedicated AI key with a daily USD limit no higher than the CRM budget, including BYOK.": "Нужен отдельный ключ OpenRouter с дневным лимитом в USD не выше бюджета CRM, с учётом BYOK.",
		"The bounded AI request cost exceeds its reservation.": "Предельная стоимость запроса превышает резерв. Анализ не запускался.",
		"The AI account cannot cover this request reserve.": "На аккаунте AI недостаточно средств для резерва этого запроса.",
		"The AI key cannot cover this request reserve.": "Остатка лимита ключа AI недостаточно для этого запроса.",
		"The AI key has no remaining budget.": "На AI-ключе закончился доступный бюджет.",
		"Transcription pricing changed or is unavailable. Review the AI budget before upload.": "Тариф распознавания изменился или недоступен. Проверьте модель и бюджет перед отправкой записи.",
		"Could not verify recording duration.": "Не удалось проверить длительность записи.",
		"AI supports recordings up to 10 minutes per analysis.": "Для одного анализа доступна запись до 10 минут.",
		"Unsupported recording format for AI.": "Этот формат записи не поддерживается распознаванием.",
		"Transcript is empty or too large for this analysis.": "Распознавание вернуло пустой или слишком большой текст. Исходный ответ сохранён.",
		"Invalid transcript timestamps; original AI response was retained.": "Временные метки распознавания некорректны. Исходный ответ сохранён.",
		"AI summary could not be validated; raw transcript was retained.": "Не удалось проверить итог AI. Исходная расшифровка сохранена; можно повторить подготовку итога.",
		"The recording changed. Start a new analysis after reviewing the source.": "Запись или карточка звонка изменилась. Проверьте источник и запустите новый анализ.",
		"AI cost reached the reserved amount; summary was not requested.": "Расход достиг резерва. Подготовка итога не запускалась.",
		"The AI request reserve is exhausted.": "Резерв на анализ исчерпан.",
		"The budget day changed. Resume the summary with a new explicit request.": "Начался новый бюджетный день. Подготовку итога можно продолжить отдельной командой.",
		"The daily AI budget is exhausted.": "Дневной бюджет AI исчерпан.",
		"The daily AI budget was lowered below current reservations.": "Новый бюджет AI меньше уже зарезервированной суммы.",
		"Call recording is not available to the requesting CRM account.": "Нет доступа к записи этого звонка. Проверьте учётную запись участника звонка.",
		"The requesting CRM account is disabled.": "Учётная запись автора запроса отключена.",
	}
	if message.startswith("AI service rejected the request (HTTP "):
		return _("AI-провайдер отклонил запрос. Сверьте его журнал расходов перед повтором.")
	return _(
		labels.get(message, "Не удалось завершить анализ. Проверьте доступ, настройки AI и журнал расходов.")
	)


def _project(run):
	receipts = frappe.parse_json(run.task_receipts or "{}")
	data = frappe.parse_json(run.summary_json or "{}")
	for i, task in enumerate(data.get("tasks", [])):
		if receipt := receipts.get(str(i)):
			try:
				task["created_task"] = celio_tasks.project(celio_tasks._task(receipt["task"]))
			except (frappe.PermissionError, frappe.DoesNotExistError):
				task["unavailable"] = True
	return {
		"name": run.name,
		"state": run.state,
		"error": error_label(run.error) if run.error else "",
		"raw_transcript": run.raw_transcript or "",
		"segments": frappe.parse_json(run.segments or "[]"),
		"analysis": data,
		"actual_cost": run.actual_cost,
		"budget_charge": run.budget_charge,
		"created": str(run.creation),
		"stage": run.stage,
		"legacy": False,
	}


@frappe.whitelist()
def get(name, run_name=None):
	call = _call(name)
	run = frappe.get_doc(RUN, run_name) if run_name else _latest(name, permitted=True)
	if run and run.call_log != name:
		frappe.throw(_("This call analysis is not available."), frappe.PermissionError)
	if run:
		_check_run(run)
	legacy = None
	if not run and (call.ai_transcript or call.ai_summary):
		legacy = {
			"state": "Completed",
			"legacy": True,
			"raw_transcript": call.ai_transcript or "",
			"segments": [],
			"analysis": {"summary": call.ai_summary or "", "agreements": [], "tasks": []},
		}
	return {
		"viewer": frappe.session.user,
		"can_start": frappe.has_permission("CRM Call Log", "write", call) and recording_access(call),
		"recording_unavailable": bool(call.recording_url) and not recording_access(call),
		"result": {**_project(run), "recording_matches": run.recording_source == call.recording_url}
		if run
		else legacy,
		"settings": settings(),
		"versions": run_query(
			[frappe.qb.DocType(RUN).name, frappe.qb.DocType(RUN).state, frappe.qb.DocType(RUN).creation]
		)
		.where(frappe.qb.DocType(RUN).call_log == name)
		.orderby(frappe.qb.DocType(RUN).creation, order=Order.desc)
		.limit(100)
		.run(as_dict=True),
	}


@frappe.whitelist(methods=["POST"])
def confirm_task(name, run_name, index, values, mutation_id, expected_viewer):
	def action():
		call_work._require(expected_viewer)
		call_work._lock_author()
		from crm.integrations.exolve.api import _lock_call

		_lock_call(name)
		call = _call(name, write=True, lock=True)
		run = frappe.get_doc(RUN, run_name, for_update=True)
		_check_run(run)
		if run.call_log != name or run.state != "Completed":
			frappe.throw(_("This AI suggestion is not available."), frappe.PermissionError)
		try:
			i = int(index)
			if str(i) != str(index) or i < 0:
				raise ValueError
			proposal = frappe.parse_json(run.summary_json)["tasks"][i]
		except (ValueError, TypeError, IndexError, KeyError):
			frappe.throw(_("This AI suggestion is not available."))
		values_ = frappe.parse_json(values) if isinstance(values, str) else values
		if (
			not isinstance(values_, dict)
			or set(values_) != {"title", "context_kind", "context_name", "assigned_to", "due_date"}
			or not all(isinstance(v, str) and v for v in values_.values())
			or not isinstance(mutation_id, str)
			or not 16 <= len(mutation_id) <= 80
		):
			frappe.throw(_("Choose a customer, assignee and task deadline."))
		try:
			get_datetime(values_["due_date"])
		except (ValueError, TypeError):
			frappe.throw(_("Choose a valid task deadline."))
		call_work._context(values_["context_kind"], values_["context_name"], current=True)
		receipts = frappe.parse_json(run.task_receipts or "{}")
		digest = sha256(frappe.as_json(values_).encode()).hexdigest()
		if previous := receipts.get(str(i)):
			if (
				previous["user"] != frappe.session.user
				or previous["mutation"] != mutation_id
				or previous["hash"] != digest
			):
				frappe.throw(_("This AI suggestion was already turned into a task. Reload the analysis."))
			return {"task": celio_tasks.project(celio_tasks._task(previous["task"])), "replayed": True}
		# Native task hooks own assignments, permissions and notification semantics.
		task = celio_tasks._save_task(
			{
				**values_,
				"status": "Todo",
				"priority": "Medium",
				"description": _("Suggested from call transcript") + "\n" + escape(proposal["evidence"]),
			},
			"ai-" + sha256(f"{run_name}\0{i}".encode()).hexdigest(),
			None,
			None,
			expected_viewer,
		)["task"]
		call.link_with_reference_doc("CRM Task", task["name"])
		flag = frappe.flags.in_exolve_sync
		try:
			frappe.flags.in_exolve_sync = True
			call.save(ignore_permissions=True)
		finally:
			frappe.flags.in_exolve_sync = flag
		receipts[str(i)] = {
			"task": task["name"],
			"user": frappe.session.user,
			"mutation": mutation_id,
			"hash": digest,
		}
		run.task_receipts = frappe.as_json(receipts)
		_save(run)
		return {"task": task, "replayed": False}

	return call_work._retry(action)


@frappe.whitelist(methods=["POST"])
def reconcile(run_name, actual_cost, note):
	if not manager():
		frappe.throw(_("Only a telephony manager can reconcile AI spending."), frappe.PermissionError)
	try:
		amount = float(actual_cost)
		if (
			not math.isfinite(amount)
			or amount < 0
			or not isinstance(note, str)
			or not 10 <= len(note.strip()) <= 500
		):
			raise ValueError
	except (ValueError, TypeError):
		frappe.throw(_("Enter the verified total USD cost and a provider usage reference."))
	control = _control(True)
	run = frappe.get_doc(RUN, run_name, for_update=True)
	if run.state != "Uncertain":
		frappe.throw(_("This AI run was already reconciled."))
	run.actual_cost, run.budget_charge = amount, amount
	run.reconciled_by, run.reconciliation_note = frappe.session.user, note
	run.state, run.stage = "Failed", "reconciled"
	_save(run)
	# Reconciliation never silently restarts work or re-enables AI.
	control.enabled, control.revision = 0, (control.revision or 0) + 1
	_save(control)
	return settings()


def _persist(run, **values):
	for key, value in values.items():
		run.set(key, value)
	_save(run)
	frappe.db.commit()


def process_one(name):
	"""Dedicated worker only. Durable intent before I/O prevents automatic paid retries."""
	original_user = frappe.session.user
	intent = False
	run = None
	try:
		control = _control(True)
		run = frappe.get_doc(RUN, name, for_update=True)
		if run.state != "Queued":
			return
		_gate(control)
		if not frappe.db.get_value("User", run.requested_by, "enabled"):
			raise provider.ProviderError("The requesting CRM account is disabled.")
		frappe.set_user(run.requested_by)
		call = _call(run.call_log, write=True)
		if call.recording_url != run.recording_source or (call.reference_doctype, call.reference_docname) != (
			run.reference_doctype,
			run.reference_docname,
		):
			raise provider.ProviderError(
				"The recording changed. Start a new analysis after reviewing the source."
			)
		_persist(run, state="Processing", stage="preflight")
		provider.check_key_budget(
			control.daily_limit,
			allow_shared=shared_key_allowed(),
			reserve=run.budget_charge - run.actual_cost,
		)
		if not run.raw_transcript:
			recording = download_recording(call, max_bytes=get_config().max_recording_bytes)
			duration = provider.audio_duration(recording.data)
			_persist(run, audio_seconds=duration, recording_hash=sha256(recording.data).hexdigest())
			_before_paid(run, "transcribing")
			intent = True
			response = provider.transcribe(recording)
			_persist(
				run, stt_response=frappe.as_json(response), provider_ids=str(response.get("id") or "")[:500]
			)
			# Save original response BEFORE validation or summary. Never replace raw text.
			text, segments = provider.transcript(response, duration)
			_persist(run, raw_transcript=text, segments=frappe.as_json(segments))
			charge = provider.cost(response)
			intent = False
			_persist(run, actual_cost=charge, stage="transcribed")
			if charge >= run.budget_charge:
				raise provider.ProviderError(
					"AI cost reached the reserved amount; summary was not requested."
				)
		_before_paid(run, "summarizing")
		intent = True
		response = provider.summarize(run.raw_transcript)
		_persist(
			run,
			summary_response=frappe.as_json(response),
			provider_ids=(run.provider_ids or "") + "\n" + str(response.get("id") or "")[:250],
		)
		charge = provider.cost(response)
		intent = False
		_persist(run, actual_cost=run.actual_cost + charge)
		data = provider.summary(response, run.raw_transcript)
		_persist(
			run,
			summary_json=frappe.as_json(data),
			state="Completed",
			stage="completed",
			budget_charge=run.actual_cost,
			error="",
		)
	except Exception as exc:
		frappe.db.rollback()
		if run:
			run.reload()
			# Safe errors only; never log credentials, signed audio URLs or raw conversation.
			message = (
				"Call recording is not available to the requesting CRM account."
				if isinstance(exc, frappe.PermissionError)
				else str(exc)
				if isinstance(exc, provider.ProviderError)
				else "AI analysis could not be completed. Check access and configuration."
			)
			unknown = intent
			_persist(
				run,
				state="Uncertain" if unknown else "Failed",
				error=message[:500],
				budget_charge=max(run.budget_charge, run.actual_cost) if unknown else run.actual_cost,
			)
	finally:
		frappe.set_user(original_user)


def _before_paid(run, stage):
	control = _control(True)
	_gate(control)
	# Each paid step starts a new permission check, including after raw ASR is saved.
	frappe.clear_cache(user=frappe.session.user)
	frappe.local.user_perms = None
	_check_run(run)
	_call(run.call_log, write=True)
	if str(run.budget_day) != today():
		if run.actual_cost:
			raise provider.ProviderError(
				"The budget day changed. Resume the summary with a new explicit request."
			)
		if _used(current=True) + run.budget_charge > control.daily_limit + 0.00000001:
			raise provider.ProviderError("The daily AI budget is exhausted.")
		run.budget_day = today()
	if _used(current=True) > control.daily_limit + 0.00000001:
		raise provider.ProviderError("The daily AI budget was lowered below current reservations.")
	provider.check_key_budget(
		control.daily_limit, allow_shared=shared_key_allowed(), reserve=run.budget_charge - run.actual_cost
	)
	if stage == "transcribing":
		rate = provider.check_transcription_price()
		quote = rate * math.ceil(run.audio_seconds) + provider.summary_cost_bound()
	else:
		quote = provider.summary_cost_bound(run.raw_transcript)
	if quote > run.budget_charge - run.actual_cost + 0.00000001:
		raise provider.ProviderError("The bounded AI request cost exceeds its reservation.")
	# Full request cost reserve; max summary tokens and routing prices are bounded.
	# Provider's dedicated daily key limit is the hard USD ceiling, not this estimate.
	if run.actual_cost >= run.budget_charge:
		raise provider.ProviderError("The AI request reserve is exhausted.")
	_persist(run, stage=stage)


def work():
	# A killed request may have cost money. Never auto-repeat it after restart.
	for row in frappe.get_all(RUN, filters={"state": "Processing"}, fields=["name", "modified"]):
		if (now_datetime() - row.modified).total_seconds() > 600:
			run = frappe.get_doc(RUN, row.name, for_update=True)
			_persist(
				run,
				state="Uncertain",
				error="AI worker was interrupted. Reconcile provider usage before retrying.",
			)
	for row in frappe.get_all(
		RUN, filters={"state": "Queued"}, fields=["name"], order_by="creation asc", limit=1
	):
		process_one(row.name)
