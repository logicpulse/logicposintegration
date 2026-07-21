# Artigos Portal Parceiro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catálogo `/artigos` no portal de parceiros com preços só de `PVR-PT`, carrinho em localStorage e pedido de orçamento por email ao Account Manager.

**Architecture:** Página web em `logicposintegration` + API whitelisted que lê `Item Price`/`Item` com price list fixa `PVR-PT`. Checkout revalida preços no servidor, resolve o Customer via `Portal User`, e envia email ao `account_manager` (fallback `PARTNER_QUOTE_FALLBACK_EMAIL`). Sem Quotation/Sales Order.

**Tech Stack:** Frappe/ERPNext, Jinja (`www/`), vanilla JS + jQuery (`frappe.call`), CSS alinhado ao portal (`#0f172a` / `#64748b`), patch idempotente em Portal Settings.

**Spec:** `docs/superpowers/specs/2026-07-20-artigos-portal-parceiro-design.md`

## Global Constraints

- Implementar **apenas** em `apps/logicposintegration/` (não alterar `frappe` / `erpnext` / `hrms`).
- Price list canónica: **`PVR-PT`** (nunca aceitar `price_list` do cliente).
- Roles: **Customer** (e System Manager para suporte); Guest bloqueado.
- Checkout: **só email** — não criar Quotation, Sales Order nem Issue.
- Carrinho: **localStorage** (chave `logicpos_partner_cart`).
- Respostas e UI em **português** (mensagens `_()` quando fizer sentido).
- Commits: só quando o utilizador pedir explicitamente (omitir passos de commit se não pedidos).

---

## File map

| Ficheiro | Responsabilidade |
|----------|------------------|
| `logicposintegration/logicpos_integration/partner_articles.py` | Constantes, auth, query catálogo, checkout + email |
| `logicposintegration/logicpos_integration/test_partner_articles.py` | Testes unitários da API |
| `logicposintegration/www/artigos.py` | `get_context` da página |
| `logicposintegration/www/artigos.html` | Markup catálogo + drawer + modal |
| `logicposintegration/public/js/artigos.js` | Fetch, cards, carrinho localStorage, pedido |
| `logicposintegration/public/css/artigos.css` | Estilos do catálogo/drawer |
| `logicposintegration/hooks.py` | Incluir `artigos.css` em `web_include_css` |
| `logicposintegration/templates/includes/web_sidebar.html` | Ícone `/artigos` |
| `logicposintegration/www/portal.py` | `FEATURE_CARD_META` para `/artigos` |
| `logicposintegration/patches/v1_0/add_artigos_portal_menu.py` | Menu item Portal Settings |
| `logicposintegration/patches.txt` | Registar patch |

---

### Task 1: API — listagem `get_partner_articles`

**Files:**
- Create: `logicposintegration/logicpos_integration/partner_articles.py`
- Create: `logicposintegration/logicpos_integration/test_partner_articles.py`

**Interfaces:**
- Consumes: Frappe DB (`Item Price`, `Item`), `frappe.get_roles`, `frappe.session`
- Produces:
  - `PARTNER_PRICE_LIST = "PVR-PT"`
  - `PARTNER_QUOTE_FALLBACK_EMAIL = ""`  # preencher se necessário no site
  - `assert_partner_access() -> None`
  - `get_partner_articles(search=None, page=1, page_size=24) -> dict` com keys `items`, `total`, `page`, `page_size`
  - Cada item: `item_code`, `item_name`, `price_list_rate`, `currency`, `uom`, `image`

- [ ] **Step 1: Criar teste que falha para listagem PVR-PT**

Criar `logicposintegration/logicpos_integration/test_partner_articles.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestPartnerArticles(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Price List", "PVR-PT"):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": "PVR-PT",
					"selling": 1,
					"currency": "EUR",
					"enabled": 1,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("Item", "_Test Partner Article"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "_Test Partner Article",
					"item_name": "_Test Partner Article",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists(
			"Item Price",
			{"item_code": "_Test Partner Article", "price_list": "PVR-PT"},
		):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": "_Test Partner Article",
					"price_list": "PVR-PT",
					"price_list_rate": 12.5,
					"currency": "EUR",
				}
			).insert(ignore_permissions=True)

	def test_get_partner_articles_returns_pvr_pt_only(self):
		from logicposintegration.logicpos_integration.partner_articles import (
			get_partner_articles,
		)

		# System Manager passa assert_partner_access
		result = get_partner_articles(search="_Test Partner Article", page=1, page_size=24)
		codes = [i["item_code"] for i in result["items"]]
		self.assertIn("_Test Partner Article", codes)
		row = next(i for i in result["items"] if i["item_code"] == "_Test Partner Article")
		self.assertEqual(float(row["price_list_rate"]), 12.5)
		self.assertEqual(result["page"], 1)
```

