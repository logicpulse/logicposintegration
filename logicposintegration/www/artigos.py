import frappe
from frappe import _

no_cache = 1


def get_context(context):
	frappe.only_for(("Customer", "System Manager"))
	context.no_cache = 1
	context.show_sidebar = True
	context.title = _("Artigos")
	context.parents = [{"name": _("Home"), "route": "/portal"}]
	context.metatags = {
		"title": _("Artigos"),
		"description": _("Catálogo de artigos com preços da lista de venda"),
	}
	return context
