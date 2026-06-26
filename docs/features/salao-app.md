# Feature: SalaoApp — implementação inicial completa

Status: ✅ DONE — 2026-05-14 (ondas 1–6 concluídas; pendente apenas execução do `scripts/baixar_vendors.py` pelo usuário)

## Resumo
Implementar do zero o SalaoApp conforme `implementação.md` (raiz). Sistema local single-user de gestão de salão: FastAPI + SQLModel + SQLite + Jinja2 + HTMX/Alpine/Tailwind via CDN. Sem build step, sem auth.

## Fonte da verdade
O documento `implementação.md` na raiz **é o contrato completo**. Todos os agentes devem lê-lo antes de começar e seguir literalmente:
- Estrutura de arquivos (seção 2)
- Stack e requirements (seção 3)
- Banco/sessão (seção 4)
- Modelos (seção 5)
- Layout/paleta (seção 6)
- CRUD pattern (seção 7)
- Agendamentos (seção 8)
- Padrões transversais (seção 9)
- Critério de aceite (seção 12)

## Impacto estrutural
Projeto novo. Cria pasta `app/` com toda a estrutura listada na seção 2.

## Plano de delegação (ondas)

### Onda 1 — Bootstrap + Auth (sequencial, bloqueia tudo)
Agente: **backend-architect** (papel "Agente 1 — Bootstrap" da seção 11) + escopo extra da feature de autenticação (ver `auth-single-user.md`).
Entrega: `requirements.txt`, `app/__init__.py`, `app/main.py`, `app/database.py`, `app/templating.py`, `app/templates/base.html`, `app/templates/home.html`, **mais** `app/models/usuario.py`, `app/routers/auth.py`, `app/security.py` (helpers de hash/sessão/dependency `requer_login`), `app/templates/base_auth.html`, `app/templates/auth/login.html`, `app/templates/auth/setup.html`.
**Importante:** `base.html` deve incluir os dois handlers HTMX globais (seção 6 e 9). Paleta exata da seção 6. Sidebar de `base.html` ganha botão "Sair" no rodapé (POST /logout), grudado no fim via `mt-auto` (sidebar como flex-column h-full). `main.py` registra `SessionMiddleware` e aplica `Depends(requer_login)` nos routers protegidos.

### Onda 2 — CRUDs simples (paralelo: clientes, profissionais, serviços)
Três agentes **backend-architect** em paralelo. Cada um entrega seu model + router + 2 templates conforme seção 7. Como toda a UI é Jinja SSR e os templates são simples, este agente também escreve os templates HTML (cooperando com o estilo já estabelecido em `base.html`).

Cada delegação inclui: regex de validação, mensagens literais, helpers locais, soft-delete, ordenação por nome.

### Onda 3 — Agendamentos backend
Agente: **backend-architect** (papel "Agente 5"). Entrega `app/models/agendamento.py` (3 tabelas) e `app/routers/agendamentos.py` com toda a lógica: `_duracao_efetiva`, `_conflita_para_profissional`, `_substitui_links`, `_contexto_form`, validações da seção 8.5, rotas da seção 8.4.

### Onda 4 — Agendamentos frontend
Agente: **frontend-developer** (papel "Agente 6"). Entrega `lista.html` (calendário), `_form_modal.html`, `_card.html`, `form_edit.html` conforme seção 8.7–8.10. Drag-and-drop SortableJS, multi-selects Alpine, modal único.

Precisa do **contrato de campos do form** já fixado na Onda 3. O contrato está literalmente na seção 8.8 do spec (nomes dos inputs: `data`, `hora`, `profissional_ids`, `servico_ids`, `cliente_id`, `duracao_override`, `observacoes`).

### Onda 5 — Auditoria (paralelo)
- **security-auditor**: revisar validação de input, SQL injection (SQLModel mitiga, mas conferir helpers), XSS em templates (autoescape do Jinja por padrão).
- **code-reviewer**: revisar consistência com o spec, naming, duplicação, conformidade com padrões transversais (seção 9).

### Onda 6 — Correções (se necessário)
Delegar de volta ao agente original conforme achados.

## Critério de aceite
Literalmente a seção 12 do `implementação.md`.

## Riscos conhecidos
- HTMX `htmx:beforeSwap` para 4xx é fácil de esquecer — auditar.
- Alpine `initTree` após swap também.
- `check_same_thread=False` no engine SQLite.
- `_substitui_links` precisa de `flush()` entre delete e insert.
- Itens inativos vinculados não podem sumir do form (seção 8.3 final).