- [ ] **Step 2: Correr o teste e confirmar FAIL**

Run:

```bash
cd /workspace/development/frappe-bench && bench --site development.localhost run-tests --app logicposintegration --module logicposintegration.logicpos_integration.test_partner_articles
```

Expected: FAIL (módulo / função inexistente).

- [ ] **Step 3: Implementar `partner_articles.py` (auth + listagem)**

Criar `logicposintegration/logicpos_integration/partner_articles.py` com este conteúdo completo:

```python
import frappe
from frappe import _
from frappe.utils import cint, flt

PARTNER_PRICE_LIST = "PVR-PT"
PARTNER_QUOTE_FALLBACK_EMAIL = ""  # email comercial se account_manager vazio


def assert_partner_access():
	if frappe.session.user == "Guest":
		frappe.throw(_("É necessário iniciar sessão."), frappe.PermissionError)
	roles = set(frappe.get_roles())
	if "Customer" not in roles and "System Manager" not in roles:
		frappe.throw(_("Sem permissão para aceder aos artigos."), frappe.PermissionError)


def _count_active_partner_prices(search=None):
	conditions = ["ip.price_list = %(price_list)s", "IFNULL(i.disabled, 0) = 0"]
	values = {"price_list": PARTNER_PRICE_LIST}
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


def _list_active_partner_prices(search, offset, page_size):
	conditions = ["ip.price_list = %(price_list)s", "IFNULL(i.disabled, 0) = 0"]
	values = {
		"price_list": PARTNER_PRICE_LIST,
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
	page = max(cint(page), 1)
	page_size = min(max(cint(page_size), 1), 48)
	offset = (page - 1) * page_size
	search = (search or "").strip() or None
	items = _list_active_partner_prices(search, offset, page_size)
	for row in items:
		row["price_list_rate"] = flt(row["price_list_rate"])
	return {
		"items": items,
		"total": _count_active_partner_prices(search),
		"page": page,
		"page_size": page_size,
	}
```

- [ ] **Step 4: Correr o teste e confirmar PASS**

Mesmo comando do Step 2. Expected: PASS.

- [ ] **Step 5: Commit (só se o utilizador pedir)**

```bash
git add logicposintegration/logicpos_integration/partner_articles.py \
  logicposintegration/logicpos_integration/test_partner_articles.py
git commit -m "$(cat <<'EOF'
feat: API get_partner_articles com price list PVR-PT

EOF
)"
```

---

### Task 2: API — `request_partner_quote` + email

**Files:**
- Modify: `logicposintegration/logicpos_integration/partner_articles.py`
- Modify: `logicposintegration/logicpos_integration/test_partner_articles.py`

**Interfaces:**
- Consumes: `assert_partner_access`, `PARTNER_PRICE_LIST`, `PARTNER_QUOTE_FALLBACK_EMAIL`
- Produces:
  - `get_partner_customer() -> str` (Customer name)
  - `resolve_quote_recipient(customer: str) -> str` (email)
  - `request_partner_quote(items, notes=None) -> dict` com `{"ok": True, "sent_to": email}`

- [ ] **Step 1: Adicionar testes que falham**

No `TestPartnerArticles`, adicionar:

