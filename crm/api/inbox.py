"""One inbox over source-owned messages and mail, with independent private state.

Reading never calls a provider or changes source read cursors. Account grants,
native customer permissions and per-message email account access all apply before
search, counts and pagination. No matching on names, subjects or phone numbers.
"""

from email.utils import getaddresses
from hashlib import sha256
from urllib.parse import quote

import frappe
from bs4 import BeautifulSoup
from frappe.query_builder import Order
from frappe.utils import cint, escape_html, get_datetime, now_datetime

from crm.inbox_storage import internal_write

KINDS = {"messenger", "email"}
CONTEXTS = {"CRM Lead": ("lead_name", "leads"), "CRM Deal": ("deal_name", "deals")}
STATUSES = {"needs_reply", "waiting_customer", "snoozed", "closed"}
WORK = "CRM Inbox Work"
STATE = "CRM Inbox State"
ACCESS = "CRM Inbox Access"
OP = "CRM Inbox Operation"


def _require():
	u = frappe.session.user
	if (
		u == "Guest"
		or not frappe.db.get_value("User", u, "enabled")
		or not (
			_admin()
			or set(frappe.get_roles()).intersection(
				{"Sales User", "Sales Manager", "CRM User", "CRM Manager"}
			)
		)
	):
		frappe.throw("Мессенджер недоступен этому пользователю.", frappe.PermissionError)


def _admin(user=None):
	u = user or frappe.session.user
	return u == "Administrator" or "System Manager" in frappe.get_roles(u)


def _expect_viewer(expected_viewer=None):
	_require()
	if expected_viewer is not None and expected_viewer != frappe.session.user:
		frappe.throw("Пользователь изменился. Обновите страницу перед сохранением.", frappe.PermissionError)


def _key(*parts):
	return sha256("\0".join(str(p or "") for p in parts).encode()).hexdigest()


def _plain(text):
	return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _json(value, default=None):
	if value in (None, ""):
		return {} if default is None else default
	return frappe.parse_json(value) if isinstance(value, str) else value


def _account_allowed(kind, account, user=None, send=False):
	u = user or frappe.session.user
	if _admin(u):
		return True
	if not account:
		return False
	grant = frappe.db.get_value(ACCESS, _key(kind, account, u), ["can_read", "can_send"], as_dict=True)
	if grant:
		return bool(grant.can_read and (not send or grant.can_send))
	if kind == "email":
		return bool(
			frappe.db.exists("User Email", {"parent": u, "parenttype": "User", "email_account": account})
		)
	return False


def _reference_allowed(dt, name, write=False, user=None):
	if not dt and not name:
		return _admin(user)
	return bool(
		dt in CONTEXTS
		and name
		and frappe.db.exists(dt, name)
		and frappe.has_permission(dt, "write" if write else "read", doc=name, user=user)
	)


def _source_allowed(kind, row, write=False, user=None):
	account = row.channel if kind == "messenger" else row.email_account
	return _account_allowed(kind, account, user, send=write) and _reference_allowed(
		row.reference_doctype, row.reference_name, write, user
	)


def _allowed_rows(kind):
	"""Source scans contain headers only; bodies are loaded after authorization."""
	if kind == "messenger":
		if not frappe.db.exists("DocType", "Messenger Conversation"):
			return []
		rows = frappe.get_all(
			"Messenger Conversation",
			fields=[
				"name",
				"channel",
				"provider",
				"provider_chat_key",
				"chat_type",
				"client_name",
				"client_phone",
				"reference_doctype",
				"reference_name",
				"status",
				"creation",
			],
		)
	else:
		rows = frappe.get_all(
			"Communication",
			filters={"communication_medium": "Email", "communication_type": "Communication"},
			fields=[
				"name",
				"email_account",
				"reference_doctype",
				"reference_name",
				"subject",
				"sender",
				"sender_full_name",
				"recipients",
				"sent_or_received",
				"in_reply_to",
				"communication_date",
				"creation",
				"delivery_status",
				"message_id",
			],
		)
	return [r for r in rows if _source_allowed(kind, r)]


def _email_root(row, allowed):
	seen = set()
	while row.in_reply_to in allowed and row.name not in seen:
		seen.add(row.name)
		parent = allowed[row.in_reply_to]
		# Keep account/customer boundaries even if a malformed native reply link crosses them.
		if (parent.email_account, parent.reference_doctype, parent.reference_name) != (
			row.email_account,
			row.reference_doctype,
			row.reference_name,
		):
			break
		row = parent
	return min(seen | {row.name}) if row.name in seen else row.name


def _groups(kind):
	rows = _allowed_rows(kind)
	if kind == "messenger":
		return {r.name: [r] for r in rows}
	allowed = {r.name: r for r in rows}
	groups = {}
	for row in rows:
		groups.setdefault(_email_root(row, allowed), []).append(row)
	return groups


