import json

import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, fmt_money

PARTNER_QUOTE_FALLBACK_EMAIL = "hailes.mauricio@logicpulse.com"  # email comercial se account_manager vazio

CURRENCY_TO_PRICE_LIST_SUFFIX = {
	"AOA": "-AO",
	"EUR": "-PT",
	"MZN": "-MZ",
}


def resolve_partner_price_list(customer: str) -> str:
	"""PVP/PVR × sufixo de moeda; PVR em falta → fallback PVP mesma moeda."""
	row = frappe.db.get_value(
		"Customer",
		customer,
		["customer_type", "default_currency"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Cliente inválido."))

	currency = (row.default_currency or "").strip().upper()
	suffix = CURRENCY_TO_PRICE_LIST_SUFFIX.get(currency)
	if not suffix:
		frappe.throw(
			_(
				"Moeda base do cliente não configurada ou não suportada ({0}). "
				"Use AOA, EUR ou MZN."
			).format(currency or _("vazio"))
		)

	prefix = "PVR" if row.customer_type == "Partnership" else "PVP"
	price_list = f"{prefix}{suffix}"

	if frappe.db.exists("Price List", price_list):
		return price_list

	if prefix == "PVR":
		fallback = f"PVP{suffix}"
		if frappe.db.exists("Price List", fallback):
			return fallback
		frappe.throw(
			_("Lista de preços {0} (nem fallback {1}) não existe.").format(
				price_list, fallback
			)
		)

	frappe.throw(_("Lista de preços {0} não existe.").format(price_list))


def assert_partner_access():
	if frappe.session.user == "Guest":
		frappe.throw(_("É necessário iniciar sessão."), frappe.PermissionError)
	roles = set(frappe.get_roles())
	if "Customer" not in roles and "System Manager" not in roles:
		frappe.throw(_("Sem permissão para aceder aos artigos."), frappe.PermissionError)


def _count_active_partner_prices(price_list, search=None):
	conditions = ["ip.price_list = %(price_list)s", "IFNULL(i.disabled, 0) = 0"]
	values = {"price_list": price_list}
	if search:
		conditions.append(
			"(ip.item_code LIKE %(q)s OR ip.item_name LIKE %(q)s OR i.item_name LIKE %(q)s)"
		)
		values["q"] = f"%{search}%"
	where = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT COUNT(*)
		FROM `tabItem Price` ip
		INNER JOIN `tabItem` i ON i.name = ip.item_code
		WHERE {where}
		""",
		values,
	)[0][0]


def _list_active_partner_prices(price_list, search, offset, page_size):
	conditions = ["ip.price_list = %(price_list)s", "IFNULL(i.disabled, 0) = 0"]
	values = {
		"price_list": price_list,
		"limit": page_size,
		"offset": offset,
	}
	if search:
		conditions.append(
			"(ip.item_code LIKE %(q)s OR ip.item_name LIKE %(q)s OR i.item_name LIKE %(q)s)"
		)
		values["q"] = f"%{search}%"
	where = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			ip.item_code,
			i.item_name,
			ip.price_list_rate,
			ip.currency,
			ip.uom,
			i.image
		FROM `tabItem Price` ip
		INNER JOIN `tabItem` i ON i.name = ip.item_code
		WHERE {where}
		ORDER BY i.item_name ASC
		LIMIT %(limit)s OFFSET %(offset)s
		""",
		values,
		as_dict=True,
	)


@frappe.whitelist()
def get_partner_articles(search=None, page=1, page_size=24):
	assert_partner_access()
	customer = get_partner_customer()
	price_list = resolve_partner_price_list(customer)
	page = max(cint(page), 1)
	page_size = min(max(cint(page_size), 1), 48)
	offset = (page - 1) * page_size
	search = (search or "").strip() or None
	items = _list_active_partner_prices(price_list, search, offset, page_size)
	for row in items:
		row["price_list_rate"] = flt(row["price_list_rate"])
	return {
		"items": items,
		"total": _count_active_partner_prices(price_list, search),
		"page": page,
		"page_size": page_size,
		"price_list": price_list,
	}


def get_partner_customer():
	"""Customer ligado ao utilizador via Portal User."""
	customers = frappe.db.get_all(
		"Portal User",
		filters={"user": frappe.session.user, "parenttype": "Customer"},
		pluck="parent",
	)
	if not customers:
		frappe.throw(_("Não foi encontrado um cliente associado à sua conta."))
	return customers[0]


def resolve_quote_recipient(customer: str) -> str:
	account_manager = frappe.db.get_value("Customer", customer, "account_manager")
	email = None
	if account_manager:
		email = frappe.db.get_value("User", account_manager, "email")
	if not email and PARTNER_QUOTE_FALLBACK_EMAIL:
		email = PARTNER_QUOTE_FALLBACK_EMAIL
	if not email:
		frappe.throw(
			_("Não há Account Manager definido para o seu cliente. Contacte o suporte.")
		)
	return email


def _load_server_lines(items, price_list):
	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(_("O carrinho está vazio."))

	lines = []
	invalid = []
	for raw in items:
		item_code = raw.get("item_code")
		qty = flt(raw.get("qty"))
		if not item_code or qty <= 0:
			invalid.append(item_code or "?")
			continue
		price = frappe.db.get_value(
			"Item Price",
			{"item_code": item_code, "price_list": price_list},
			["price_list_rate", "currency", "uom", "item_name"],
			as_dict=True,
		)
		disabled = frappe.db.get_value("Item", item_code, "disabled")
		if not price or disabled:
			invalid.append(item_code)
			continue
		rate = flt(price.price_list_rate)
		lines.append(
			{
				"item_code": item_code,
				"item_name": price.item_name
				or frappe.db.get_value("Item", item_code, "item_name"),
				"qty": qty,
				"rate": rate,
				"amount": rate * qty,
				"currency": price.currency or "EUR",
				"uom": price.uom,
			}
		)

	if invalid:
		frappe.throw(
			_("Itens sem preço {0} ou inválidos: {1}").format(
				price_list, ", ".join(invalid)
			)
		)
	if not lines:
		frappe.throw(_("Nenhuma linha válida no pedido."))
	return lines


def _build_quote_email_html(customer, lines, notes, requester, price_list):
	currency = lines[0]["currency"]
	rows = "".join(
		f"<tr><td>{escape_html(l['item_code'])}</td>"
		f"<td>{escape_html(l['item_name'] or '')}</td>"
		f"<td style='text-align:right'>{l['qty']}</td>"
		f"<td style='text-align:right'>{fmt_money(l['rate'], currency=currency)}</td>"
		f"<td style='text-align:right'>{fmt_money(l['amount'], currency=currency)}</td></tr>"
		for l in lines
	)
	total = sum(l["amount"] for l in lines)
	notes_html = escape_html(notes or "") or "—"
	return f"""
	<p>Pedido de orçamento do parceiro <strong>{escape_html(customer)}</strong>.</p>
	<p>Utilizador: {escape_html(requester)} ({escape_html(frappe.session.user)})</p>
	<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
	<thead><tr>
		<th>Código</th><th>Artigo</th><th>Qty</th><th>Preço</th><th>Total</th>
	</tr></thead>
	<tbody>{rows}</tbody>
	</table>
	<p><strong>Total estimado ({escape_html(price_list)}):</strong>
	{fmt_money(total, currency=currency)}</p>
	<p><strong>Notas:</strong> {notes_html}</p>
	"""


@frappe.whitelist()
def request_partner_quote(items, notes=None):
	assert_partner_access()
	customer = get_partner_customer()
	price_list = resolve_partner_price_list(customer)
	lines = _load_server_lines(items, price_list)
	recipient = resolve_quote_recipient(customer)
	requester = frappe.utils.get_fullname(frappe.session.user)
	html = _build_quote_email_html(customer, lines, notes, requester, price_list)

	cc = []
	user_email = frappe.db.get_value("User", frappe.session.user, "email")
	if user_email and user_email != recipient:
		cc.append(user_email)

	frappe.sendmail(
		recipients=[recipient],
		cc=cc or None,
		subject=_("Pedido de orçamento — {0}").format(customer),
		message=html,
		now=False,
	)
	return {"ok": True, "sent_to": recipient}
