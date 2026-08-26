# Relatório de trabalho — Portal, projectos e satisfação

**Destinatários:** Direcção  
**Período:** 3 de Julho a 21 de Agosto de 2026  
**Autor:** Hailes Mauricio  
**Formato:** revisão Scrum (o que foi planeado, o que foi entregue, que valor gera)

---

## 1. Resumo executivo

Neste período (cerca de **sete semanas**, **quatro sprints**) o trabalho concentrou-se em tornar o sistema mais útil para **parceiros**, **clientes** e **equipas internas** — sem depender de alterações pesadas no núcleo da plataforma.

Em linguagem simples, o que passou a existir:

1. **Parceiros** consultam o catálogo de artigos no portal, vêem o **preço correcto** (consoante o tipo de cliente e a moeda) e pedem orçamento por email ao gestor de conta.
2. **Clientes** acompanham melhor **encomendas** (detalhe, impostos, comentários) e **projectos/tarefas** (calendário, gráfico de planeamento em português, lista no portal).
3. A empresa passa a **medir satisfação** quando um projecto ou uma fase importante é concluída: o cliente recebe um inquérito por email, responde no portal, e a equipa vê resultados no Desk (incluindo indicadores de taxa de resposta e pontuação média).
4. As **propostas comerciais** geradas pelo sistema passam a ter **controlo de versão**, reduzindo o risco de enviar um documento desactualizado.

**Nota sobre o repositório Frappe:** no período não houve alterações. Toda a evolução de produto ficou na aplicação própria (`logicposintegration`) e, pontualmente, no ERPNext (catálogo Google Sheets e campos de cliente nas tarefas). Isto reduz o custo e o risco nas próximas actualizações de versão.

---

## 2. Números do período (visão de gestão)

| Indicador | Valor |
|-----------|--------|
| Duração | 3 Jul – 21 Ago 2026 (~7 semanas) |
| Sprints | 4 (ciclos de duas semanas; o último ainda em curso à data do relatório) |
| Entregas de produto (incrementos visíveis) | 5 temas principais |
| Commits no período | 26 (24 na app própria, 2 no ERPNext, 0 no Frappe) |
| Repositórios tocados | `logicposintegration` (principal) e `erpnext` (pontual) |

Estes números servem para **ritmo e concentração do esforço**, não para medir qualidade. A qualidade mede-se pelo que o utilizador consegue fazer (secção 3) e pelo facto de as regras de preço e de inquérito terem testes automáticos associados.

---

## 3. Backlog entregue — temas (épicos)

Cada tema abaixo corresponde a um **objectivo de negócio**. As user stories estão escritas do ponto de vista de quem usa o sistema.

### Épico A — Catálogo e orçamentos no portal de parceiros

**Objectivo:** o parceiro deixa de depender de um PDF ou de um email genérico para ver artigos e pedir preço.

| Como… | Quero… | Para… |
|--------|--------|--------|
| Parceiro (cliente no portal) | ver uma secção **Artigos** no menu | encontrar o catálogo sem pedir à equipa comercial |
| Parceiro | pesquisar artigos e montar um pedido | enviar um orçamento ao meu gestor de conta |
| Empresa | que o preço mostrado seja o da lista correcta | não vender com PVP a quem deve ter PVR, nem misturar moedas (euro, kwanza, metical) |
| Empresa | que o pedido de orçamento **não crie** encomenda automática | o comercial validar antes de formalizar a venda |

**O que ficou pronto**

- Menu **Artigos** no portal, com catálogo em cartões, pesquisa e “carrinho” para montar o pedido.
- Pedido de orçamento por **email ao Account Manager** (com cópia ao parceiro). Não cria encomenda nem cotação no ERP — o comercial mantém o controlo.
- Preços calculados **no servidor**, consoante:
  - tipo de cliente: **PVR** para parcerias, **PVP** para empresas e particulares;
  - moeda: **-PT** (euro), **-AO** (kwanza), **-MZ** (metical).
- Se a lista de parceiro (PVR) ainda não existir para aquele país, o sistema usa a lista PVP da **mesma moeda**, em vez de mostrar um preço errado ou ficar em branco.
- O parceiro **não consegue** escolher outra lista de preços no browser — evita fraude ou engano.

**Valor para a Direcção:** canal de self-service comercial, menos idas e voltas, preços alinhados com a política comercial por mercado (PT / AO / MZ).