def _load(kind, name, write=False, lock=False):
	_require()
	if kind not in KINDS or not isinstance(name, str):
		frappe.throw("Диалог недоступен.", frappe.PermissionError)
	dt = "Messenger Conversation" if kind == "messenger" else "Communication"
	if not frappe.db.exists(dt, name):
		frappe.throw("Диалог недоступен.", frappe.PermissionError)
	source = frappe.get_doc(dt, name, for_update=lock)
	if not _source_allowed(kind, source, write):
		frappe.throw("Нет доступа к аккаунту или карточке клиента.", frappe.PermissionError)
	if kind == "email" and (
		source.communication_medium != "Email" or source.communication_type != "Communication"
	):
		frappe.throw("Диалог недоступен.", frappe.PermissionError)
	groups = _groups(kind) if kind == "email" else {name: [source]}
	if name not in groups:
		frappe.throw("Цепочка изменилась. Обновите список.", frappe.ValidationError)
	return source, groups[name]


def _row(dt, key):
	return frappe.get_doc(dt, key) if frappe.db.exists(dt, key) else None


def _save(dt, key, values):
	with internal_write():
		previous = _row(dt, key)
		doc = previous or frappe.get_doc({"doctype": dt, "name": key})
		doc.update(values)
		if previous:
			doc.save(ignore_permissions=True)
		else:
			doc.insert(ignore_permissions=True)
	return doc


def _lock_user():
	frappe.db.get_value("User", frappe.session.user, "enabled", for_update=True)
	_require()


def _work(kind, name):
	doc = _row(WORK, _key(kind, name))
	return {
		"revision": cint(doc.revision) if doc else 0,
		"status": doc.status if doc else "",
		"assigned_to": (doc.assigned_to or "") if doc else "",
		"snoozed_until": str(doc.snoozed_until or "") if doc else "",
		"watermark": doc.watermark if doc else "",
		"context_doctype": doc.context_doctype if doc else "",
		"context_name": doc.context_name if doc else "",
	}


def _private(kind, name):
	doc = _row(STATE, _key(kind, name, frappe.session.user))
	return {
		"revision": cint(doc.revision) if doc else 0,
		"draft": _json(doc.data) if doc else {},
		"read_cursor": _json(doc.read_cursor, []) if doc else [],
	}


def _messages(kind, rows):
	if kind == "messenger":
		return frappe.get_all(
			"Messenger Message",
			filters={"conversation": rows[0].name, "status": ["!=", "deleted"]},
			fields=["name", "creation", "message_datetime", "direction", "text", "message_type", "status"],
			order_by="message_datetime asc, creation asc, name asc",
		)
	return [
		frappe._dict(
			{
				"name": r.name,
				"creation": r.creation,
				"message_datetime": r.communication_date or r.creation,
				"direction": "inbound" if r.sent_or_received == "Received" else "outbound",
				"status": r.delivery_status,
				"text": r.subject,
			}
		)
		for r in sorted(
			rows, key=lambda r: (str(r.communication_date or r.creation), str(r.creation), r.name)
		)
	]


def _restricted(kind, source):
	if kind != "messenger" or source.provider != "avito_direct" or not source.channel:
		return False
	from crm_messenger.services.avito_access import messenger_restricted

	return messenger_restricted(frappe.get_doc("Messenger Channel", source.channel))


def _cursor(m):
	return [str(m.creation), m.name]


def _project(kind, name, rows):
	source = rows[0] if kind == "messenger" else next(r for r in rows if r.name == name)
	msgs = _messages(kind, rows)
	latest = msgs[-1] if msgs else None
	work, private = _work(kind, name), _private(kind, name)
	watermark = frappe.as_json(max((_cursor(m) for m in msgs if m.direction == "inbound"), default=[]))
	status = work["status"] or (
		"needs_reply" if latest and latest.direction == "inbound" else "waiting_customer"
	)
	if (
		status in {"closed", "waiting_customer", "snoozed"}
		and work["watermark"]
		and _json(watermark, []) > _json(work["watermark"], [])
	):
		status = "needs_reply"
	if (
		status == "snoozed"
		and work["snoozed_until"]
		and get_datetime(work["snoozed_until"]) <= now_datetime()
	):
		status = "needs_reply"
	unread = sum(1 for m in msgs if m.direction == "inbound" and _cursor(m) > private["read_cursor"])
	account = source.channel if kind == "messenger" else source.email_account
	channel = (
		frappe.db.get_value(
			"Messenger Channel",
			account,
			["custom_display_name", "provider_display_name", "platform"],
			as_dict=True,
		)
		if kind == "messenger" and account
		else None
	)
	title = source.client_name if kind == "messenger" else source.sender_full_name or source.sender
	if source.reference_doctype in CONTEXTS and source.reference_name:
		title = (
			frappe.db.get_value(
				source.reference_doctype, source.reference_name, CONTEXTS[source.reference_doctype][0]
			)
			or title
		)
	return {
		"kind": kind,
		"name": name,
		"id": f"{kind}:{name}",
		"title": title or "Новый клиент",
		"account": account or "",
		"account_label": (channel.custom_display_name or channel.provider_display_name or account)
		if channel
		else account or "Ящик не указан",
		"channel": (channel.platform if channel else source.chat_type) if kind == "messenger" else "email",
		"subject": source.subject if kind == "email" else "",
		"preview": "Содержимое недоступно по условиям канала."
		if _restricted(kind, source)
		else _plain(latest.text)[:180]
		if latest
		else "Сообщений пока нет",
		"last_at": str(latest.message_datetime or latest.creation) if latest else str(source.creation),
		"status": status,
		"unread": unread,
		"work": work,
		"watermark": watermark,
		"reference_doctype": source.reference_doctype or "",
		"reference_name": source.reference_name or "",
		"can_operate": _source_allowed(kind, source, True),
		"demo": _is_demo(kind, source),
	}