```python
	def test_request_partner_quote_rejects_guest_price_tampering(self):
		from logicposintegration.logicpos_integration.partner_articles import (
			request_partner_quote,
		)
		from unittest.mock import patch

		# Customer + Portal User mínimos: criar se necessário no setUp helper
		self._ensure_partner_user()
		frappe.set_user(self.partner_user)

		with patch(
			"logicposintegration.logicpos_integration.partner_articles.frappe.sendmail"
		) as sendmail:
			result = request_partner_quote(
				items=[{"item_code": "_Test Partner Article", "qty": 2, "rate": 0.01}],
				notes="Pedido teste",
			)
			self.assertTrue(result["ok"])
			self.assertTrue(sendmail.called)
			args, kwargs = sendmail.call_args
			html = kwargs.get("message") or ""
			self.assertIn("12.5", html)  # preço servidor, não 0.01
			self.assertNotIn("0.01", html)

	def test_request_partner_quote_fails_without_recipient(self):
		from logicposintegration.logicpos_integration.partner_articles import (
			PARTNER_QUOTE_FALLBACK_EMAIL,
			request_partner_quote,
		)
		import logicposintegration.logicpos_integration.partner_articles as mod

		self._ensure_partner_user(account_manager=None)
		frappe.set_user(self.partner_user)
		original = mod.PARTNER_QUOTE_FALLBACK_EMAIL
		mod.PARTNER_QUOTE_FALLBACK_EMAIL = ""
		try:
			with self.assertRaises(frappe.ValidationError):
				request_partner_quote(
					items=[{"item_code": "_Test Partner Article", "qty": 1}]
				)
		finally:
			mod.PARTNER_QUOTE_FALLBACK_EMAIL = original

	def _ensure_partner_user(self, account_manager="Administrator"):
		email = "partner_articles_test@example.com"
		self.partner_user = email
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Partner",
					"send_welcome_email": 0,
					"user_type": "Website User",
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Customer")

		customer_name = "_Test Partner Customer"
		if not frappe.db.exists("Customer", customer_name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"customer_type": "Company",
					"account_manager": account_manager,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Customer", customer_name, "account_manager", account_manager)

		# Portal User child
		cust = frappe.get_doc("Customer", customer_name)
		if not any(p.user == email for p in cust.get("portal_users") or []):
			cust.append("portal_users", {"user": email})
			cust.save(ignore_permissions=True)
```

Nota: `account_manager` é Link para User — se `None`, limpar o campo. Ajustar o helper:

```python
frappe.db.set_value(
	"Customer",
	customer_name,
	"account_manager",
	account_manager or "",
)
```

- [ ] **Step 2: Correr testes — FAIL**

Expected: FAIL (`request_partner_quote` em falta).

- [ ] **Step 3: Implementar checkout + email**

Acrescentar a `partner_articles.py`:

```python
import json


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
			_(
				"Não há Account Manager definido para o seu cliente. Contacte o suporte."
			)
		)
	return email


def _load_server_lines(items):
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
			{"item_code": item_code, "price_list": PARTNER_PRICE_LIST},
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
			_("Itens sem preço PVR-PT ou inválidos: {0}").format(", ".join(invalid))
		)
	if not lines:
		frappe.throw(_("Nenhuma linha válida no pedido."))
	return lines


def _build_quote_email_html(customer, lines, notes, requester):
	from frappe.utils import fmt_money

	currency = lines[0]["currency"]
	rows = "".join(
		f"<tr><td>{frappe.utils.escape_html(l['item_code'])}</td>"
		f"<td>{frappe.utils.escape_html(l['item_name'] or '')}</td>"
		f"<td style='text-align:right'>{l['qty']}</td>"
		f"<td style='text-align:right'>{fmt_money(l['rate'], currency=currency)}</td>"
		f"<td style='text-align:right'>{fmt_money(l['amount'], currency=currency)}</td></tr>"
		for l in lines
	)
	total = sum(l["amount"] for l in lines)
	notes_html = frappe.utils.escape_html(notes or "") or "—"
	return f"""
	<p>Pedido de orçamento do parceiro <strong>{frappe.utils.escape_html(customer)}</strong>.</p>
	<p>Utilizador: {frappe.utils.escape_html(requester)} ({frappe.utils.escape_html(frappe.session.user)})</p>
	<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
	<thead><tr>
		<th>Código</th><th>Artigo</th><th>Qty</th><th>Preço</th><th>Total</th>
	</tr></thead>
	<tbody>{rows}</tbody>
	</table>
	<p><strong>Total estimado ({frappe.utils.escape_html(PARTNER_PRICE_LIST)}):</strong>
	{fmt_money(total, currency=currency)}</p>
	<p><strong>Notas:</strong> {notes_html}</p>
	"""


@frappe.whitelist()
def request_partner_quote(items, notes=None):
	assert_partner_access()
	customer = get_partner_customer()
	lines = _load_server_lines(items)
	recipient = resolve_quote_recipient(customer)
	requester = frappe.utils.get_fullname(frappe.session.user)
	html = _build_quote_email_html(customer, lines, notes, requester)

	cc = []
	user_email = frappe.db.get_value("User", frappe.session.user, "email")
	if user_email and user_email != recipient:
		cc.append(user_email)

	frappe.sendmail(
		recipients=[recipient],
		cc=cc or None,
		subject=_("Pedido de orçamento — {0}").format(customer),
		message=html,
		now=True,
	)
	return {"ok": True, "sent_to": recipient}
```

