# Design: Inquérito de Satisfação (Project / Task grupo)

**Data:** 2026-08-10  
**App:** `logicposintegration`  
**Estado:** aprovado em conversa (abordagem 1)  
**Referência UI:** inquérito existente (pills de assunto + escala 0–10 + ENVIAR); portal deve ficar igual ou melhor

## Objetivo

Quando um utilizador do Desk marca um **Project** como Concluído (`Completed`), ou uma **Task** com **É Grupo** activa (em condições abaixo), mostrar um Dialog a perguntar se pretende enviar email ao cliente com link para preencher um inquérito de satisfação no portal. As respostas ficam no Desk para análise. O cliente acede por **token no email** e/ou **menu no portal** (login).

## Decisões

| Tema | Decisão |
|------|---------|
| Onde implementar | Só `logicposintegration` (DocTypes, hooks, portal, email) |
| Dialog | Confirmar/editar destinatário antes de enviar (opção B) |
| Modelo de perguntas | Configurável no Desk (template + child questions) |
| Tipos de pergunta (v1) | `Scale` (ex. 0–10), `Text`, `Choice` (pills; necessário para UI tipo referência) |
| Acesso portal | Token único no email **e** menu portal para Customer autenticado |
| Identidade | Identificado: cliente vê contexto Project/Task; Desk guarda Customer, Project/Task, `submitted_by` se login |
| Trigger Project | Status → `Completed` via UI do form |
| Trigger Task | `is_group = 1` e status → `Completed`; Task **sem** Project, **ou** Task **com** Project sem inquérito ativo desse Project |
| Deduplicação | Não criar/perguntar de novo se já existir Inquérito `Sent` ou `Submitted` para o mesmo Project (ou para a mesma Task órfã) |
| Auto-complete Project | Se Project passa a Completed sem interação UI (ex. % automático), **não** enviar email automático na v1 |
| Se user recusar no Dialog | Não criar documento de inquérito; conclusão do Project/Task não é bloqueada |
| Resolução de email | Portal Users do Customer → se nenhum, Contact principal / email do Contact; Dialog permite editar |
| Relatório | v1: lista + form no Desk com filtros; relatório de médias Scale opcional no mesmo ciclo se couber |

## Fora de scope (v1)

- Envio automático quando o Project fecha por percentagem/tarefas sem user no form
- Builder visual avançado de inquéritos (drag-and-drop)
- Anonimato real (sem ligação a Customer/Project)
- Alterações a `frappe` / `erpnext` / `hrms` core
- Reutilizar Quality Feedback (ERPNext) ou produto comercial `q.track.survey`

## Arquitetura

```
Desk user (Project/Task form)
    │  status → Completed (+ regras Task grupo)
    ▼
doctype_js Dialog
    │  resolve recipients (Portal User → Contact)
    │  user confirma/edita email → Sim
    ▼
whitelisted API (logicposintegration)
    │  cria Inquérito de Satisfação (token, snapshot perguntas)
    │  envia email com /satisfacao/{token}
    ▼
Cliente
    ├─ email link (token) ──────────────┐
    └─ portal menu Inquéritos (login) ──┤
                                        ▼
                              formulário portal
                                        │
                                        ▼
                              status Submitted + respostas no Desk
```

## Modelo de dados

### 1. Modelo de Inquérito de Satisfação

Template configurável.

| Campo | Tipo | Notas |
|-------|------|--------|
| `title` | Data | Nome do modelo |
| `is_active` | Check | Só modelos ativos são usados no envio |
| `description` | Small Text | Opcional |

Child **Pergunta do Modelo de Inquérito**:

| Campo | Tipo | Notas |
|-------|------|--------|
| `question` | Small Text | Texto da pergunta |
| `question_type` | Select | `Scale` \| `Text` \| `Choice` |
| `scale_min` / `scale_max` | Int | Default 0 / 10 |
| `options` | Text | Uma opção por linha (`Choice`) |
| `is_mandatory` | Check | |

### 2. Inquérito de Satisfação

Instância enviada / preenchida.

| Campo | Tipo | Notas |
|-------|------|--------|
| `survey_template` | Link | Modelo usado |
| `customer` | Link | Obrigatório quando conhecido via Project/Task |
| `project` | Link | Opcional |
| `task` | Link | Opcional; Task grupo (órfã ou fase) |
| `recipient_email` | Data | Email efetivamente usado |
| `recipient_user` | Link (User) | Se resolvido a partir de Portal User |
| `access_token` | Data | Único; indexado |
| `status` | Select | `Draft` \| `Sent` \| `Submitted` \| `Cancelled` |
| `sent_on` / `submitted_on` | Datetime | |
| `submitted_by` | Link (User) | Se sessão autenticada no submit |