def _is_demo(kind, source):
	if not frappe.conf.get("crm_inbox_demo_enabled"):
		return False
	if kind == "messenger":
		return bool(source.provider_chat_key and source.provider_chat_key.startswith("local-inbox-demo:"))
	return bool(not source.email_account and str(source.message_id or "").endswith("@inbox.local.invalid>"))


@frappe.whitelist()
def list_threads(
	view="open", query="", channel="", account="", reference_doctype="", reference_name="", offset=0, limit=30
):
	_require()
	items = []
	for kind in KINDS:
		for name, rows in _groups(kind).items():
			source = rows[0] if kind == "messenger" else next(r for r in rows if r.name == name)
			# Safe source projection needs no tokens, provider raw payloads or email bodies.
			if reference_doctype and not any(
				(c["doctype"], c["name"]) == (reference_doctype, reference_name) for c in _contexts(source)
			):
				continue
			item = _project(kind, name, rows)
			if (channel and channel != item["channel"]) or (account and account != item["account"]):
				continue
			if query:
				needle = str(query).strip().casefold()[:200]
				haystack = " ".join([item["title"], item["subject"], item["preview"]])
				if needle not in haystack.casefold():
					if _restricted(kind, source):
						continue
					if kind == "messenger":
						texts = frappe.get_all(
							"Messenger Message",
							filters={"conversation": name, "status": ["!=", "deleted"]},
							pluck="text",
						)
					else:
						texts = [frappe.db.get_value("Communication", r.name, "content") for r in rows]
					if not any(needle in _plain(t).casefold() for t in texts):
						continue
			items.append(item)
	counts = {
		k: sum(_matches(item, k) for item in items)
		for k in [
			"open",
			"mine",
			"unassigned",
			"needs_reply",
			"waiting_customer",
			"snoozed",
			"closed",
			"unread",
			"all",
		]
	}
	filtered = sorted(
		[i for i in items if _matches(i, view)], key=lambda i: (i["last_at"], i["id"]), reverse=True
	)
	offset, limit = max(0, cint(offset)), min(100, max(1, cint(limit)))
	return {
		"items": filtered[offset : offset + limit],
		"counts": counts,
		"has_more": offset + limit < len(filtered),
		"viewer": frappe.session.user,
		"accounts": accounts(),
		"total": len(filtered),
	}


def _matches(item, view):
	status = item["status"]
	return {
		"all": True,
		"open": status != "closed",
		"mine": item["work"]["assigned_to"] == frappe.session.user and status != "closed",
		"unassigned": not item["work"]["assigned_to"] and status != "closed",
		"unread": item["unread"] > 0,
		"needs_reply": status == "needs_reply",
		"waiting_customer": status == "waiting_customer",
		"snoozed": status == "snoozed",
		"closed": status == "closed",
	}.get(view, False)


@frappe.whitelist()
def accounts():
	_require()
	result = []
	if frappe.db.exists("DocType", "Messenger Channel"):
		for r in frappe.get_all(
			"Messenger Channel",
			fields=[
				"name",
				"custom_display_name",
				"provider_display_name",
				"provider",
				"platform",
				"enabled",
				"state",
			],
		):
			if _account_allowed("messenger", r.name):
				result.append(
					{
						"kind": "messenger",
						"name": r.name,
						"label": r.custom_display_name or r.provider_display_name or r.name,
						"channel": r.platform,
						"enabled": bool(r.enabled),
						"state": r.state,
						"can_send": _account_allowed("messenger", r.name, send=True),
					}
				)
	for r in frappe.get_all(
		"Email Account", fields=["name", "email_id", "enable_incoming", "enable_outgoing"]
	):
		if _account_allowed("email", r.name):
			result.append(
				{
					"kind": "email",
					"name": r.name,
					"label": r.email_id,
					"channel": "email",
					"enabled": bool(r.enable_incoming or r.enable_outgoing),
					"can_send": bool(r.enable_outgoing and _account_allowed("email", r.name, send=True)),
				}
			)
	return result