---

### Épico B — Encomendas no portal (clareza para o cliente)

**Objectivo:** o cliente perceber o que encomendou, quanto paga de imposto, e poder comentar sem telefonar.

| Como… | Quero… | Para… |
|--------|--------|--------|
| Cliente no portal | abrir o **detalhe da encomenda** | confirmar artigos, totais e impostos |
| Cliente e equipa | **comentar** na própria encomenda | esclarecer dúvidas no sítio certo |

**O que ficou pronto**

- Página de detalhe da encomenda no portal.
- Visualização de impostos.
- Zona de comentários partilhada.

**Valor para a Direcção:** menos pedidos repetidos ao suporte; histórico da conversa fica no documento.

---

### Épico C — Projectos e tarefas (equipa interna + cliente)

**Objectivo:** planear melhor o trabalho e dar visibilidade ao cliente, sem o cliente alterar tarefas.

| Como… | Quero… | Para… |
|--------|--------|--------|
| Gestor de projecto | ver tarefas em **calendário** e em **gráfico de planeamento (Gantt)** | gerir prazos e responsáveis de relance |
| Equipa / cliente no portal | ver o Gantt **em português** | perceber estados e etiquetas sem barreira de idioma |
| Cliente no portal | ver as **tarefas do meu projecto** (incluindo tarefas “órfãs” ligadas ao meu cliente) | acompanhar o que está a ser feito |
| Empresa | que o cliente **só consulte e comente**, sem criar ou editar tarefas | proteger o plano de trabalho |
| Equipa | ter **cliente e contacto** na tarefa, e datas de início/fim obrigatórias | não avançar trabalho sem dono nem prazo |

**O que ficou pronto**

- Calendário de tarefas no Desk (com responsáveis visíveis no evento).
- Gantt no portal traduzido (estados e etiquetas em português).
- Vista Gantt também no Desk (lista de tarefas).
- Portal: listagem de tarefas do cliente; contacto do cliente visível.
- Tarefas passam a exigir datas previstas de início e fim.
- Utilizadores do portal **não editam** tarefas — apenas vêem e comentam.

**Valor para a Direcção:** mais disciplina de planeamento; o cliente acompanha o projecto sem pôr em risco o plano interno.

---

### Épico D — Inquérito de satisfação (fecho de projecto)

**Objectivo:** quando um projecto (ou uma fase importante) termina, perguntar ao cliente se ficou satisfeito — e guardar a resposta para a Direcção analisar.

| Como… | Quero… | Para… |
|--------|--------|--------|
| Gestor, ao marcar o projecto como **Concluído** | ser perguntado se envio o inquérito | não esquecer o pedido de feedback |
| Gestor | confirmar / corrigir o **email do destinatário** antes de enviar | o inquérito chegar à pessoa certa |
| Cliente | responder pelo **link no email** ou pelo **menu no portal** | ser rápido e sem instalação de nada |
| Direcção / qualidade | ver respostas, pontuação média e taxa de resposta | saber se estamos a melhorar o serviço |
| Empresa | **um único preenchimento** por projecto | não distorcer indicadores com respostas duplicadas |

**O que ficou pronto**

- Modelos de inquérito configuráveis (perguntas de escala 0–10, texto livre e escolha).
- Ao concluir um **Projecto** (ou uma **tarefa de grupo**, quando faz sentido), aparece um diálogo: enviar ou não. Recusar **não bloqueia** o fecho do projecto.
- Email com link único; o cliente também encontra **Inquéritos** no portal.
- Respostas ficam ligadas ao cliente e ao projecto/tarefa.
- Área no Desk (sob Projectos) para gerir inquéritos e modelos, em português.
- Painel com indicadores: total, enviados, respondidos, pendentes, pontuação média, taxa de resposta, evolução no tempo e por cliente/estado.
- Email de convite passou a usar um modelo profissional (mais fácil de manter e de alinhar com a imagem da empresa).

**Regras de negócio relevantes para a Direcção**

- Não se envia automaticamente se o projecto fechar “sozinho” (por percentagem de tarefas). Só quando alguém conclui no ecrã — evita spam acidental.
- Não se volta a perguntar se já existe inquérito enviado ou respondido para o mesmo projecto.
- O cliente não acede ao back-office; só ao portal / link.

