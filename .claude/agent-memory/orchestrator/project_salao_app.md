---
name: project-salao-app
description: SalaoApp — sistema local single-user de gestão de salão (FastAPI+SQLModel+SQLite+Jinja+HTMX/Alpine/Tailwind)
metadata:
  type: project
---

App local da dona de salão. Roda em `localhost:8000`, single-user com senha (bcrypt+sessão starlette), dados em `salao.db` SQLite na raiz. Stack sem build step (tudo via CDN ou vendor local). Idioma português; código snake_case.

**Why:** Pedido explícito do usuário (ti@kodexexpress.com) para implementar conforme `implementação.md` na raiz. Auth single-user adicionada via pedido posterior, registrada em `docs/features/auth-single-user.md` (revoga decisão "sem login" da seção 1 do spec).

**How to apply:**
- Spec é `implementação.md` na raiz — fonte da verdade técnica.
- Padrões transversais críticos (seção 9 do spec): rotas síncronas (`def`), form-encoded POSTs, 303 redirect após mutação não-HTMX, 204+HX-Refresh para HTMX que precisa reload total, 400+re-render preservando input em erro. Soft-delete em Cliente/Profissional/Serviço; hard-delete só em Agendamento.
- Inativos vinculados a agendamentos não somem dos forms (seção 8.3 final) — eles voltam no contexto marcados como inativo.
- **Regra adicional ao spec**: agendamento exige pelo menos 1 profissional **ativo** vinculado; desativação de profissional bloqueada se ele é único ativo em algum agendamento. Profissional inativo não tem coluna no calendário; blocos com inativo escurecidos via `opacity-60 grayscale` na coluna dos ativos.

**Estrutura de delegação que funcionou:**
Onda 1 (bootstrap+auth) → Onda 2 (3 CRUDs paralelos: clientes/profissionais/servicos) → Onda 3 (agendamentos backend) → Onda 4 (agendamentos frontend) → Onda 5 (security-auditor‖code-reviewer) → Onda 6 (correções backend‖frontend).

**Débitos técnicos registrados:**
- Tailwind via CDN/vendor JIT no browser tem warning de produção — aceitável para single-user local.
- Validação anti-DoS: bcrypt rounds default 12; senha mínima 6 chars; sem rate-limit em /login (aceitável para localhost).
- `.secret_key` no disco é equivalente a "chave-mestra" da sessão — documentado em [[auth-single-user]].

Ver: `docs/features/salao-app.md`, `docs/features/auth-single-user.md`, [[alpine-dispatch-precisa-de-escopo]].
