import frappe


APP_NAME = "EXP CRM"
APP_ROUTE = "/crm"
APP_LOGO_URL = "/assets/crm/images/crm_logo.png"
APP_FAVICON_URL = APP_LOGO_URL

LEGACY_APP_NAMES = {"", None, "CRM", "Frappe CRM"}
LEGACY_ASSET_URLS = {
	"",
	None,
	"/assets/crm/images/logo.svg",
	"/assets/crm/images/logo.png",
	"/assets/crm/manifest/manifest-icon-192.maskable.png",
	"/assets/crm/manifest/manifest-icon-512.maskable.png",
	"/assets/exp_theme/img/exp-favicon.png",
}


def ensure_crm_branding_defaults():
	ensure_fcrm_settings_branding()
	ensure_desktop_icon_branding()


def ensure_fcrm_settings_branding():
	if not frappe.db.exists("DocType", "FCRM Settings"):
		return

	settings = frappe.get_single("FCRM Settings")
	changed = False

	if settings.brand_name in LEGACY_APP_NAMES:
		settings.brand_name = APP_NAME
		changed = True

	if settings.brand_logo in LEGACY_ASSET_URLS:
		settings.brand_logo = APP_LOGO_URL
		changed = True

	if settings.favicon in LEGACY_ASSET_URLS:
		settings.favicon = APP_FAVICON_URL
		changed = True

	if changed:
		settings.save(ignore_permissions=True)


def ensure_desktop_icon_branding():
	if not frappe.db.table_exists("Desktop Icon"):
		return

	icon_names = set(frappe.get_all("Desktop Icon", filters={"app": "crm"}, pluck="name"))
	for name in ("Frappe CRM", APP_NAME):
		if frappe.db.exists("Desktop Icon", name):
			icon_names.add(name)

	if not icon_names:
		frappe.get_doc(
			{
				"doctype": "Desktop Icon",
				"label": APP_NAME,
				"icon_type": "App",
				"app": "crm",
				"logo_url": APP_LOGO_URL,
				"hidden": 0,
				"standard": 1,
			}
		).insert(ignore_permissions=True)
		return

	has_exp_label = bool(frappe.db.exists("Desktop Icon", {"label": APP_NAME}))
	for name in icon_names:
		doc = frappe.get_doc("Desktop Icon", name)
		values = {}

		if doc.label in LEGACY_APP_NAMES and (doc.label == APP_NAME or not has_exp_label):
			values["label"] = APP_NAME
			has_exp_label = True

		if doc.logo_url in LEGACY_ASSET_URLS:
			values["logo_url"] = APP_LOGO_URL

		if doc.icon_type != "App":
			values["icon_type"] = "App"

		if doc.app != "crm":
			values["app"] = "crm"

		if doc.hidden:
			values["hidden"] = 0

		if values:
			frappe.db.set_value("Desktop Icon", name, values, update_modified=False)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