**Valor para a Direcção:** primeira base sistemática de NPS/satisfação por projecto, com dono do processo (quem fecha o projecto) e indicadores prontos a acompanhar.

---

### Épico E — Propostas comerciais e catálogo interno

**Objectivo:** documentos de venda mais fiáveis e sincronização de catálogo mais estável.

| Como… | Quero… | Para… |
|--------|--------|--------|
| Comercial | gerar a proposta com **versão** e validações | não enviar um PDF desactualizado ou incompleto |
| Equipa de catálogo | que a ligação ao **Google Sheets** aguente falhas temporárias | o catálogo não “partir” quando a Google limita pedidos |

**O que ficou pronto**

- Geração de propostas com **versionamento** e validações no ecrã da cotação.
- Sincronização Google Sheets mais robusta (repete tentativas quando a Google recusa por excesso de pedidos; trabalha sobre uma “fotografia” dos dados para não misturar estados).

**Valor para a Direcção:** menos risco comercial no documento que o cliente assina; menos interrupções na actualização do catálogo.

---

## 4. Revisão por sprint

Sprints de **duas semanas**. O Sprint 4 estava em curso à data deste relatório (21 de Agosto).

### Sprint 1 — 3 a 16 de Julho  
**Meta do sprint:** melhorar a experiência de projectos, propostas e encomendas.

| Entrega | Para quem | Estado |
|---------|-----------|--------|
| Gantt do portal em português | Equipas e clientes | Feito |
| Calendário de tarefas | Gestores de projecto | Feito |
| Versão e validação nas propostas | Comercial | Feito |
| Detalhe de encomenda + impostos + comentários | Cliente no portal | Feito |
| Sincronização Google Sheets mais estável | Operações / catálogo | Feito |

**Incremento:** o portal e o Desk passam a ser usáveis no dia-a-dia de projectos e de vendas, em português e com documentos mais claros.

---

### Sprint 2 — 17 a 30 de Julho  
**Meta do sprint:** abrir o catálogo aos parceiros.

| Entrega | Para quem | Estado |
|---------|-----------|--------|
| Secção **Artigos** no portal (catálogo + pedido de orçamento) | Parceiros | Feito |

**Incremento:** o parceiro deixa de estar “cego” em relação ao catálogo. Pedido de orçamento chega ao gestor de conta por email, sem criar venda automática.

*Nota:* este sprint teve uma entrega única, mas de dimensão elevada (página nova, regras de acesso, email comercial).

---

### Sprint 3 — 31 de Julho a 13 de Agosto  
**Meta do sprint:** preços certos por mercado **e** inquérito de satisfação no fecho do projecto.

| Entrega | Para quem | Estado |
|---------|-----------|--------|
| Preço PVP/PVR conforme tipo de cliente e moeda (PT, AO, MZ) | Parceiros / comercial | Feito |
| Símbolo de moeda e textos mais claros no catálogo | Parceiros | Feito |
| Vista Gantt no Desk | Gestores | Feito |
| Inquérito de satisfação (modelo, envio, portal, email, área no Desk, traduções) | Qualidade + cliente | Feito |

**Incremento:** política comercial de preços aplicada automaticamente; processo de satisfação no fecho de projecto, ponta a ponta.

Este foi o sprint de **maior volume** (cerca de dois terços dos commits do período), o que é coerente com ter saído um produto novo (inquéritos) mais o fecho das regras de preço.

---

### Sprint 4 — 14 a 21 de Agosto (em curso à data do relatório)  
**Meta do sprint:** tornar o inquérito **analisável** pela Direcção e as tarefas **visíveis e seguras** no portal.

| Entrega | Para quem | Estado |
|---------|-----------|--------|
| Email do inquérito em modelo dedicado | Comunicação / qualidade | Feito |
| Painel de indicadores de satisfação | Direcção / qualidade | Feito |
| Tarefas no portal (lista, contacto, permissões de só leitura) | Cliente | Feito |
| Cliente, contacto e datas obrigatórias na tarefa | Gestores de projecto | Feito |

**Incremento:** a satisfação deixa de ser “só um email” e passa a ter números; o cliente vê o trabalho sem o poder alterar.

---

## 5. O que isto muda no negócio (impacto)