Definir `PARTNER_QUOTE_FALLBACK_EMAIL` com um email real de fallback do projeto se existir; caso contrário deixar `""` e documentar no README interno / comentário.

- [ ] **Step 4: Correr testes — PASS**

Expected: PASS (com mock de `sendmail`).

- [ ] **Step 5: Commit (só se pedido)**

```bash
git add logicposintegration/logicpos_integration/partner_articles.py \
  logicposintegration/logicpos_integration/test_partner_articles.py
git commit -m "$(cat <<'EOF'
feat: pedido de orçamento por email ao account manager

EOF
)"
```

---

### Task 3: Página web `/artigos` (backend + HTML)

**Files:**
- Create: `logicposintegration/www/artigos.py`
- Create: `logicposintegration/www/artigos.html`
- Modify: `logicposintegration/hooks.py` (CSS include)

**Interfaces:**
- Consumes: `assert_partner_access` (opcional no context; a página também redireciona Guest)
- Produces: rota `/artigos` com `no_cache = 1`, `show_sidebar = 1`

- [ ] **Step 1: Criar `artigos.py`**

```python
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
		"description": _("Catálogo de artigos com preços PVR-PT"),
	}
	return context
```

- [ ] **Step 2: Criar `artigos.html`**

```html
{% extends "templates/web.html" %}

{% block head_include %}
<link rel="stylesheet" href="/assets/logicposintegration/css/artigos.css">
{% endblock %}

{% block page_content %}
<div class="partner-artigos" id="partner-artigos"
	data-api-list="logicposintegration.logicpos_integration.partner_articles.get_partner_articles"
	data-api-quote="logicposintegration.logicpos_integration.partner_articles.request_partner_quote">

	<header class="partner-artigos-header">
		<h1 class="partner-artigos-title">{{ _("Artigos") }}</h1>
		<p class="partner-artigos-sub">{{ _("Preços da lista PVR-PT") }}</p>
		<div class="partner-artigos-toolbar">
			<input type="search" id="artigos-search" class="form-control partner-artigos-search"
				placeholder="{{ _('Pesquisar por código ou nome') }}" autocomplete="off">
			<button type="button" class="btn btn-primary partner-artigos-cart-btn" id="artigos-cart-toggle"
				aria-expanded="false">
				<i class="fa-solid fa-cart-shopping" aria-hidden="true"></i>
				<span>{{ _("Carrinho") }}</span>
				<span class="partner-artigos-cart-badge" id="artigos-cart-count">0</span>
			</button>
		</div>
	</header>

	<div class="partner-artigos-grid" id="artigos-grid" aria-live="polite"></div>
	<div class="partner-artigos-pagination" id="artigos-pagination"></div>
	<p class="partner-artigos-empty d-none" id="artigos-empty">{{ _("Nenhum artigo encontrado.") }}</p>

	<aside class="partner-artigos-drawer" id="artigos-drawer" hidden>
		<div class="partner-artigos-drawer-panel">
			<header class="partner-artigos-drawer-header">
				<h2>{{ _("Carrinho") }}</h2>
				<button type="button" class="btn btn-sm btn-light" id="artigos-drawer-close">{{ _("Fechar") }}</button>
			</header>
			<ul class="partner-artigos-cart-list" id="artigos-cart-list"></ul>
			<div class="partner-artigos-cart-footer">
				<p class="partner-artigos-cart-total">{{ _("Total estimado") }}:
					<strong id="artigos-cart-total">—</strong></p>
				<label class="partner-artigos-notes-label" for="artigos-notes">{{ _("Notas") }}</label>
				<textarea id="artigos-notes" class="form-control" rows="3"
					placeholder="{{ _('Mensagem opcional para a equipa comercial') }}"></textarea>
				<button type="button" class="btn btn-primary btn-block" id="artigos-request-quote" disabled>
					{{ _("Pedir orçamento") }}
				</button>
			</div>
		</div>
	</aside>
</div>

<script src="/assets/logicposintegration/js/artigos.js"></script>
{% endblock %}
```