Child **Resposta do Inquérito** (snapshot no envio + valores no submit):

| Campo | Tipo | Notas |
|-------|------|--------|
| `question` | Small Text | Cópia no momento do envio |
| `question_type` | Select | |
| `scale_min` / `scale_max` | Int | |
| `options` | Text | Snapshot Choice |
| `answer_scale` | Int | |
| `answer_text` | Text | |
| `answer_choice` | Data | |

**Permissões Desk:** System Manager / role de Projects (ler e analisar). Cliente sem acesso Desk.

**Regra de unicidade lógica:** no máximo um inquérito `Sent`/`Submitted` por Project; no máximo um por Task órfã (`task` preenchido, `project` vazio).

## Fluxo Desk (Dialog)

1. Em `doctype_js` de Project e Task, detetar transição para `Completed` (após regras de elegibilidade).
2. Abrir Dialog: título a convidar envio; listar/sugerir emails; campo editável.
3. **Enviar:** API cria doc (`Sent`), gera token, copia perguntas do modelo ativo padrão (ou único ativo), envia email.
4. **Não / fechar:** nada é criado; o documento Project/Task grava normalmente.
5. Modelo a usar: o Modelo de Inquérito com `is_active`; se houver vários, usar o marcado como default (campo `is_default` no modelo) ou o mais recente ativo — **regra explícita:** um único modelo com `is_default=1` ativo; se nenhum default, o único ativo; se ambíguo, erro claro no Dialog.

## Resolução de destinatário

Ordem:

1. `Portal User` do `Customer` do Project (ou Customer ligado à Task, se existir); preferir users enabled com email.
2. Se vazio: Contact principal do Customer (`customer_primary_contact` / default contact) → `email_id`.
3. Dialog mostra candidatos e permite override manual do email.

Se não houver Customer (Task órfã sem cliente): Dialog exige email manual; `customer` pode ficar vazio até se definir regra — **regra explícita:** Task grupo sem Project e sem Customer exige email manual; `customer` opcional nesse caso.

## Portal e email

### Email

- Assunto: inquérito de satisfação com referência ao Project ou Task.
- Corpo: texto curto + link `{site}/satisfacao/{access_token}`.
- Conta de envio: email account padrão Frappe.

### Rotas / menu

- `portal_menu_items`: **Inquéritos** (role Customer) → lista.
- Página lista: inquéritos do Customer do utilizador (`Sent`, `Submitted`).
- Página formulário: `/satisfacao/<token>` (acesso por token) e acesso autenticado ao mesmo doc se pertencer ao Customer.

### Formulário (UX)

- Mostrar contexto: nome do Project ou subject da Task.
- `Choice`: pills (como referência).
- `Scale`: círculos 0–10 (ou min–max do modelo).
- `Text`: textarea.
- Botão ENVIAR; pós-submit: mensagem de sucesso; `status=Submitted`; uma única submissão por token/doc.
- Com login: gravar `submitted_by`.

### Desk análise

- List view + form do Inquérito com child respostas.
- Filtros: Customer, Project, Task, status, datas.

## Componentes (ficheiros previstos)

| Área | Localização prevista |
|------|----------------------|
| DocTypes | `logicposintegration/logicpos_integration/doctype/...` |
| API envio/submit | módulo Python dedicado (ex. `satisfaction_survey.py`) |
| Client scripts | `public/js/project.js`, `public/js/task.js` + `hooks.doctype_js` |
| Portal | `www/satisfacao.py` / templates + CSS alinhado ao portal existente |
| Menu | `hooks.portal_menu_items` + patch se necessário (padrão Artigos) |
| Email template | Email Template DocType fixture ou `frappe.sendmail` com template Jinja na app |
| Testes | testes unitários resolução destinatário, dedupe, submit token |

## Tratamento de erros

| Situação | Comportamento |
|----------|----------------|
| Sem modelo ativo | Dialog informa; não envia |
| Email inválido | Validação no Dialog / API |
| Token inválido / já Submitted | Página portal com mensagem clara |
| User portal sem Customer | Lista vazia / sem acesso a docs de outros |
| Project Completed sem UI | Sem email automático (v1) |

## Critérios de sucesso

1. Ao concluir Project no form, Dialog aparece com email sugerido editável; envio cria doc + email.
2. Task grupo sem Project: mesmo fluxo; Task com Project só se ainda não houver inquérito do Project.
3. Cliente preenche via link e/ou menu; respostas visíveis no Desk ligadas ao contexto.
4. Segunda submissão pelo mesmo token rejeitada.
5. Nenhuma alteração necessária em apps core para a v1.
