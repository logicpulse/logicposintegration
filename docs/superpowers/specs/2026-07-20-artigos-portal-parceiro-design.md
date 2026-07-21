# Design: Artigos no portal de parceiros

**Data:** 2026-07-20  
**App:** `logicposintegration`  
**Estado:** aprovado em conversa (abordagem 1)

## Objetivo

Permitir que parceiros (Clientes) consultem o catálogo de artigos com preços da price list **PVR-PT** e enviem um pedido de orçamento por email ao Account Manager — sem criar Quotation nem Sales Order.

## Contexto

- O portal usa sidebar de **Portal Settings** + template custom `web_sidebar.html`.
- No site, a price list existe como **`PVR-PT`** (~1181 `Item Price`).
- Não há `E Commerce Settings` / `Website Item` neste ambiente.
- Clientes têm campo `account_manager` no DocType Customer.

## Decisões

| Tema | Decisão |
|------|---------|
| UI | Catálogo em cards (imagem, nome, código, preço) |
| Carrinho | localStorage no browser |
| Checkout | Email/notificação ao `account_manager` (não cria docs de venda) |
| Price list | Fixa no servidor: `PVR-PT` (nunca parametrizável pelo cliente) |
| Onde implementar | Só `logicposintegration` |

## Arquitetura

```
Parceiro (Customer)
    │
    ├─ GET /artigos  → página Jinja + JS (catálogo + drawer carrinho)
    │
    ├─ frappe.call get_partner_articles(search, page)
    │         └─ Item Price WHERE price_list='PVR-PT' + Item (disabled=0)
    │
    └─ frappe.call request_partner_quote(items, notes)
              ├─ revalida preços PVR-PT no servidor
              ├─ resolve Customer do user
              └─ email → account_manager (fallback se vazio)
```

## Componentes

### 1. Sidebar e portal home

- Adicionar item **Artigos** em Portal Settings: route `/artigos`, role `Customer`, enabled.
- Patch idempotente em `patches/` que insere o menu item em Portal Settings se ainda não existir (route `/artigos`).
- Ícone em `templates/includes/web_sidebar.html` (ex. `fa-solid fa-boxes-stacked`).
- Meta em `www/portal.py` `FEATURE_CARD_META` para `/artigos`.

### 2. Página web `/artigos`

Ficheiros previstos:

- `logicposintegration/www/artigos.py` — `get_context` (login required, role Customer).
- `logicposintegration/www/artigos.html` — layout catálogo + drawer/modal.
- Assets: `public/js/artigos.js` e `public/css/artigos.css`, registados via `web_include_js` / `web_include_css` só na página ou incluídos no template.

Comportamento UI:

- Grelha de cards; pesquisa por código/nome; paginação server-side.
- Badge do carrinho; drawer com qty (+/−), remover, total estimado.
- Botão **Pedir orçamento** → notas opcionais → sucesso → limpar localStorage.

### 3. API Python

Módulo: `logicposintegration/logicpos_integration/partner_articles.py` (mesmo padrão de `articles.py` / `customers.py`).

#### `get_partner_articles(search=None, page=1, page_size=24)`

- `@frappe.whitelist()`
- Exige utilizador autenticado com role Customer (ou System Manager).
- Query apenas `Item Price` com `price_list = "PVR-PT"`, join `Item` ativo.
- Campos: `item_code`, `item_name`, `price_list_rate`, `currency`, `uom`, `image` (do Item).
- Devolve `{ items, total, page, page_size }`.

#### `request_partner_quote(items, notes=None)`

- `@frappe.whitelist()`
- `items`: lista `{ item_code, qty }`.
- Re-lê preços de `PVR-PT` no servidor; ignora qualquer rate enviado pelo cliente.
- Resolve Customer associado ao `frappe.session.user` (Contact → Dynamic Link / padrão ERPNext portal).
- Destinatário: User de `Customer.account_manager`.
- Fallback: constante `PARTNER_QUOTE_FALLBACK_EMAIL` no módulo (configurável depois se necessário); se destinatário e fallback vazios → `frappe.throw` com mensagem clara.
- Envia email (HTML) com tabela item / qty / preço / linha + total + notas + dados do parceiro/user.
- CC ao email do utilizador parceiro quando existir.
- Não cria Quotation, Sales Order nem Issue.

### 4. Segurança

- Guest: sem acesso à página nem às APIs.
- Role: Customer (System Manager para suporte).
- Price list nunca aceita parâmetro externo.
- Validar qty > 0 e item_code existente com preço PVR-PT.

### 5. Erros e edge cases

| Caso | Comportamento |
|------|----------------|
| Sem Customer ligado ao user | Erro amigável ao pedir orçamento |
| `account_manager` vazio | Usar fallback; se falhar, erro |
| Item sem preço PVR-PT no checkout | Falhar o pedido com mensagem listando os itens inválidos |
| Carrinho vazio | Botão desativado |
| Item disabled | Não aparece no catálogo |

## Fora de âmbito

- Criação automática de Quotation / Sales Order.
- Persistência de carrinho no servidor.
- Outras price lists ou override por Customer.default_price_list.
- E-commerce / Website Item do ERPNext.
- Alterações a `frappe` / `erpnext` / `hrms`.

## Critérios de sucesso

1. Parceiro Customer vê **Artigos** na sidebar e acede a `/artigos`.
2. Só preços `PVR-PT` visíveis e usados no email.
3. Pedir orçamento envia email ao Account Manager (ou fallback) e limpa o carrinho.
4. Nenhum documento de venda criado pelo fluxo.
5. Implementação contida em `logicposintegration`.

## Notas de implementação

- Nome canónico da price list: **`PVR-PT`** (não `pvr_pt`).
- Estilo visual: alinhar ao portal existente (`portal_sidebar.css`, tipografia/cores do portal home), sem redesign global.
- Portal Settings: alteração idempotente (patch) para não depender só de UI manual em cada site.