- [ ] **Step 3: Adicionar CSS global ao hooks (opcional reforço)**

Em `hooks.py`, acrescentar a `web_include_css`:

```python
"/assets/logicposintegration/css/artigos.css",
```

(O template já inclui; o hooks garante consistência com outras páginas do portal.)

- [ ] **Step 4: Verificar rota**

```bash
cd /workspace/development/frappe-bench && bench --site development.localhost clear-cache
# Abrir /artigos autenticado como Customer — deve renderizar o shell (grid vazio até JS)
```

Expected: HTML 200, título Artigos, sem traceback.

- [ ] **Step 5: Commit (só se pedido)**

---

### Task 4: CSS + JS do catálogo e carrinho

**Files:**
- Create: `logicposintegration/public/css/artigos.css`
- Create: `logicposintegration/public/js/artigos.js`

**Interfaces:**
- Consumes: APIs Task 1–2 via `frappe.call`; localStorage key `logicpos_partner_cart`
- Produces: UI interativa (cards, drawer, pedido)

- [ ] **Step 1: Criar `artigos.css`**

Estilo alinhado ao portal (`#0f172a`, `#64748b`, cards com border `#e2e8f0`, radius 12px):

```css
.partner-artigos { max-width: 1100px; margin: 0 auto; padding: 0.5rem 0 2.5rem; }
.partner-artigos-title { font-size: clamp(1.75rem, 4vw, 2.25rem); font-weight: 700; color: #0f172a; margin: 0 0 0.35rem; }
.partner-artigos-sub { color: #64748b; margin: 0 0 1.25rem; }
.partner-artigos-toolbar { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.25rem; }
.partner-artigos-search { flex: 1; min-width: 200px; }
.partner-artigos-cart-btn { display: inline-flex; align-items: center; gap: 0.4rem; background: #0f172a; border-color: #0f172a; }
.partner-artigos-cart-badge { background: #fff; color: #0f172a; border-radius: 999px; padding: 0 0.45rem; font-size: 0.75rem; font-weight: 700; }
.partner-artigos-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
.partner-artigos-card { display: flex; flex-direction: column; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; overflow: hidden; }
.partner-artigos-card-image { aspect-ratio: 4/3; background: #f1f5f9; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.partner-artigos-card-image img { width: 100%; height: 100%; object-fit: contain; }
.partner-artigos-card-body { padding: 0.9rem 1rem 1rem; display: flex; flex-direction: column; gap: 0.35rem; flex: 1; }
.partner-artigos-card-name { font-weight: 600; color: #0f172a; font-size: 0.95rem; line-height: 1.35; margin: 0; }
.partner-artigos-card-code { font-size: 0.75rem; color: #64748b; }
.partner-artigos-card-price { font-weight: 700; color: #0f172a; margin-top: auto; }
.partner-artigos-card .btn { margin-top: 0.5rem; }
.partner-artigos-pagination { display: flex; justify-content: center; gap: 0.5rem; margin-top: 1.5rem; }
.partner-artigos-drawer { position: fixed; inset: 0; background: rgba(15,23,42,0.35); z-index: 1040; }
.partner-artigos-drawer[hidden] { display: none !important; }
.partner-artigos-drawer-panel { position: absolute; right: 0; top: 0; bottom: 0; width: min(400px, 100%); background: #fff; padding: 1rem; display: flex; flex-direction: column; box-shadow: -8px 0 24px rgba(15,23,42,0.12); }
.partner-artigos-drawer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.partner-artigos-cart-list { list-style: none; padding: 0; margin: 0; overflow: auto; flex: 1; }
.partner-artigos-cart-list li { display: grid; grid-template-columns: 1fr auto; gap: 0.35rem 0.75rem; padding: 0.75rem 0; border-bottom: 1px solid #e2e8f0; }
.partner-artigos-cart-footer { padding-top: 1rem; border-top: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 0.5rem; }
.partner-artigos-empty { text-align: center; color: #64748b; margin-top: 2rem; }
```

