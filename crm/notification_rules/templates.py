"""Manager-authored suggestions; recipients explicitly copy them into personal policy."""

from copy import deepcopy

import frappe
from exp_theme.notifications import policy
from exp_theme.notifications.access import identity

from crm.notification_rules import api, mutation, schema
from crm.notification_rules.access import visible_configuration

SOURCE = "crm_templates"
ROLES = {"Sales User", "Sales Manager"}


def manager(user):
	return bool({"System Manager", "Sales Manager"} & set(frappe.get_roles(user)))


def _require_manager(user):
	if not manager(user):
		frappe.throw(frappe._("Only a CRM manager can publish team templates."), frappe.PermissionError)


def _templates(user):
	row = policy.load(user, SOURCE)
	return row, policy.configuration(row).get("templates", [])


def _offered(template, user):
	return bool(
		template["enabled"]
		and (user in template["recipients"] or set(template["roles"]) & set(frappe.get_roles(user)))
	)


@frappe.whitelist(methods=["GET"])
def catalog(expected_viewer: str):
	user = api.viewer(expected_viewer)
	row, own = _templates(user)
	items = []
	for author in frappe.get_all(
		policy.DOCTYPE, filters={"source": SOURCE}, fields=["user", "configuration", "revision"], limit=200
	):
		if not frappe.db.get_value("User", author.user, "enabled") or not manager(author.user):
			continue
		for template in policy.configuration(author).get("templates", []):
			if _offered(template, user):
				visible = visible_configuration({"rules": template["rules"]}, user)
				items.append(
					{
						"author": author.user,
						"id": template["id"],
						"name": template["name"],
						"revision": author.revision,
						"rules": visible["rules"],
						"unavailable_selection_count": sum(
							r["unavailable_selection_count"] for r in visible["rules"]
						),
					}
				)
	return {
		"viewer": user,
		"can_manage": manager(user),
		"revision": row.revision,
		"owned": own if manager(user) else [],
		"offered": items,
		"roles": sorted(ROLES),
	}


def _validate(values, user):
	if not isinstance(values, dict) or set(values) != {
		"id",
		"name",
		"enabled",
		"roles",
		"recipients",
		"rules",
	}:
		schema.invalid()
	schema.rule_id(values["id"])
	if (
		not isinstance(values["name"], str)
		or not 1 <= len(values["name"].strip()) <= 100
		or type(values["enabled"]) is not bool
	):
		schema.invalid()
	roles, recipients = schema.names(values["roles"]), schema.names(values["recipients"])
	if set(roles) - ROLES or not (roles or recipients):
		schema.invalid()
	for recipient in recipients:
		if not frappe.db.get_value("User", recipient, "enabled"):
			schema.invalid()
		from crm.notification_rules.access import require_crm

		require_crm(recipient)
	if not isinstance(values["rules"], list) or not 1 <= len(values["rules"]) <= 20:
		schema.invalid()
	rules = [schema.validate(rule, user) for rule in values["rules"]]
	if len({r["id"] for r in rules}) != len(rules):
		schema.invalid()
	return {
		**values,
		"name": values["name"].strip(),
		"roles": roles,
		"recipients": recipients,
		"rules": rules,
	}


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def save_template(values: dict, expected_revision: int, mutation_id: str, expected_viewer: str):
	user = api.viewer(expected_viewer)
	_require_manager(user)
	template = _validate(frappe.parse_json(values), user)

	def transform(current):
		items = [t for t in current.get("templates", []) if t["id"] != template["id"]] + [template]
		if len(items) > 30:
			schema.invalid()
		return {"templates": items}

	_, replayed, applied = policy.update(
		user, SOURCE, {"save_template": template}, expected_revision, mutation_id, transform
	)
	return {**catalog(user), "replayed": replayed, "applied_revision": applied}


@frappe.whitelist(methods=["POST"])
@mutation.rpc
def apply_template(
	author: str,
	template_id: str,
	expected_template_revision: int,
	expected_revision: int,
	mutation_id: str,
	expected_viewer: str,
):
	user = api.viewer(expected_viewer)
	schema.rule_id(template_id)
	action = {"apply_template": [author, template_id, expected_template_revision]}
	for locked_user in sorted({user, author}):
		frappe.db.get_value("User", locked_user, "enabled", for_update=True)
	if frappe.db.exists(policy.OPERATION, identity(user, "crm", mutation_id)):
		row, replayed, applied = policy.update(
			user, "crm", action, expected_revision, mutation_id, lambda current: current
		)
		return {**api._state(user, row), "replayed": replayed, "applied_revision": applied}
	if not frappe.db.get_value("User", author, "enabled") or not manager(author):
		frappe.throw(frappe._("This team template is no longer available."), frappe.PermissionError)
	row = policy.load(author, SOURCE, lock=True)
	if row.revision != expected_template_revision:
		frappe.throw(
			frappe._("The team template changed. Review its current version."), frappe.TimestampMismatchError
		)
	template = next(
		(t for t in policy.configuration(row).get("templates", []) if t["id"] == template_id), None
	)
	if not template or not _offered(template, user):
		frappe.throw(frappe._("This team template is not offered to you."), frappe.PermissionError)
	rules = []
	for item in template["rules"]:
		item = deepcopy(item)
		item["id"] = identity("crm-template", author, template_id, item["id"])[:32]
		rules.append(schema.validate(item, user))

	def transform(current):
		result = api._configuration(current)
		ids = {r["id"] for r in rules}
		result["rules"] = [r for r in result["rules"] if r["id"] not in ids] + rules
		if len(result["rules"]) > 50:
			schema.invalid()
		result["mode"] = "rules"
		return result

	row, replayed, applied = policy.update(user, "crm", action, expected_revision, mutation_id, transform)
	return {**api._state(user, row), "replayed": replayed, "applied_revision": applied}