def _contexts(source):
	refs = (
		{(source.reference_doctype, source.reference_name)}
		if source.reference_doctype in CONTEXTS and source.reference_name
		else set()
	)
	if (
		source.reference_doctype == "CRM Lead"
		and source.reference_name
		and frappe.has_permission("CRM Deal", "read")
	):
		refs.update(
			("CRM Deal", r.name)
			for r in frappe.get_list("CRM Deal", filters={"lead": source.reference_name}, fields=["name"])
		)
	elif source.reference_doctype == "CRM Deal" and source.reference_name:
		lead = frappe.db.get_value("CRM Deal", source.reference_name, "lead")
		if lead:
			refs.add(("CRM Lead", lead))
	return [
		{
			"doctype": dt,
			"name": name,
			"title": frappe.db.get_value(dt, name, CONTEXTS[dt][0]) or name,
			"path": f"/crm/{CONTEXTS[dt][1]}/{quote(name, safe='')}",
			"can_write": _reference_allowed(dt, name, True),
		}
		for dt, name in sorted(refs)
		if _reference_allowed(dt, name)
	]


@frappe.whitelist()
def get_thread(kind, name, before_cursor=None):
	source, rows = _load(kind, name)
	thread = _project(kind, name, rows)
	if kind == "messenger":
		from crm_messenger.api.messages import get_message_page
		from crm_messenger.services.channel_info import get_channel_info

		data = get_message_page(conversation=name, before_cursor=before_cursor, limit=50)
		info = get_channel_info(source.channel, source) if source.channel else {}
		can_send = bool(thread["can_operate"] and (thread["demo"] or (info and info.get("can_send"))))
		capabilities = (info or {}).get("capabilities") or {}
		messages = data["messages"]
		page = data["page"]
	else:
		messages = []
		for r in sorted(
			rows, key=lambda r: (str(r.communication_date or r.creation), str(r.creation), r.name)
		):
			m = frappe.get_doc("Communication", r.name)
			messages.append(
				{
					"name": m.name,
					"direction": "inbound" if m.sent_or_received == "Received" else "outbound",
					"text": _plain(m.content),
					"content": m.content,
					"subject": m.subject,
					"sender": m.sender,
					"recipients": m.recipients,
					"cc": m.cc,
					"bcc": m.bcc if m.sent_or_received == "Sent" else "",
					"message_datetime": str(m.communication_date or m.creation),
					"creation": str(m.creation),
					"status": m.delivery_status,
					"attachments": frappe.get_all(
						"File",
						filters={"attached_to_doctype": "Communication", "attached_to_name": m.name},
						fields=["name", "file_name", "file_url"],
					),
				}
			)
		page = {"has_more": False}
		can_send = bool(
			thread["can_operate"]
			and (
				thread["demo"]
				or (
					source.email_account
					and frappe.db.get_value("Email Account", source.email_account, "enable_outgoing")
				)
			)
		)
		can_send = can_send and (
			not source.reference_doctype
			or frappe.has_permission(source.reference_doctype, "email", source.reference_name)
		)
		if frappe.conf.mute_emails and not thread["demo"]:
			can_send = False
		capabilities = {"supports_attachments": True}
	contexts = _contexts(source)
	work = thread["work"]
	selected = next(
		(c for c in contexts if (c["doctype"], c["name"]) == (work["context_doctype"], work["context_name"])),
		None,
	)
	selected = selected or next(
		(
			c
			for c in contexts
			if (c["doctype"], c["name"]) == (source.reference_doctype, source.reference_name)
		),
		None,
	)
	materials = _materials(kind, name, selected)
	read = max(([str(m["creation"]), m["name"]] for m in messages if m["direction"] == "inbound"), default=[])
	return {
		"thread": thread,
		"messages": messages,
		"page": page,
		"private": _private(kind, name),
		"read_cursor": read,
		"contexts": contexts,
		"customer": _customer(selected),
		"context": selected,
		"materials": materials,
		"can_send": bool(can_send),
		"capabilities": capabilities,
		"disabled_reason": "" if can_send else "Нет права отправки или канал не подключён.",
		"people": _people(kind, source),
		"can_note": bool(
			thread["can_operate"]
			and selected
			and selected["can_write"]
			and frappe.has_permission("FCRM Note", "create")
		),
		"can_task": bool(
			thread["can_operate"]
			and selected
			and selected["can_write"]
			and frappe.has_permission("CRM Task", "create")
		),
		"viewer": frappe.session.user,
	}


def _people(kind, source):
	return [
		{"value": r.name, "label": r.full_name or r.name}
		for r in frappe.get_all(
			"User", filters={"enabled": 1, "user_type": "System User"}, fields=["name", "full_name"]
		)
		if _source_allowed(kind, source, True, user=r.name)
	]