- [ ] **Step 2: Criar `artigos.js`**

```javascript
(function () {
	const ROOT = document.getElementById("partner-artigos");
	if (!ROOT) return;

	const STORAGE_KEY = "logicpos_partner_cart";
	const apiList = ROOT.dataset.apiList;
	const apiQuote = ROOT.dataset.apiQuote;

	const els = {
		grid: document.getElementById("artigos-grid"),
		empty: document.getElementById("artigos-empty"),
		pagination: document.getElementById("artigos-pagination"),
		search: document.getElementById("artigos-search"),
		cartCount: document.getElementById("artigos-cart-count"),
		cartToggle: document.getElementById("artigos-cart-toggle"),
		drawer: document.getElementById("artigos-drawer"),
		drawerClose: document.getElementById("artigos-drawer-close"),
		cartList: document.getElementById("artigos-cart-list"),
		cartTotal: document.getElementById("artigos-cart-total"),
		notes: document.getElementById("artigos-notes"),
		requestBtn: document.getElementById("artigos-request-quote"),
	};

	let state = { page: 1, pageSize: 24, total: 0, search: "", loading: false };

	function loadCart() {
		try {
			return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
		} catch (e) {
			return [];
		}
	}

	function saveCart(cart) {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
		renderCart();
	}

	function formatMoney(amount, currency) {
		return format_currency(amount, currency || "EUR");
	}

	function fetchArticles() {
		if (state.loading) return;
		state.loading = true;
		frappe.call({
			method: apiList,
			args: { search: state.search || null, page: state.page, page_size: state.pageSize },
			callback: function (r) {
				state.loading = false;
				const data = r.message || {};
				state.total = data.total || 0;
				renderGrid(data.items || []);
				renderPagination();
			},
			error: function () {
				state.loading = false;
			},
		});
	}

	function renderGrid(items) {
		els.grid.innerHTML = "";
		els.empty.classList.toggle("d-none", items.length > 0);
		items.forEach(function (item) {
			const card = document.createElement("article");
			card.className = "partner-artigos-card";
			const img = item.image
				? `<img src="${frappe.utils.escape_html(item.image)}" alt="">`
				: `<i class="fa-solid fa-box" style="color:#94a3b8;font-size:2rem" aria-hidden="true"></i>`;
			card.innerHTML = `
				<div class="partner-artigos-card-image">${img}</div>
				<div class="partner-artigos-card-body">
					<p class="partner-artigos-card-code">${frappe.utils.escape_html(item.item_code)}</p>
					<h3 class="partner-artigos-card-name">${frappe.utils.escape_html(item.item_name || "")}</h3>
					<p class="partner-artigos-card-price">${formatMoney(item.price_list_rate, item.currency)}</p>
					<button type="button" class="btn btn-sm btn-secondary btn-block">${__("Adicionar")}</button>
				</div>`;
			card.querySelector("button").addEventListener("click", function () {
				addToCart(item);
			});
			els.grid.appendChild(card);
		});
	}

	function renderPagination() {
		els.pagination.innerHTML = "";
		const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
		if (pages <= 1) return;
		const prev = document.createElement("button");
		prev.className = "btn btn-sm btn-light";
		prev.textContent = __("Anterior");
		prev.disabled = state.page <= 1;
		prev.onclick = function () {
			state.page -= 1;
			fetchArticles();
		};
		const next = document.createElement("button");
		next.className = "btn btn-sm btn-light";
		next.textContent = __("Seguinte");
		next.disabled = state.page >= pages;
		next.onclick = function () {
			state.page += 1;
			fetchArticles();
		};
		const info = document.createElement("span");
		info.textContent = state.page + " / " + pages;
		els.pagination.append(prev, info, next);
	}

	function addToCart(item) {
		const cart = loadCart();
		const existing = cart.find(function (c) {
			return c.item_code === item.item_code;
		});
		if (existing) {
			existing.qty += 1;
		} else {
			cart.push({
				item_code: item.item_code,
				item_name: item.item_name,
				qty: 1,
				price_list_rate: item.price_list_rate,
				currency: item.currency,
			});
		}
		saveCart(cart);
		frappe.show_alert({ message: __("Adicionado ao carrinho"), indicator: "green" });
	}

	function renderCart() {
		const cart = loadCart();
		const count = cart.reduce(function (s, c) {
			return s + (c.qty || 0);
		}, 0);
		els.cartCount.textContent = String(count);
		els.requestBtn.disabled = count === 0;
		els.cartList.innerHTML = "";
		let total = 0;
		let currency = "EUR";
		cart.forEach(function (line) {
			currency = line.currency || currency;
			total += (line.price_list_rate || 0) * (line.qty || 0);
			const li = document.createElement("li");
			li.innerHTML = `
				<div>
					<strong>${frappe.utils.escape_html(line.item_name || line.item_code)}</strong>
					<div class="text-muted small">${frappe.utils.escape_html(line.item_code)}</div>
					<div class="mt-1">
						<button type="button" class="btn btn-xs btn-light" data-act="dec">−</button>
						<span class="mx-1">${line.qty}</span>
						<button type="button" class="btn btn-xs btn-light" data-act="inc">+</button>
						<button type="button" class="btn btn-xs btn-link text-danger" data-act="rm">${__("Remover")}</button>
					</div>
				</div>
				<div>${formatMoney((line.price_list_rate || 0) * line.qty, currency)}</div>`;
			li.querySelector('[data-act="dec"]').onclick = function () {
				updateQty(line.item_code, -1);
			};
			li.querySelector('[data-act="inc"]').onclick = function () {
				updateQty(line.item_code, 1);
			};
			li.querySelector('[data-act="rm"]').onclick = function () {
				removeLine(line.item_code);
			};
			els.cartList.appendChild(li);
		});
		els.cartTotal.textContent = count ? formatMoney(total, currency) : "—";
	}

	function updateQty(item_code, delta) {
		const cart = loadCart();
		const line = cart.find(function (c) {
			return c.item_code === item_code;
		});
		if (!line) return;
		line.qty += delta;
		if (line.qty <= 0) {
			saveCart(
				cart.filter(function (c) {
					return c.item_code !== item_code;
				})
			);
		} else {
			saveCart(cart);
		}
	}

	function removeLine(item_code) {
		saveCart(
			loadCart().filter(function (c) {
				return c.item_code !== item_code;
			})
		);
	}

	function openDrawer(open) {
		if (open) {
			els.drawer.hidden = false;
			els.cartToggle.setAttribute("aria-expanded", "true");
		} else {
			els.drawer.hidden = true;
			els.cartToggle.setAttribute("aria-expanded", "false");
		}
	}

	els.cartToggle.addEventListener("click", function () {
		openDrawer(els.drawer.hidden);
	});
	els.drawerClose.addEventListener("click", function () {
		openDrawer(false);
	});
	els.drawer.addEventListener("click", function (e) {
		if (e.target === els.drawer) openDrawer(false);
	});

	let searchTimer = null;
	els.search.addEventListener("input", function () {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(function () {
			state.search = els.search.value.trim();
			state.page = 1;
			fetchArticles();
		}, 300);
	});

	els.requestBtn.addEventListener("click", function () {
		const cart = loadCart();
		if (!cart.length) return;
		els.requestBtn.disabled = true;
		frappe.call({
			method: apiQuote,
			args: {
				items: cart.map(function (c) {
					return { item_code: c.item_code, qty: c.qty };
				}),
				notes: els.notes.value || null,
			},
			callback: function (r) {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("Pedido enviado"),
						message: __("O pedido de orçamento foi enviado à equipa comercial."),
						indicator: "green",
					});
					saveCart([]);
					els.notes.value = "";
					openDrawer(false);
				}
				els.requestBtn.disabled = loadCart().length === 0;
			},
			error: function () {
				els.requestBtn.disabled = loadCart().length === 0;
			},
		});
	});

	renderCart();
	fetchArticles();
})();
```

