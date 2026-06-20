import frappe


DESKTOP_HOME_ROUTE = "/home"

STANDARD_DROPDOWN_ITEMS = [
	{
		"name1": "desktop_home",
		"label": "Рабочий стол",
		"type": "Route",
		"icon": "home",
		"route": DESKTOP_HOME_ROUTE,
		"is_standard": 1,
	},
	{
		"name1": "settings",
		"label": "Settings",
		"type": "Route",
		"icon": "settings",
		"route": "#",
		"is_standard": 1,
	},
	{
		"name1": "separator",
		"label": "",
		"type": "Separator",
		"is_standard": 1,
	},
	{
		"name1": "logout",
		"label": "Log out",
		"type": "Route",
		"icon": "log-out",
		"route": "#",
		"is_standard": 1,
	},
]


def ensure_crm_dropdown_items():
	if not frappe.db.exists("DocType", "FCRM Settings"):
		return

	settings = frappe.get_single("FCRM Settings")
	custom_fields = {
		"name1",
		"label",
		"type",
		"route",
		"open_in_new_window",
		"hidden",
		"is_standard",
		"icon",
	}
	custom_items = [
		{field: item.get(field) for field in custom_fields}
		for item in settings.dropdown_items
		if not item.is_standard
	]

	settings.set("dropdown_items", [])
	for item in STANDARD_DROPDOWN_ITEMS:
		settings.append("dropdown_items", item)

	for item in custom_items:
		settings.append("dropdown_items", item)

	settings.save(ignore_permissions=True)
