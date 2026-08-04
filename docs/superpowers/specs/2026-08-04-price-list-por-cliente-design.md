# Design: Price list do catálogo por tipo e moeda do cliente

**Data:** 2026-08-04  
**App:** `logicposintegration`  
**Estado:** aprovado em conversa (abordagem 1)  
**Relacionado:** `2026-07-20-artigos-portal-parceiro-design.md` (substitui a regra de price list fixa `PVR-PT`)

## Objetivo

O utilizador website (ligado a um Customer via Portal User) vê preços da price list correcta consoante o tipo e a moeda do cliente — sem o browser poder escolher a lista.

## Decisões

| Tema | Decisão |
|------|---------|
| Fonte da regra | Servidor: `customer_type` + `default_currency` do Customer |
| Prefixo | `Partnership` → `PVR`; `Company` e `Individual` → `PVP` |
| Sufixo (moeda) | `AOA`→`-AO`; `EUR`→`-PT`; `MZN`→`-MZ` |
| Lista resultante | `{prefixo}{sufixo}` (ex.: `PVP-PT`, `PVR-AO`) |
| Fallback PVR | Se a lista `PVR-*` não existir → usar `PVP-*` da mesma moeda |
| Moeda em falta / desconhecida | Erro claro a pedir configuração de `default_currency` |
| Sem lista nem fallback | Erro com o nome da lista em falta |
| Cliente pode enviar `price_list`? | Não — resolução só no servidor |
| Onde implementar | Só `logicposintegration` |
| Fora de scope | Criar Price Lists no ERP; gravar `Customer.default_price_list` |

## Mapeamento

| customer_type | prefixo |
|---------------|---------|
| Partnership | PVR |
| Company | PVP |
| Individual | PVP |

| default_currency | sufixo |
|------------------|--------|
| AOA | -AO |
| EUR | -PT |
| MZN | -MZ |

Exemplos: Company+EUR → `PVP-PT`; Partnership+EUR → `PVR-PT`; Partnership+AOA sem `PVR-AO` → `PVP-AO`.

## Arquitetura

```
Website User
    │
    ├─ Portal User → Customer
    │
    ├─ resolve_partner_price_list(customer)
    │         ├─ customer_type → prefixo (PVR|PVP)
    │         ├─ default_currency → sufixo (-AO|-PT|-MZ)
    │         └─ se PVR em falta → fallback PVP mesma moeda
    │
    ├─ get_partner_articles → Item Price WHERE price_list = resolvida
    │         └─ response inclui price_list efectiva
    │
    └─ request_partner_quote → revalida rates na lista resolvida + email
```

## Componentes

### 1. `partner_articles.py`

- Remover uso de constante fixa como única lista (`PARTNER_PRICE_LIST = "PVR-PT"`).
- Constantes de mapa: prefixos / sufixos de moeda.
- `resolve_partner_price_list(customer: str) -> str`
- `get_partner_customer()` já existente; usar antes de listar e no checkout.
- `_count_active_partner_prices` / `_list_active_partner_prices` / `_load_server_lines` recebem `price_list` resolvida.
- `get_partner_articles` devolve `price_list` na resposta.
- Mensagens de erro e email usam o nome da lista efectiva (não “PVR-PT” hardcoded).

### 2. UI

- `artigos.html`, `artigos.py`, texto do portal: subtítulo deixa de ser fixo “PVR-PT”.
- JS actualiza o subtítulo com `price_list` devolvida pela API.

### 3. Testes (`test_partner_articles.py`)

- Company + EUR → catálogo em `PVP-PT` (ajustar fixtures: hoje o teste assume PVR-PT com customer Company — alinhar dados).
- Partnership + EUR → `PVR-PT`.
- Partnership + AOA sem `PVR-AO` → fallback `PVP-AO`.
- Moeda inválida → throw.
- Quote continua a ignorar `rate` enviado pelo cliente.

## Tratamento de erros

| Caso | Comportamento |
|------|----------------|
| Guest / sem role Customer | PermissionError (igual ao actual) |
| Sem Customer via Portal User | Erro existente |
| `default_currency` vazio ou fora do mapa | Throw a pedir configuração |
| Price List (e fallback) inexistente | Throw com nome da lista |
| Item sem preço na lista no checkout | Throw listando item_codes |

## Critérios de sucesso

1. Company/Individual com EUR vê `PVP-PT`; Partnership com EUR vê `PVR-PT`.
2. Partnership AOA/MZN sem PVR correspondente usa PVP da mesma moeda.
3. Checkout e email usam a mesma lista que o catálogo.
4. Browser não controla a price list.
5. Textes cobrem resolução, fallback e anti-tampering.

## Fora de scope

- Cadastrar `PVR-AO` / `PVR-MZ` no ERP (feito manualmente depois).
- Sincronizar `Customer.default_price_list`.
- Conversão cambial entre listas.