def _customer(context):
	from frappe.model import get_permitted_fields

	profile = {"phone": "", "email": "", "organization": None, "contacts": []}
	if not context:
		return profile
	dt, name = context["doctype"], context["name"]
	doc = frappe.get_doc(dt, name)
	fields = set(get_permitted_fields(dt))
	if dt == "CRM Lead":
		profile["phone"] = next(
			(doc.get(f) for f in ["mobile_no", "phone"] if f in fields and doc.get(f)), ""
		)
		profile["email"] = doc.get("email") or "" if "email" in fields else ""
		if "organization" in fields and doc.organization:
			profile["organization"] = {"title": doc.organization, "path": None}
	elif (
		"organization" in fields
		and doc.organization
		and frappe.has_permission("CRM Organization", "read", doc.organization)
	):
		profile["organization"] = {
			"title": frappe.db.get_value("CRM Organization", doc.organization, "organization_name")
			or doc.organization,
			"path": "/crm/organizations/" + quote(doc.organization, safe=""),
		}
	if not frappe.has_permission("Contact", "read"):
		return profile
	linked = (
		[r.contact for r in doc.get("contacts", []) if r.contact]
		if dt == "CRM Deal" and doc.has_permlevel_access_to("contacts")
		else []
	)
	linked += frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": dt, "link_name": name},
		pluck="parent",
	)
	for contact_name in dict.fromkeys(linked):
		if not frappe.has_permission("Contact", "read", contact_name):
			continue
		contact = frappe.get_doc("Contact", contact_name)
		allowed = set(get_permitted_fields("Contact"))
		phone = next((contact.get(f) for f in ["mobile_no", "phone"] if f in allowed and contact.get(f)), "")
		email = contact.get("email_id") or "" if "email_id" in allowed else ""
		profile["contacts"].append(
			{
				"name": contact_name,
				"title": contact.full_name or contact_name,
				"path": "/crm/contacts/" + quote(contact_name, safe=""),
				"phone": phone,
				"email": email,
			}
		)
		profile["phone"] = profile["phone"] or phone
		profile["email"] = profile["email"] or email
	return profile


def _materials(kind, name, context):
	result = {"notes": [], "tasks": [], "calls": []}
	if not context:
		return result
	from crm.api import celio_tasks, telephony

	dt, ref = context["doctype"], context["name"]
	for r in (
		frappe.get_list(
			"FCRM Note",
			filters={"reference_doctype": dt, "reference_docname": ref},
			fields=["name", "title", "content", "creation"],
			order_by="creation desc",
			limit_page_length=20,
		)
		if frappe.has_permission("FCRM Note", "read")
		else []
	):
		result["notes"].append(
			{"name": r.name, "title": r.title, "text": _plain(r.content), "creation": str(r.creation)}
		)
	if frappe.has_permission("CRM Task", "read"):
		for r in frappe.get_list(
			"CRM Task",
			filters={"reference_doctype": dt, "reference_docname": ref},
			fields=["name"],
			order_by="modified desc",
			limit_page_length=20,
		):
			doc = frappe.get_doc("CRM Task", r.name)
			if celio_tasks.readable(doc):
				result["tasks"].append(celio_tasks.project(doc))
	if frappe.has_permission("CRM Call Log", "read"):
		t = frappe.qb.DocType("CRM Call Log")
		result["calls"] = (
			telephony._base_query(["name", "type", "status", "duration", "creation"])
			.where((t.reference_doctype == dt) & (t.reference_docname == ref))
			.orderby(t.creation, order=Order.desc)
			.limit(10)
			.run(as_dict=True)
		)
	return result


@frappe.whitelist(methods=["POST"])
def save_private(kind, name, expected_revision, draft=None, read_cursor=None, expected_viewer=None):
	_expect_viewer(expected_viewer)
	_lock_user()
	_, rows = _load(kind, name)
	current = _private(kind, name)
	if cint(expected_revision) != current["revision"]:
		frappe.throw(
			"Черновик изменился в другом окне. Ваш текст сохранён в этом браузере.",
			frappe.TimestampMismatchError,
		)
	values = {
		"source_kind": kind,
		"source_name": name,
		"user": frappe.session.user,
		"revision": current["revision"] + 1,
	}
	if draft is not None:
		draft = _json(draft)
		if (
			not isinstance(draft, dict)
			or set(draft) - {"text", "subject", "to", "cc", "bcc", "attachments", "mode"}
			or len(frappe.as_json(draft)) > 120000
		):
			frappe.throw("Некорректный черновик.")
		values["data"] = frappe.as_json(draft)
	if read_cursor is not None:
		cursor = _json(read_cursor, [])
		if cursor not in [_cursor(m) for m in _messages(kind, rows) if m.direction == "inbound"] + (
			[] if cursor else [[]]
		):
			frappe.throw("Обновите переписку перед отметкой прочтения.")
		values["read_cursor"] = frappe.as_json(max(current["read_cursor"], cursor))
	_save(STATE, _key(kind, name, frappe.session.user), values)
	return _private(kind, name)


