import frappe
from frappe import _
from frappe.utils.user import is_website_user

PROJECT_STATUS_COLORS = {
	"Open": "orange",
	"Completed": "green",
	"Cancelled": "grey",
	"On Hold": "yellow",
}

ISSUE_STATUS_COLORS = {
	"Open": "red",
	"Closed": "green",
	"Replied": "blue",
}

_patched = False


def ensure_list_context_patch():
	global _patched
	if _patched:
		return

	import frappe.www.list as list_module
	import frappe.www.portal as portal_module

	original = list_module.get_list_context

	def wrapped(context, doctype, web_form_name=None):
		list_context = original(context, doctype, web_form_name) or frappe._dict()
		apply_portal_list_templates(list_context, doctype)
		return list_context

	# Patch module and stale imports (portal.py binds get_list_context at import time).
	list_module.get_list_context = wrapped
	portal_module.get_list_context = wrapped
	_patched = True


def apply_portal_list_templates(list_context, doctype):
	if frappe.session.user == "Guest" or not is_website_user():
		return

	list_context.list_template = "templates/includes/portal/portal_list.html"
	list_context.portal_status_colors = PROJECT_STATUS_COLORS
	list_context.portal_issue_status_colors = ISSUE_STATUS_COLORS

	if doctype == "Project":
		list_context.row_template = "templates/includes/portal/portal_project_row.html"
		list_context.list_template = "templates/includes/portal/portal_project_list.html"
		list_context.portal_list_layout = "project"
		return

	if doctype == "Issue":
		list_context.row_template = "templates/includes/portal/portal_issue_row.html"
		list_context.portal_list_columns = [_("Issue"), _("Status"), _("Updated")]
		return

	list_context.row_template = "templates/includes/portal/portal_transaction_row.html"
	list_context.portal_list_columns = [_("Document"), _("Status"), _("Amount")]


ensure_list_context_patch()