| Área | Antes (situação típica) | Depois |
|------|-------------------------|--------|
| Venda a parceiros | Catálogo e preço pediam-se à equipa | Parceiro consulta e pede orçamento sozinho, com a lista certa |
| Preços multi-mercado | Risco de mostrar PVR-PT a todos | PVP vs PVR e sufixo PT / AO / MZ, com fallback seguro |
| Encomendas | Pouca transparência no portal | Detalhe, impostos e comentários no próprio documento |
| Projectos | Planeamento e idioma inconsistentes | Calendário, Gantt em PT, datas obrigatórias, cliente na tarefa |
| Qualidade de serviço | Feedback informal / irregular | Inquérito no fecho, respostas guardadas, indicadores no Desk |
| Propostas | Risco de versão errada | Versão e validação na geração do PDF |
| Actualizações futuras | Lógica espalhada pelo núcleo | Quase tudo na app própria — actualizações de versão mais baratas |

---

## 6. Qualidade, riscos e decisões conscientes

**O que foi feito para reduzir risco**

- Regras de preço e de inquérito têm **testes automáticos** (o sistema verifica sozinho os casos principais: tipo de cliente, moeda, fallback, um único preenchimento do inquérito, etc.).
- O cliente do portal **não altera tarefas**.
- O preço **não é escolhido no browser** — o servidor decide.
- O inquérito **não bloqueia** o fecho do projecto se a pessoa recusar enviar.

**O que ainda não está neste ciclo (e foi decisão, não esquecimento)**

- O pedido de orçamento do parceiro **não cria** cotação/encomenda no ERP — o comercial valida.
- O inquérito **não dispara sozinho** se o projecto fechar por percentagem de tarefas.
- Não há construtor visual avançado de inquéritos (tipo “arrastar perguntas”); os modelos configuram-se no Desk de forma simples.
- As listas de preços em falta (ex.: PVR-AO) **não são criadas automaticamente** — continuam a ser cadastro comercial.

**Frappe (núcleo da plataforma):** zero alterações neste período. É uma boa notícia para a Direcção: menos conflito quando actualizarmos a plataforma.

**ERPNext:** só duas alterações pontuais — robustez do catálogo Google Sheets (3 Jul) e campos de cliente / datas nas tarefas (18 Ago). A segunda foi necessária para o portal e o inquérito saberem **a quem pertence a tarefa**; não cabia só na app própria porque o formulário de Tarefa vive no ERPNext.

---

## 7. Distribuição do esforço por repositório

| Repositório | Papel | Trabalho neste período |
|-------------|--------|-------------------------|
| **logicposintegration** | Aplicação da empresa (portal, inquéritos, catálogo parceiro, propostas) | Quase todo o produto (24 entregas/commits) |
| **erpnext** | ERP (projectos, catálogo interno) | 2 ajustes pontuais |
| **frappe** | Motor da plataforma | Nenhum |

Recomendação para a Direcção: **manter esta disciplina** — produto na app própria, núcleo só quando for inevitável. É o que protege o investimento nas próximas actualizações.

---

## 8. Como ler este relatório em reunião (10 minutos)

1. **Minuto 1–2:** resumo executivo (secção 1) — quatro ganhos: catálogo parceiro, encomendas, projectos, satisfação.  
2. **Minuto 3–6:** épicos A e D (catálogo/preços e inquérito) — são os de maior impacto comercial e de qualidade.  
3. **Minuto 7–8:** sprints 3 e 4 — onde o volume e o “produto novo” se concentraram.  
4. **Minuto 9–10:** secção 6 — o que **não** foi feito de propósito, e a nota sobre Frappe/ERPNext.

---

## 9. Glossário breve (para não-técnicos)

| Termo | Significado aqui |
|-------|------------------|
| **Portal** | Área web onde o cliente/parceiro entra com login (não é o back-office da equipa) |
| **Desk** | Back-office usado pela equipa interna |
| **Sprint** | Ciclo de duas semanas com uma meta clara e um incremento utilizável no fim |
| **Épico** | Tema grande de produto, composto por várias histórias |
| **Incremento** | O que o utilizador já consegue fazer de novo no fim do sprint |
| **PVP / PVR** | Listas de preço (público vs. revenda/parceiro) |
| **Inquérito de satisfação** | Questionário enviado ao cliente no fecho do projecto ou de uma fase |

---

*Documento gerado a partir do histórico de trabalho (commits) de 3 de Julho a 21 de Agosto de 2026 nos repositórios `logicposintegration`, `erpnext` e `frappe`. Não inclui trabalho não registado nesses repositórios.*