@frappe.whitelist(methods=["POST"])
def update_work(
	kind,
	name,
	expected_revision,
	status=None,
	assigned_to=None,
	snoozed_until=None,
	context_doctype=None,
	context_name=None,
	expected_viewer=None,
):
	_expect_viewer(expected_viewer)
	_lock_user()
	source, rows = _load(kind, name, write=True, lock=True)
	current = _work(kind, name)
	if cint(expected_revision) != current["revision"]:
		frappe.throw("Диалог изменился у другого сотрудника. Обновите его.", frappe.TimestampMismatchError)
	values = {**current, "revision": current["revision"] + 1, "source_kind": kind, "source_name": name}
	if status is not None:
		if status not in STATUSES:
			frappe.throw("Неверный статус.")
		values["status"] = status
		values["watermark"] = _project(kind, name, rows)["watermark"]
		if status == "snoozed":
			if not snoozed_until or get_datetime(snoozed_until) <= now_datetime():
				frappe.throw("Выберите время в будущем.")
			values["snoozed_until"] = snoozed_until
		else:
			values["snoozed_until"] = None
	if assigned_to is not None:
		if assigned_to and (
			not frappe.db.get_value("User", assigned_to, "enabled")
			or not _source_allowed(kind, source, True, user=assigned_to)
		):
			frappe.throw("У сотрудника нет доступа к этому диалогу.", frappe.PermissionError)
		values["assigned_to"] = assigned_to or None
	if context_doctype is not None or context_name is not None:
		if not any(
			(c["doctype"], c["name"]) == (context_doctype, context_name) and c["can_write"]
			for c in _contexts(source)
		):
			frappe.throw("Выберите доступную связанную карточку.", frappe.PermissionError)
		values.update(context_doctype=context_doctype, context_name=context_name)
	_save(WORK, _key(kind, name), values)
	return _work(kind, name)


def _operation(kind, name, mutation_id, payload, action):
	if not isinstance(mutation_id, str) or not 16 <= len(mutation_id) <= 100:
		frappe.throw("Неверный идентификатор действия.")
	_lock_user()
	key = _key(frappe.session.user, mutation_id)
	fingerprint = _key(kind, name, frappe.as_json(payload))
	previous = _row(OP, key)
	if previous:
		if previous.request_hash != fingerprint:
			frappe.throw("Этот запрос уже использован для другого действия.")
		return _json(previous.result)
	result = action()
	_save(
		OP,
		key,
		{
			"user": frappe.session.user,
			"source_kind": kind,
			"source_name": name,
			"request_hash": fingerprint,
			"result": frappe.as_json(result),
		},
	)
	return result


@frappe.whitelist(methods=["POST"])
def add_note(kind, name, text, mutation_id, context_doctype, context_name, expected_viewer=None):
	_expect_viewer(expected_viewer)

	def action():
		source, _ = _load(kind, name, write=True, lock=True)
		if not any(
			(c["doctype"], c["name"]) == (context_doctype, context_name) and c["can_write"]
			for c in _contexts(source)
		):
			frappe.throw("Выберите доступную связанную карточку.", frappe.PermissionError)
		if not isinstance(text, str) or not text.strip() or len(text) > 100000:
			frappe.throw("Введите текст заметки.")
		doc = frappe.get_doc(
			{
				"doctype": "FCRM Note",
				"title": "Переписка · " + str(now_datetime())[:16],
				"content": "<p>" + escape_html(text.strip()).replace("\n", "<br>") + "</p>",
				"reference_doctype": context_doctype,
				"reference_docname": context_name,
			}
		)
		doc.insert()
		return {"name": doc.name, "doctype": doc.doctype, "context_name": context_name}

	source, _ = _load(kind, name, write=True)
	if not any(
		(c["doctype"], c["name"]) == (context_doctype, context_name) and c["can_write"]
		for c in _contexts(source)
	):
		frappe.throw("Выберите доступную связанную карточку.", frappe.PermissionError)
	return _operation(
		kind,
		name,
		mutation_id,
		{"action": "note", "text": text, "dt": context_doctype, "ref": context_name},
		action,
	)


@frappe.whitelist(methods=["POST"])
def add_task(kind, name, values, mutation_id, expected_viewer=None):
	from crm.api import celio_tasks

	_expect_viewer(expected_viewer)
	_lock_user()
	source, _ = _load(kind, name, write=True, lock=True)
	values = _json(values)
	dt = celio_tasks.CONTEXTS.get(values.get("context_kind"), ("", ""))[0]
	if not any(
		(c["doctype"], c["name"]) == (dt, values.get("context_name")) and c["can_write"]
		for c in _contexts(source)
	):
		frappe.throw("Выберите доступную связанную карточку.", frappe.PermissionError)
	return celio_tasks.save_task(values, mutation_id, expected_viewer=frappe.session.user)


