import frappe
from frappe import _

no_cache = 1


def get_context(context):
	frappe.only_for(("Customer", "System Manager"))
	context.no_cache = 1
	context.show_sidebar = True
	context.title = _("Inquéritos")
	context.parents = [{"name": _("Home"), "route": "/portal"}]
	from logicposintegration.logicpos_integration.satisfaction_survey import (
		list_portal_surveys,
	)

	context.surveys = list_portal_surveys()
	context.metatags = {
		"title": _("Inquéritos"),
		"description": _("Inquéritos de satisfação"),
	}
	return context