- [ ] **Step 3: Build assets / clear cache**

```bash
cd /workspace/development/frappe-bench && bench build --app logicposintegration && bench --site development.localhost clear-cache
```

Expected: assets publicados em `/assets/logicposintegration/...`.

- [ ] **Step 4: Teste manual rápido**

1. Login como Customer com Portal User.
2. Abrir `/artigos` — cards com preços.
3. Adicionar 2 itens, pedir orçamento (com `PARTNER_QUOTE_FALLBACK_EMAIL` ou AM definido).
4. Confirmar email em Email Queue / logs.

- [ ] **Step 5: Commit (só se pedido)**

---

### Task 5: Sidebar, portal home e patch Portal Settings

**Files:**
- Modify: `logicposintegration/templates/includes/web_sidebar.html` (mapa de ícones)
- Modify: `logicposintegration/www/portal.py` (`FEATURE_CARD_META`)
- Create: `logicposintegration/patches/v1_0/add_artigos_portal_menu.py`
- Modify: `logicposintegration/patches.txt`

**Interfaces:**
- Consumes: Portal Settings single
- Produces: menu item title `Artigos`, route `/artigos`, role `Customer`, enabled=1

- [ ] **Step 1: Ícone na sidebar**

Em `web_sidebar.html`, no dict `icons`, adicionar:

