import frappe
from frappe import _
from frappe.www import portal as frappe_portal

from logicposintegration.utils.portal_list import ensure_list_context_patch

ensure_list_context_patch()

no_cache = 1

FEATURE_CARD_META = {
	"/orders": {
		"icon": "fa-solid fa-bag-shopping",
		"icon_color": "#2563eb",
		"description": "Acompanhe encomendas e o estado das entregas em tempo real.",
	},
	"/invoices": {
		"icon": "fa-solid fa-file-lines",
		"icon_color": "#dc2626",
		"description": "Consulte faturas, pagamentos e histórico de faturação.",
	},
	"/quotations": {
		"icon": "fa-regular fa-file",
		"icon_color": "#7c3aed",
		"description": "Revise propostas comerciais e cotações pendentes.",
	},
	"/project": {
		"icon": "fa-regular fa-folder-open",
		"icon_color": "#0284c7",
		"description": "Acompanhe o progresso dos seus projetos e tarefas.",
	},
	"/projects": {
		"icon": "fa-regular fa-folder-open",
		"icon_color": "#0284c7",
		"description": "Acompanhe o progresso dos seus projetos e tarefas.",
	},
	"/issues": {
		"icon": "fa-solid fa-life-ring",
		"icon_color": "#ea580c",
		"description": "Abra um ticket ou contacte o seu gestor de conta.",
	},
	"/rfq": {
		"icon": "fa-regular fa-file-lines",
		"icon_color": "#7c3aed",
		"description": "Consulte pedidos de cotação e responda online.",
	},
	"/supplier-quotations": {
		"icon": "fa-regular fa-file",
		"icon_color": "#2563eb",
		"description": "Submeta e acompanhe as suas cotações de fornecedor.",
	},
	"/purchase-orders": {
		"icon": "fa-solid fa-cart-shopping",
		"icon_color": "#0284c7",
		"description": "Confirme e acompanhe as encomendas de compra.",
	},
	"/purchase-invoices": {
		"icon": "fa-solid fa-credit-card",
		"icon_color": "#dc2626",
		"description": "Gerir faturas e pagamentos de fornecedor.",
	},
	"/shipments": {
		"icon": "fa-solid fa-truck",
		"icon_color": "#16a34a",
		"description": "Siga o estado das expedições e entregas.",
	},
	"/timesheets": {
		"icon": "fa-regular fa-clock",
		"icon_color": "#64748b",
		"description": "Consulte registos de horas e timesheets.",
	},
	"/material-requests": {
		"icon": "fa-solid fa-truck",
		"icon_color": "#0d9488",
		"description": "Acompanhe pedidos de material e requisições.",
	},
	"/addresses": {
		"icon": "fa-solid fa-location-dot",
		"icon_color": "#ea580c",
		"description": "Gerir moradas de entrega e faturação.",
	},
	"/artigos": {
		"icon": "fa-solid fa-boxes-stacked",
		"icon_color": "#0d9488",
		"description": "Consulte o catálogo e preços da lista de venda e peça orçamento.",
	},
}


def get_context(context, **dict_params):
	frappe_portal.get_context(context, **dict_params)

	if context.get("doctype"):
		return context

	context.update(get_portal_home_context())
	return context


def get_portal_home_context():
	from frappe.website.utils import get_portal_sidebar_items

	roles = set(frappe.get_roles())
	is_supplier = "Supplier" in roles
	is_customer = "Customer" in roles

	if is_supplier and not is_customer:
		headline = _("Gerir, cotar, entregar.")
		subheadline = _(
			"O portal de fornecedores para acompanhar RFQs, encomendas de compra e faturação num só lugar."
		)
	elif is_customer:
		headline = _("Gerir, acompanhar, colaborar.")
		subheadline = _(
			"O portal de clientes para encomendas, faturas, projetos e suporte — tudo centralizado."
		)
	else:
		headline = _("Gerir, acompanhar, colaborar.")
		subheadline = _(
			"A plataforma unificada para clientes e fornecedores acompanhar encomendas e comunicação."
		)

	feature_cards = []
	seen_routes = set()

	for item in get_portal_sidebar_items():
		route = item.get("route") or "/"
		if route in seen_routes or route in ("/me", "/portal"):
			continue

		meta = FEATURE_CARD_META.get(route, {})
		feature_cards.append(
			{
				"title": item.get("title") or item.get("label"),
				"route": route,
				"icon": meta.get("icon", "fa-solid fa-angle-right"),
				"icon_color": meta.get("icon_color", "#0284c7"),
				"description": _(meta.get("description", "Aceda a esta secção do portal.")),
			}
		)
		seen_routes.add(route)

		if len(feature_cards) >= 4:
			break

	company_name = frappe.get_website_settings("app_name") or frappe.db.get_default("company")
	is_guest = frappe.session.user == "Guest"
	full_name = None if is_guest else frappe.utils.get_fullname(frappe.session.user)
	cta_route = "/login" if is_guest else (feature_cards[0]["route"] if feature_cards else "/me")

	return {
		"portal_home": True,
		"portal_headline": headline,
		"portal_subheadline": subheadline,
		"portal_feature_cards": feature_cards,
		"portal_company_name": company_name,
		"portal_user_name": full_name,
		"portal_cta_route": cta_route,
		"portal_cta_label": _("Entrar no portal") if is_guest else _("Explorar portal"),
		"portal_is_supplier": is_supplier and not is_customer,
		"portal_is_customer": is_customer,
		"portal_is_guest": is_guest,
	}
