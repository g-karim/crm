"""A local catalogue-based report draft. Only the explicit board save writes."""

import re

import frappe
from frappe import _

from crm.analytics.boards import _catalog, _definition
from crm.utils import sales_user_only

METRIC_PATTERNS = {
	"calls_late_callback": r"(?:просроч\w*|overdue) (?:перезвон\w*|callbacks?)",
	"calls_sla": r"\bsla\b|перезвон\w* в срок|callbacks? on time",
	"calls_missed": r"пропущ\w* (?:входящ\w*|звон\w*|вызов\w*)|missed calls?",
	"calls_answer_incoming": r"(?:дол\w*|процент\w*) дозвон\w* (?:по )?входящ\w*|inbound answer rate",
	"calls_answer_outgoing": r"(?:дол\w*|процент\w*) дозвон\w* (?:по )?исходящ\w*|outbound answer rate",
	"calls_connected": r"состоявш\w* (?:звон\w*|соединен\w*)|connected calls?",
	"calls_total": r"все звонки|числ\w* звон\w*|количеств\w* звон\w*|total calls?",
	"tasks_overdue": r"просроч\w* зада\w*|overdue tasks?",
	"tasks_open": r"открыт\w* зада\w*|open tasks?",
	"new_leads": r"нов\w* лид\w*|new leads?",
	"won_value": r"сумм\w* (?:выигранн\w* сдел\w*|побед\w*)|продаж\w* по источник\w*|won (?:amount|value)",
	"won_count": r"выигранн\w* сдел\w*|числ\w* побед\w*|won deals?",
	"lost_count": r"проигранн\w* сдел\w*|потерянн\w* сдел\w*|lost deals?",
	"open_count": r"открыт\w* сдел\w*|воронк\w* по этап\w*|open deals?",
	"forecast": r"прогноз\w*|\bforecast\b",
}
GROUP_PATTERNS = {
	"team": r"по команд\w*|\bby teams?\b",
	"employee": r"по (?:сотрудник\w*|менеджер\w*)|\bby (?:employees?|managers?)\b",
	"source": r"по источник\w*|\bby sources?\b",
	"line": r"по лини\w*|\bby lines?\b",
	"day": r"по дн\w*|\bby day\b",
	"pipeline": r"по воронк\w*|\bby pipelines?\b",
	"stage": r"по этап\w*|\bby stages?\b",
}
PERIOD = re.compile(r"(?<!\d)(7|30|90)\s*(?:дней|days?)\b")
VALID_DISPLAY = re.compile(r"график\w*|\bchart\b")


@frappe.whitelist(methods=["POST"])
@sales_user_only
def suggest(text: str):
	if len(text) > 320 or len(text.strip()) < 3:
		frappe.throw(_("Enter a short report request of 3 to 320 characters."), frappe.ValidationError)
	query = re.sub(r"\s+", " ", text.casefold().replace("ё", "е"))
	catalog = _catalog()
	spans = [(match.span(), key) for key, pattern in METRIC_PATTERNS.items() if (match := re.search(pattern, query))]
	# Longer matches take priority when a phrase means either a count or a value.
	matched = {}
	for (start, end), key in sorted(spans, key=lambda match: -(match[0][1] - match[0][0])):
		if not any(start < right and left < end for left, right in matched):
			matched[start, end] = key
	groups = [key for key, pattern in GROUP_PATTERNS.items() if re.search(pattern, query)]
	period = PERIOD.search(query)
	cards = []
	for _span, key in sorted(matched.items())[:8]:
		group = next((value for value in groups if value in catalog[key]["groups"]), "")
		cards.append({"metric": key, "group": group,
			"display": ("bar" if VALID_DISPLAY.search(query) else "table") if group else "number"})
	return {
		"mode": "catalog",
		"definition": _definition({"days": int(period[1]) if period else 30, "cards": cards}) if cards else None,
		"default_period": not bool(period),
	}