```python
'/artigos': 'fa-solid fa-boxes-stacked',
```

(é Jinja dict — mesma sintaxe das linhas existentes.)

- [ ] **Step 2: Card no portal home**

Em `portal.py` `FEATURE_CARD_META`:

```python
"/artigos": {
	"icon": "fa-solid fa-boxes-stacked",
	"icon_color": "#0d9488",
	"description": "Consulte o catálogo e preços PVR-PT e peça orçamento.",
},
```

- [ ] **Step 3: Patch idempotente**

Criar `logicposintegration/patches/v1_0/add_artigos_portal_menu.py`:

```python
import frappe


def execute():
	ps = frappe.get_single("Portal Settings")
	if any((row.route or "").rstrip("/") == "/artigos" for row in ps.menu):
		return
	ps.append(
		"menu",
		{
			"title": "Artigos",
			"enabled": 1,
			"route": "/artigos",
			"reference_doctype": "",
			"role": "Customer",
		},
	)
	ps.save(ignore_permissions=True)
	frappe.db.commit()
```

Em `patches.txt` sob `[post_model_sync]`:

```
logicposintegration.patches.v1_0.add_artigos_portal_menu
```

- [ ] **Step 4: Migrar**

```bash
cd /workspace/development/frappe-bench && bench --site development.localhost migrate
```

Expected: item Artigos em Portal Settings; aparece na sidebar para Customer.

- [ ] **Step 5: Verificação final**

Checklist:
- [ ] Sidebar mostra Artigos (Customer)
- [ ] `/artigos` lista só PVR-PT
- [ ] Guest redirecionado / sem acesso
- [ ] Pedido envia email; sem Quotation/SO criado
- [ ] Carrinho limpa após sucesso

- [ ] **Step 6: Commit (só se pedido)**

```bash
git add logicposintegration/templates/includes/web_sidebar.html \
  logicposintegration/www/portal.py \
  logicposintegration/patches/v1_0/add_artigos_portal_menu.py \
  logicposintegration/patches.txt
git commit -m "$(cat <<'EOF'
feat: item Artigos na sidebar do portal de parceiros

EOF
)"
```

---

## Self-review (plan vs spec)

| Requisito spec | Task |
|----------------|------|
| Sidebar Artigos + role Customer | Task 5 |
| Página `/artigos` cards + pesquisa + paginação | Tasks 3–4 |
| Só PVR-PT | Task 1 |
| Carrinho localStorage | Task 4 |
| Email ao account_manager + fallback | Task 2 |
| Sem Quotation/SO | Task 2 (só `sendmail`) |
| Só logicposintegration | Todas |
| Patch Portal Settings | Task 5 |
| Ícone + FEATURE_CARD_META | Task 5 |

**Nota operacional:** neste site `account_manager` está vazio em todos os Customers — definir `PARTNER_QUOTE_FALLBACK_EMAIL` antes de testar o fluxo de email em staging, ou preencher Account Manager num cliente de teste.