def _addresses(value):
	if not isinstance(value, str) or "\r" in value or "\n" in value:
		frappe.throw("Некорректные адреса.")
	addresses = [addr for _, addr in getaddresses([value]) if addr]
	if value.strip() and not addresses:
		frappe.throw("Проверьте адреса получателей.")
	if len(addresses) > 30 or any(not frappe.utils.validate_email_address(a) for a in addresses):
		frappe.throw("Проверьте адреса получателей.")
	return ", ".join(addresses)


@frappe.whitelist(methods=["POST"])
def send_reply(
	kind, name, text, mutation_id, subject="", to="", cc="", bcc="", attachments=None, expected_viewer=None
):
	_expect_viewer(expected_viewer)
	source, rows = _load(kind, name, write=True, lock=True)
	attachments = _json(attachments, [])
	if (
		not isinstance(text, str)
		or not text.strip()
		or len(text) > 100000
		or not isinstance(attachments, list)
		or len(attachments) > 10
	):
		frappe.throw("Введите сообщение допустимой длины.")
	if kind == "messenger" and not _is_demo(kind, source):
		from crm_messenger.api.messages import send_message

		result = send_message(
			conversation=name,
			text=text,
			channel=source.channel,
			client_request_id="crm-inbox-" + _key(frappe.session.user, mutation_id),
			attachments=attachments,
			reference_doctype=source.reference_doctype,
			reference_name=source.reference_name,
		)
		if not result.get("ok"):
			frappe.throw(result.get("message") or "Не удалось отправить сообщение.")
		return result

	def action():
		if _is_demo(kind, source):
			if not frappe.conf.get("crm_inbox_demo_enabled"):
				frappe.throw("Локальные примеры отключены.")
			if attachments:
				frappe.throw(
					"В локальном примере вложения можно просматривать; для отправки подключите канал."
				)
			if kind == "messenger":
				from crm_messenger.services.crm_linker import advance_conversation_last_message

				doc = frappe.get_doc(
					{
						"doctype": "Messenger Message",
						"conversation": name,
						"provider": source.provider,
						"platform": source.chat_type,
						"channel": source.channel,
						"provider_message_key": _key("local", mutation_id, frappe.session.user),
						"direction": "outbound",
						"message_type": "text",
						"text": text,
						"status": "queued",
						"provider_status": "local_preview",
						"message_datetime": now_datetime(),
						"crm_user": frappe.session.user,
					}
				)
				doc.insert(ignore_permissions=True)
				advance_conversation_last_message(source, doc.message_datetime)
				return {"ok": True, "name": doc.name, "local_only": True}
			result = _make_email(source, rows, text, subject, to, cc, bcc, [], send=False)
			frappe.db.set_value(
				"Communication",
				result["name"],
				"message_id",
				f"<{mutation_id}@inbox.local.invalid>",
				update_modified=False,
			)
			return {**result, "local_only": True}
		if not get_thread(kind, name)["can_send"]:
			frappe.throw("Почтовый аккаунт не готов к отправке.", frappe.PermissionError)
		return _make_email(source, rows, text, subject, to, cc, bcc, attachments, send=True)

	return _operation(
		kind,
		name,
		mutation_id,
		{
			"action": "reply",
			"text": text,
			"subject": subject,
			"to": to,
			"cc": cc,
			"bcc": bcc,
			"attachments": attachments,
		},
		action,
	)


def _make_email(source, rows, text, subject, to, cc, bcc, attachments, send):
	from frappe.core.doctype.communication.email import make

	if not isinstance(subject, str) or len(subject) > 240 or "\r" in subject or "\n" in subject:
		frappe.throw("Проверьте тему письма.")

	latest = max(rows, key=lambda r: (str(r.communication_date or r.creation), str(r.creation), r.name))
	if not to.strip():
		to = latest.sender if latest.sent_or_received == "Received" else latest.recipients
	to, cc, bcc = (_addresses(x) for x in (to, cc, bcc))
	if not to:
		frappe.throw("Укажите получателя.")
	for file in attachments:
		doc = frappe.get_doc("File", file)
		if (
			doc.owner != frappe.session.user
			or (doc.attached_to_doctype, doc.attached_to_name)
			!= (STATE, _key("email", source.name, frappe.session.user))
			or not doc.is_private
		):
			frappe.throw("Вложение не принадлежит этому черновику.", frappe.PermissionError)
	sender = (
		frappe.db.get_value("Email Account", source.email_account, "email_id")
		if source.email_account
		else frappe.session.user
	)
	result = make(
		doctype=source.reference_doctype or None,
		name=source.reference_name or None,
		content="<p>" + escape_html(text).replace("\n", "<br>") + "</p>",
		subject=subject or "Re: " + (source.subject or ""),
		sender=sender,
		recipients=to,
		cc=cc,
		bcc=bcc,
		attachments=attachments,
		send_email=False,
		now=False,
		in_reply_to=latest.name,
	)
	# Bind the exact account before queue creation; native sender-address matching
	# must not fall back to another account with the same email address.
	communication = frappe.get_doc("Communication", result["name"])
	if source.email_account:
		communication.db_set("email_account", source.email_account, update_modified=False)
	if send:
		communication.send_email(now=False)
	return result


