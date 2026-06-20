import frappe


LEGACY_ERP_CRM_LABEL = "CRM"


def hide_legacy_erpnext_crm():
	hide_legacy_erpnext_crm_desktop_icons()
	hide_legacy_erpnext_crm_workspaces()
	clear_desk_cache()


def hide_legacy_erpnext_crm_desktop_icons():
	if not frappe.db.table_exists("Desktop Icon"):
		return

	for icon in frappe.get_all(
		"Desktop Icon",
		fields=["name", "label", "app", "link_to", "hidden"],
		filters={
			"label": LEGACY_ERP_CRM_LABEL,
		},
	):
		if is_legacy_erpnext_crm_icon(icon):
			frappe.db.set_value("Desktop Icon", icon.name, "hidden", 1, update_modified=False)

	for icon in frappe.get_all(
		"Desktop Icon",
		fields=["name", "label", "app", "link_to", "hidden"],
		filters={
			"link_to": LEGACY_ERP_CRM_LABEL,
		},
	):
		if is_legacy_erpnext_crm_icon(icon):
			frappe.db.set_value("Desktop Icon", icon.name, "hidden", 1, update_modified=False)


def is_legacy_erpnext_crm_icon(icon) -> bool:
	if icon.app == "crm":
		return False
	if icon.app == "erpnext":
		return True
	return icon.link_to == LEGACY_ERP_CRM_LABEL and icon.label == LEGACY_ERP_CRM_LABEL


def hide_legacy_erpnext_crm_workspaces():
	if not frappe.db.table_exists("Workspace"):
		return

	workspace_names = set()
	for filters in (
		{"name": LEGACY_ERP_CRM_LABEL},
		{"label": LEGACY_ERP_CRM_LABEL},
		{"module": LEGACY_ERP_CRM_LABEL},
	):
		workspace_names.update(frappe.get_all("Workspace", filters=filters, pluck="name"))

	for name in workspace_names:
		workspace = frappe.db.get_value(
			"Workspace",
			name,
			["name", "label", "module", "app", "is_hidden"],
			as_dict=True,
		)
		if workspace and is_legacy_erpnext_crm_workspace(workspace):
			frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)


def is_legacy_erpnext_crm_workspace(workspace) -> bool:
	if workspace.app == "crm":
		return False
	if workspace.app == "erpnext":
		return True
	return workspace.name == LEGACY_ERP_CRM_LABEL and workspace.module == LEGACY_ERP_CRM_LABEL


def clear_desk_cache():
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
