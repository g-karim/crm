import frappe

from crm.branding import ensure_crm_branding_defaults
from crm.desk import hide_legacy_erpnext_crm
from crm.dropdown import ensure_crm_dropdown_items


def cleanup_exp_theme_crm_state():
	ensure_crm_branding_defaults()
	ensure_crm_dropdown_items()
	hide_legacy_erpnext_crm()
	frappe.clear_cache()