@frappe.whitelist(methods=["POST"])
def link_customer(kind, name, reference_doctype, reference_name, expected_viewer=None):
	_expect_viewer(expected_viewer)
	source, _ = _load(kind, name, write=True, lock=True)
	if not _reference_allowed(reference_doctype, reference_name, True):
		frappe.throw("Нет доступа к выбранной карточке.", frappe.PermissionError)
	# Reassignment changes who can read history; require account administration.
	if not _admin():
		frappe.throw("Привязку переписки меняет администратор.", frappe.PermissionError)
	if kind == "email":
		frappe.throw("Для почты связь задаётся в исходном письме. Выберите контекст для заметок и задач.")
	source.reference_doctype, source.reference_name = reference_doctype, reference_name
	source.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def search_customers(query="", doctype="CRM Lead"):
	_require()
	if doctype not in CONTEXTS or not frappe.has_permission(doctype, "read"):
		return []
	field, route = CONTEXTS[doctype]
	pattern = "%" + str(query or "")[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
	return [
		{
			"doctype": doctype,
			"name": r.name,
			"title": r.get(field),
			"path": f"/crm/{route}/{quote(r.name, safe='')}",
		}
		for r in frappe.get_list(
			doctype, filters={field: ["like", pattern]}, fields=["name", field], limit_page_length=20
		)
	]


@frappe.whitelist(methods=["POST"])
def set_account_access(kind, account, user, can_read=0, can_send=0, expected_viewer=None):
	_expect_viewer(expected_viewer)
	if (
		not _admin()
		or kind not in KINDS
		or not frappe.db.exists("Messenger Channel" if kind == "messenger" else "Email Account", account)
	):
		frappe.throw("Настройки доступа недоступны.", frappe.PermissionError)
	if not frappe.db.get_value("User", user, "enabled"):
		frappe.throw("Пользователь недоступен.")
	_save(
		ACCESS,
		_key(kind, account, user),
		{
			"source_kind": kind,
			"account": account,
			"user": user,
			"can_read": bool(cint(can_read)),
			"can_send": bool(cint(can_read) and cint(can_send)),
		},
	)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def upload_attachment(kind=None, docname=None, expected_viewer=None):
	_expect_viewer(expected_viewer)
	kind = kind or frappe.form_dict.get("kind") or frappe.form_dict.get("type")
	docname = docname or frappe.form_dict.get("docname")
	source, _ = _load(kind, docname, write=True)
	if _is_demo(kind, source) or not get_thread(kind, docname)["can_send"]:
		frappe.throw("Для вложений подключите канал.", frappe.PermissionError)
	if kind == "messenger":
		upload = (frappe.request.files or {}).get("file")
		if not upload or len(upload.stream.read(20 * 1024 * 1024 + 1)) > 20 * 1024 * 1024:
			frappe.throw("Выберите файл до 20 МБ.")
		upload.stream.seek(0)
		from crm_messenger.api.attachments import upload_temporary_file

		return upload_temporary_file(docname)
	from frappe.utils.file_manager import save_file

	upload = (frappe.request.files or {}).get("file")
	if not upload:
		frappe.throw("Выберите файл.")
	content = upload.stream.read(20 * 1024 * 1024 + 1)
	if not content or len(content) > 20 * 1024 * 1024:
		frappe.throw("Размер файла должен быть от 1 байта до 20 МБ.")
	state_key = _key("email", source.name, frappe.session.user)
	if not frappe.db.exists(STATE, state_key):
		_save(
			STATE,
			state_key,
			{"user": frappe.session.user, "source_kind": "email", "source_name": source.name, "revision": 0},
		)
	return save_file(
		str(upload.filename or "attachment").replace("\\", "/").split("/")[-1],
		content,
		STATE,
		state_key,
		is_private=1,
	)


@frappe.whitelist(methods=["GET"])
def email_attachment(file):
	_require()
	doc = frappe.get_doc("File", file)
	if doc.attached_to_doctype != "Communication" or not doc.attached_to_name:
		frappe.throw("Вложение недоступно.", frappe.PermissionError)
	mail = frappe.get_doc("Communication", doc.attached_to_name)
	if mail.communication_medium != "Email" or not _source_allowed("email", mail):
		frappe.throw("Вложение недоступно.", frappe.PermissionError)
	frappe.local.response.filename = doc.file_name
	frappe.local.response.filecontent = doc.get_content()
	frappe.local.response.type = "download"
