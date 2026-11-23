"""Native monthly sales plans, with optimistic versions and CRM role scope."""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import re

import frappe

from crm.analytics.engine import number
from crm.analytics.service import coherent_read, exact_json
from crm.api.session import CRM_ALLOWED_ROLES
from crm.permissions import org_hierarchy

DOCTYPE = "CRM Manager Sales Plan"
_FIELDS = ["manager", "month_start", "currency", "target_amount", "target_wins", "modified"]


def month_bounds(month: str) -> tuple[date, date]:
	if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
		frappe.throw(frappe._("Choose a valid month."), frappe.ValidationError)
	year, month_number = (int(value) for value in month.split("-"))
	if not 1900 <= year <= 2199:
		frappe.throw(frappe._("Choose a year from 1900 to 2199."), frappe.ValidationError)
	return date(year, month_number, 1), date(year, month_number, monthrange(year, month_number)[1])


def plan_name(manager: str, month_start: date) -> str:
	return "crm-plan-" + hashlib.sha256(f"{manager}\n{month_start}".encode()).hexdigest()[:40]


def currency_and_precision():
	currency = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
	precision = int(frappe.db.get_single_value("System Settings", "currency_precision") or 2)
	return currency, precision


def validate_targets(target_amount, target_wins, *, precision):
	amount = None
	wins = None
	if target_amount not in (None, ""):
		amount = number(target_amount)
		try:
			valid_amount = (
				amount is not None and 0 < amount <= Decimal("999999999")
				and amount == amount.quantize(Decimal(1).scaleb(-precision))
			)
		except InvalidOperation:
			valid_amount = False
		if not valid_amount:
			frappe.throw(frappe._("Enter a positive amount within the currency precision."), frappe.ValidationError)
	if target_wins not in (None, ""):
		wins_decimal = number(target_wins)
		if wins_decimal is None or not 1 <= wins_decimal <= 1_000_000 or wins_decimal != wins_decimal.to_integral():
			frappe.throw(frappe._("Enter a whole number of won deals from 1 to 1,000,000."), frappe.ValidationError)
		wins = int(wins_decimal)
	if amount is None and wins is None:
		frappe.throw(frappe._("Enter a target for at least one KPI."), frappe.ValidationError)
	return amount, wins


def plan_scope():
	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	if company_plan_editor():
		return True, None
	if "Sales Manager" in roles:
		if org_hierarchy.hierarchy_enabled() and org_hierarchy._in_hierarchy(user):
			return True, {row[0] for row in org_hierarchy._team_mem_query(user).run()}
		return True, None
	if "Sales User" in roles:
		return False, {user}
	return False, set()


def company_plan_editor():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def team_members(lead):
	if not lead or not org_hierarchy.hierarchy_enabled() or not frappe.db.exists("CRM Sales Hierarchy", {"user": lead, "is_group": 1}):
		return set()
	return {row[0] for row in org_hierarchy._team_mem_query(lead).run()}


def can_manage_team(lead):
	can_edit, owners = plan_scope()
	if not can_edit or not team_members(lead) or (owners is not None and lead not in owners):
		return False
	return company_plan_editor() or lead == frappe.session.user or lead in team_members(frappe.session.user)


def _editor_scope():
	can_edit, owners = plan_scope()
	if not can_edit:
		frappe.throw(frappe._("You cannot edit manager sales plans."), frappe.PermissionError)
	return owners


def _assignees(owners, manager=None):
	role_users = set(frappe.get_all("Has Role", filters={
		"parenttype": "User", "role": ["in", CRM_ALLOWED_ROLES],
	}, pluck="parent", distinct=True))
	role_users.add("Administrator")
	role_users.discard("Guest")
	if owners is not None:
		role_users &= owners
	if manager is not None:
		role_users &= {manager}
	if not role_users:
		return []
	return frappe.get_all("User", filters={"name": ["in", sorted(role_users)], "enabled": 1, "user_type": "System User"},
		fields=["name as key", "full_name as label"], order_by="full_name, name")


def _public_plan(row):
	version = frappe.utils.get_datetime(row.modified).isoformat(timespec="microseconds")
	amount = number(row.target_amount)
	return {"manager": row.manager, "currency": row.currency,
		"target_amount": format(amount.normalize(), "f") if amount else None,
		"target_wins": row.target_wins or None, "version": version}


def monthly_plans(month_start, owners):
	"""Plan readers get only their authorized owner scope."""
	if not frappe.db.table_exists(DOCTYPE) or owners == set():
		return {}
	filters = {"month_start": month_start}
	if owners is not None:
		filters["manager"] = ["in", sorted(owners)]
	rows = frappe.get_all(DOCTYPE, filters=filters, fields=_FIELDS)
	return {row.manager: _public_plan(row) for row in rows}


@frappe.whitelist(methods=["GET"])
@coherent_read
def get_plan_settings(month: str):
	owners = _editor_scope()
	first, _ = month_bounds(month)
	currency, precision = currency_and_precision()
	assignees = _assignees(owners)
	return exact_json({
		"month": month, "currency": currency, "precision": precision, "assignees": assignees,
		"plans": monthly_plans(first, {row.key for row in assignees}),
	})


@frappe.whitelist(methods=["POST"])
def save_plan(manager: str, month: str, target_amount: str | None = None,
		target_wins: str | None = None, version: str | None = None, currency: str | None = None):
	owners = _editor_scope()
	if not _assignees(owners, manager):
		frappe.throw(frappe._("That manager is outside your sales plan scope."), frappe.PermissionError)
	first, _ = month_bounds(month)
	current_currency, precision = currency_and_precision()
	if currency != current_currency:
		frappe.throw(frappe._("The reporting currency changed. Reload the plan before saving."), frappe.TimestampMismatchError)
	amount, wins = validate_targets(target_amount, target_wins, precision=precision)
	name = plan_name(manager, first)
	try:
		current = frappe.db.get_value(DOCTYPE, name, _FIELDS, as_dict=True, for_update=True)
		if current:
			latest = _public_plan(current)
			if (number(latest["target_amount"]), latest["target_wins"], latest["currency"]) == (amount, wins, currency):
				return exact_json(latest)  # A repeated save does not create an extra Version.
			if latest["version"] != version:
				frappe.throw(frappe._("This plan has changed. Reload it before saving."), frappe.TimestampMismatchError)
			doc = frappe.get_doc(DOCTYPE, name, for_update=True)
			doc.update({"currency": currency, "target_amount": amount or 0, "target_wins": wins or 0})
			doc.save(ignore_permissions=True)
		else:
			if version:
				frappe.throw(frappe._("This plan has changed. Reload it before saving."), frappe.TimestampMismatchError)
			doc = frappe.get_doc({"doctype": DOCTYPE, "manager": manager, "month_start": first,
				"currency": currency, "target_amount": amount or 0, "target_wins": wins or 0})
			doc.insert(set_name=name, ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.QueryDeadlockError):
		frappe.throw(frappe._("This plan has changed. Reload it before saving."), frappe.TimestampMismatchError)
	return exact_json(_public_plan(doc))
