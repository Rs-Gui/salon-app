---
name: alpine-dispatch-precisa-de-escopo
description: Bug recorrente — Alpine `@click="$dispatch(...)"` em elementos sem ancestral x-data é silenciosamente ignorado
metadata:
  type: feedback
---

Em templates que usam Alpine.js + HTMX, **diretivas Alpine (`@click`, `x-show`, `x-data`...) só funcionam em elementos cujo ancestral tem `x-data`**. Quando o modal Alpine é um irmão no DOM (não ancestral) dos elementos clicáveis, `@click="$dispatch('open-modal')"` é ignorado silenciosamente — HTMX continua disparando seu `hx-get`, mas o modal nunca abre.

**Why:** Aconteceu no SalaoApp: botão "+ Novo agendamento" e slots do calendário tinham `@click="$dispatch('open-modal')"` mas o `<div x-data>` do modal era irmão, não ancestral. Resultado: clique fazia request HTMX, fragmento ia para `#modal-content` oculto, usuário via "nada acontece".

**How to apply:** Em padrões "elemento clicável dispatcha evento → modal escuta via `@evento.window`", use **`onclick="window.dispatchEvent(new CustomEvent('nome'))"`** (vanilla JS) no disparador em vez de `@click="$dispatch(...)"` Alpine. Vanilla funciona independente de escopo. Alternativa: envolver tudo num único `x-data` ancestral comum, mas o vanilla-dispatch é mais robusto e local.

Sinal de detecção: "clico mas nada acontece" + DOM tem `x-data` e `@evento.window` num lugar e `@click="$dispatch"` em outro — checar ancestralidade.
