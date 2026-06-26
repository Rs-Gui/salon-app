---
name: feedback-script-no-head-documentbody
description: Script inline no `<head>` que chama `document.body.addEventListener` quebra silenciosamente — `document.body` é null antes do parse do body
metadata:
  type: feedback
---

`<script>` inline no `<head>` (sem `defer`) roda DURANTE o parse, antes do `<body>` ser parseado. `document.body` é `null` nesse momento. Qualquer chamada tipo `document.body.addEventListener(...)` lança `TypeError` e **PARA TODO O RESTO DO SCRIPT** — definições subsequentes (`window.xxx`, listeners, stores) nunca executam.

**Why:** Bug raiz no SalaoApp `base.html`. Causa encadeada: handlers HTMX (no topo do script) chamavam `document.body.addEventListener` → exceção → `window.multiselect` (definido depois no mesmo script) nunca era criado → Alpine processava `x-data='multiselect(...)'` e gritava "multiselect is not defined" no modal de agendamentos. Levou 3 ondas de "correções de Alpine" pra achar, porque os erros aparentes apontavam pra Alpine, não pra ordem de execução.

**Como detectar:**
- Console mostra `Cannot read properties of null (reading 'addEventListener')` na primeira chamada do script
- Erros subsequentes de "X is not defined" para qualquer coisa definida APÓS a chamada problemática no mesmo script
- Hard refresh não muda nada (não é cache)

**Como corrigir:**
- Para listeners de eventos que bubble (HTMX, custom events): trocar `document.body.addEventListener` por `document.addEventListener` — eventos bubble até o document e são capturados ali
- Para casos onde precisa do body literalmente: envolver em `DOMContentLoaded`, ou mover o `<script>` pro fim do `<body>`, ou adicionar `defer` na tag (mas inline `<script>` não suporta `defer`)

**Como prevenir:**
- Em scripts no `<head>`, NUNCA acessar `document.body`, `document.querySelector('body ...')`, ou qualquer DOM do body sem guard
- `document` é seguro desde o início do parse
- Eventos custom/HTMX bubble até `document`, então listener no document = listener no body para fins práticos
