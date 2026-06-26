# Feature: Auditoria visual completa do SalaoApp

## Resumo
Levantamento visual de ponta a ponta do app, com diagnóstico + propostas de correção que o usuário aprova antes de qualquer implementação. Drivers do usuário:

- **Sidebar não vai até o final da página** — para arredondamento visual estranho do bloco lateral
- **Scrollbar lateral da agenda está genérico** — quer integrado ao visual bege/stone do calendário
- **Sensação geral de "meio estranho"** — pedido aberto pra ui-designer levantar oportunidades

## Status
🟢 IMPLEMENTAÇÃO validada (escopo B aprovado e aplicado) — 2026-05-15

## Validação pós-implementação (2026-05-15)

Revisor: `ui-designer`. Inspeção de código (sem editar), conferindo cada item do "Escopo aprovado pelo usuário (opção B)" contra os arquivos entregues.

### Status por item

| # | Item | Status | Observação |
|---|------|--------|------------|
| 1 | Sidebar full-height (layout sticky em `base.html`) | Ok | `body` com `h-screen flex flex-col overflow-hidden` (linha 133), wrapper `flex flex-1 min-h-0 overflow-hidden` (139), `aside` com `shrink-0 overflow-y-auto` (140), `main` com `overflow-y-auto` (174). Conforme proposta. |
| 2 | Scrollbar bege (`.scroll-bege`) global + classe aplicada | Ok | `<style>` no `base.html` linhas 14–40 idêntico ao snippet aprovado. Classe aplicada em `aside` (140), `main` (174), wrapper da agenda (`lista.html` 55), modais de exclusão (`_modal_excluir.html` 36), modais de produtos (`produtos/lista.html` 108) e modal de agendamentos (`lista.html` 128). |
| 3 | Header `py-4 shadow-sm shrink-0` | Ok | `base.html` linha 134: `px-6 py-4 ... shadow-sm shrink-0`. Conforme. |
| 4 | Item ativo da sidebar `font-semibold` | Ok | `base.html` linha 153: `font-semibold` no link ativo. |
| 5 | "Excluir permanentemente" desinflado | Ok | `produtos/lista.html` 87 e `profissionais/lista.html` 62: `class="text-red-700 hover:text-red-900"` — `font-semibold underline decoration-dotted underline-offset-2` removido. |
| 6 | Separadores `|` consistentes entre módulos | Ok (opção X — todos usam) | `clientes/lista.html` 51 e `servicos/lista.html` 51: `<span class="text-stone-300" aria-hidden="true">|</span>` entre Editar e Desativar. Coerente com produtos/profissionais. |

### Achados de regressão

Nenhum.

- **Duplo scroll na agenda:** o `main` é `overflow-y-auto`, mas o wrapper da agenda mantém `max-h-[calc(100vh-180px)]` (`lista.html:55`). Em viewport desktop comum (≥800px de altura), o cap do wrapper deixa o conteúdo do main abaixo do limite rolável do main, então só o scroll interno da agenda é exercitado. O `overflow-x-hidden` adicionado ao `<main>` (linha 174) elimina barra horizontal residual. Não observei regressão.
- **Pipe `|` em 2-ações (clientes/serviços):** o `text-stone-300` está suficientemente discreto e o padrão fica natural — não pesa visualmente. Mantém coerência inter-módulos sem custo.

### Quick fixes recomendados

Nenhum bloqueante. Possível refinamento opcional (fora do escopo B): trocar `text-stone-300` do pipe por `text-stone-400` para harmonizar com bege bem-saturado de fundo — atual está OK, é só nuance.

### Veredito final

**Aprovado.** Os 6 itens do escopo B foram aplicados conforme proposta, sem regressões visuais identificadas na leitura do código. Restam Médios/Baixos do diagnóstico para um próximo ciclo se o usuário quiser evoluir.

### Escopo aprovado pelo usuário (opção B)
Apenas itens **Alto** + os dois pedidos explícitos. Médios/Baixos ficam para iteração futura.

Lista a aplicar:
1. Sidebar full-height (layout sticky em `base.html`)
2. Scrollbar bege (`.scroll-bege`) em `base.html` + classe aplicada em sidebar, main, modais e agenda
3. Header com `py-4 shadow-sm shrink-0`
4. Item ativo da sidebar com `font-semibold` (em vez de `font-medium`)
5. "Excluir permanentemente" desinflado — tirar `font-semibold underline decoration-dotted underline-offset-2`; manter apenas `text-red-700 hover:text-red-900`
6. Ações de tabela consistentes — padronizar separadores `|` entre módulos (escolher: ou todos usam ou nenhum usa)

## Escopo do diagnóstico
- Header (logo + texto)
- Sidebar (altura, destaque do item ativo, alinhamento, espaçamento, hover)
- Main area (paddings, contêineres, larguras máximas)
- Tabelas (densidade, cabeçalho, bordas, alternância, alinhamento de ações)
- Forms (espaçamentos, agrupamentos, labels, hierarquia visual)
- Modais (densidade, fechamento, hierarquia)
- Calendário/agenda (toolbar, colunas, blocos, sticky headers, **scrollbar customizada**)
- Tipografia (consistência de tamanhos, pesos, espaçamento entre letras)
- Cores/contrastes (texto sobre bege, badges, estados disabled)
- Microinterações (focus rings, transitions, hover)
- Estados (vazio, erro, loading)
- Responsivo desktop pequeno (sem prioridade mobile — app é desktop local)

## Critérios para o relatório
O `ui-designer` deve entregar UM relatório (atualizando a seção "Diagnóstico" deste arquivo) contendo:
1. **Inventário visual** — o que existe hoje, com referência aos arquivos
2. **Problemas identificados** (priorizados Alto/Médio/Baixo) com:
   - Onde está o problema (arquivo + componente)
   - Por que é problema (princípio violado, inconsistência, etc.)
   - Proposta de correção concreta (classes Tailwind ou ajuste estrutural)
3. **Itens explícitos do usuário** marcados separadamente (sidebar full-height + scrollbar agenda) — solução completa pra cada
4. **Quick wins vs mudanças estruturais** — separar o que é fácil de aplicar do que demanda reorganização

## Plano de delegação
1. **Onda 1 — Diagnóstico** (`ui-designer`): só leitura + relatório, NENHUMA edição de código
2. **Pausa para aprovação do usuário**
3. **Onda 2 — Implementação** (`frontend-developer`): aplica as correções aprovadas
4. **Onda 3 — Validação visual** (`ui-designer` revisa o resultado)

## Crítérios de aceite
- [ ] Relatório de diagnóstico entregue com bullets acionáveis
- [ ] Usuário aprova subconjunto a implementar
- [ ] Pós-implementação: sidebar visualmente integrada até o final, scrollbar da agenda combinada com a paleta, ajustes aprovados aplicados

---

## Diagnóstico

### Inventário visual (estado atual)

- `app/templates/base.html` — body `bg-[#f5efe4]` + `flex flex-col min-h-screen`. Header `bg-[#ebe1ce]` 1 linha (`py-3`). Wrapper `<div class="flex flex-1 min-h-0">` contém `<aside class="w-56 ... h-full flex flex-col">` e `<main class="flex-1 p-6">`. Sidebar tem itens com `border-l-4` (ativo: `border-stone-900`; inativo: `border-transparent`).
- Listas (clientes/profissionais/servicos/produtos): `max-w-5xl mx-auto`, título + botão primário, tabela branca `rounded-lg border border-stone-200` com `thead bg-stone-50`, `tbody` com `border-t` entre linhas, ações alinhadas à direita (`text-right` + `flex justify-end gap-3`).
- Forms CRUD: `max-w-2xl mx-auto`, card branco `p-6`, `space-y-4`, labels `text-sm font-medium text-stone-700 mb-1`, inputs com `focus:ring-2 focus:ring-stone-400` (em uns) ou `focus:border-stone-500` (em outros — inconsistência).
- Calendário (`agendamentos/lista.html`): toolbar inline `flex flex-wrap gap-3`, wrapper `overflow-auto max-h-[calc(100vh-180px)]` envolvendo grid de colunas; header sticky `bg-[#ebe1ce]`; blocos `bg-[#f7efde]` + `border-l-4 border-stone-900`.
- Modais: overlay `bg-stone-900/40` + caixa `bg-[#f5efe4] rounded-lg shadow-xl max-w-2xl`. Botão `×` absoluto top-right (`text-2xl`). Conteúdo `p-6`.

---

### Pedidos explícitos do usuário

#### 1. Sidebar full-height

**Diagnóstico.** Hoje `base.html` é `min-h-screen flex flex-col` com `<div class="flex flex-1 min-h-0">` envolvendo `aside w-56 h-full` + `main flex-1 p-6`. O wrapper só estica até a altura do conteúdo do `main`. Quando o `main` é curto (home, lista vazia), o wrapper colapsa e a sidebar termina no meio da viewport. Quando o `main` é alto (agenda), a sidebar acompanha, mas como tudo rola no body, o usuário perde a navegação ao scrollar.

**Proposta recomendada — sidebar fixa com main rolável (melhor UX para app desktop).**

Trocar o layout para "sidebar sticky + main como única região rolável":

- Em `base.html`, ajustar o `<body>`:
  - de: `class="bg-[#f5efe4] text-stone-900 min-h-screen flex flex-col"`
  - para: `class="bg-[#f5efe4] text-stone-900 h-screen flex flex-col overflow-hidden"`
- Manter o `<header>` como está (altura fixa por `py-3`).
- Wrapper das duas colunas:
  - de: `<div class="flex flex-1 min-h-0">`
  - para: `<div class="flex flex-1 min-h-0 overflow-hidden">`
- Sidebar:
  - de: `<aside class="w-56 bg-[#ebe1ce] border-r border-[#ddd1b8] flex flex-col h-full">`
  - para: `<aside class="w-56 bg-[#ebe1ce] border-r border-[#ddd1b8] flex flex-col shrink-0 overflow-y-auto">`
- Main (passa a ser a única área rolável):
  - de: `<main class="flex-1 p-6">`
  - para: `<main class="flex-1 p-6 overflow-y-auto">`

Resultado: sidebar vai do topo do wrapper até o fim da viewport, sempre visível, sem scroll próprio (a menos que ganhe muitos itens). O scroll vertical fica no `main`. Implicação para a agenda: o `max-h-[calc(100vh-180px)]` continua válido porque a agenda já tem scroll interno; mas como o main agora também rola, o duplo scroll pode incomodar — ver item "Médio" sobre normalizar.

**Alternativa mais conservadora (se não quiser mexer no scroll global).** Apenas garantir que a sidebar estique até o fim da viewport quando o conteúdo for curto:

- body: manter `min-h-screen flex flex-col`
- wrapper: `<div class="flex flex-1 min-h-0">` → `<div class="flex flex-1 min-h-[calc(100vh-57px)]">` (57px = altura do header `py-3` + `h-7` do texto; ajuste se necessário). Ou mais simples: deixe o wrapper natural, mas force `aside` a esticar com `self-stretch` (já é flex-item, `h-full` deveria funcionar — o problema é que `h-full` num filho de flex sem altura definida não estica). Solução robusta: usar `min-h-screen` no wrapper.
- aside: trocar `h-full` por `self-stretch` (redundante em flex) e adicionar `sticky top-[57px] h-[calc(100vh-57px)]` se quiser que ela acompanhe o scroll.

**Recomendo a opção 1 (sidebar sticky + main rolável)** — é o padrão de app desktop, resolve "sidebar até o fim" definitivamente e simplifica raciocínio de scroll.

#### 2. Scrollbar customizada da agenda

CSS pronto pra colar. Adicionar em `base.html` dentro da tag `<style>` existente (linha 11), para reaproveitar em qualquer área rolável (sidebar, main, modais, agenda) — mas escopado por classe `.scroll-bege` para não afetar scrollbars do SO em selects/textareas nativos.

```html
<style>
  [x-cloak]{display:none !important}

  /* Scrollbar bege/stone — aplique a classe .scroll-bege no wrapper rolável */
  .scroll-bege {
    scrollbar-width: thin;                 /* Firefox */
    scrollbar-color: #b8a888 #ebe1ce;      /* thumb / track — Firefox */
  }
  .scroll-bege::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }
  .scroll-bege::-webkit-scrollbar-track {
    background: #ebe1ce;                   /* mesmo tom do header/sidebar */
    border-left: 1px solid #ddd1b8;
  }
  .scroll-bege::-webkit-scrollbar-thumb {
    background: #c9b896;                   /* bege médio */
    border-radius: 6px;
    border: 2px solid #ebe1ce;             /* afastamento do track */
  }
  .scroll-bege::-webkit-scrollbar-thumb:hover {
    background: #a89472;                   /* bege escuro no hover */
  }
  .scroll-bege::-webkit-scrollbar-thumb:active {
    background: #8a7656;
  }
  .scroll-bege::-webkit-scrollbar-corner {
    background: #ebe1ce;
  }
</style>
```

Aplicação em `agendamentos/lista.html` linha 55:

- de: `<div class="overflow-auto max-h-[calc(100vh-180px)] bg-white rounded-lg border border-stone-200">`
- para: `<div class="scroll-bege overflow-auto max-h-[calc(100vh-180px)] bg-white rounded-lg border border-stone-200">`

Aplicar também no `<main>` da `base.html` (`class="flex-1 p-6 overflow-y-auto scroll-bege"`) e nos modais (`max-h-[85vh] overflow-y-auto scroll-bege`) para consistência.

**Decisão:** colocar o `<style>` em `base.html` (todas as páginas herdam). Largura 10px (suficiente em desktop, não rouba área), track `#ebe1ce` (igual sidebar/header — integra o scrollbar como elemento da paleta), thumb `#c9b896` com hover `#a89472`.

---

### Problemas identificados

#### Alto — quebram a sensação de polimento

- **Sidebar não vai até o fim** — `app/templates/base.html` linha 110 (`<aside class="w-56 ... h-full">`). Detalhado acima em "Pedidos explícitos #1". Solução: layout sticky com `overflow-hidden` no wrapper + `overflow-y-auto` no main.
- **Scrollbar nativa cinza na agenda** — `agendamentos/lista.html` linha 55. Detalhado acima em "Pedidos explícitos #2".
- **Header sem peso visual** — `base.html` linha 104. Hoje `px-6 py-3` com `<h1 text-xl>` + `<span text-sm>` na mesma linha. Falta separação clara do conteúdo (a borda inferior `border-[#ddd1b8]` é fina demais). Proposta: aumentar altura para `py-4`, adicionar `shadow-sm`, separar mais o subtítulo (`text-stone-500` em vez de `text-stone-600` ou usar `divide-x divide-[#ddd1b8]` com `pl-4`).
  - de: `class="bg-[#ebe1ce] border-b border-[#ddd1b8] px-6 py-3 flex items-center gap-4"`
  - para: `class="bg-[#ebe1ce] border-b border-[#ddd1b8] px-6 py-4 flex items-center gap-4 shadow-sm shrink-0"`
- **Item ativo da sidebar com pouca presença** — `base.html` linhas 121-124. Fundo `bg-[#d8caab]` + `border-l-4 border-stone-900` está ok, mas `font-medium` é tímido. Proposta: usar `font-semibold` e `text-stone-900` em todos os estados (hover idem) para reforçar.
- **Ações de tabela inconsistentes entre módulos** — Clientes/Serviços têm 2 ações (Editar, Desativar). Profissionais/Produtos têm 3-5 (Editar, Desativar/Reativar, Excluir permanente, Histórico, +/-). A coluna "Ações" varia muito de largura e densidade entre listas. Proposta: padronizar com um menu kebab `⋮` para ações secundárias (Excluir permanentemente, Histórico). Quick win sem JS: agrupar links com `gap-2` em vez de `gap-3` em produtos para reduzir aperto; usar separadores `|` (já tem em produtos) em todas para consistência, OU remover os separadores em todos.
- **"Excluir permanentemente" com tratamento visual gritante** — `produtos/lista.html` linha 87 e `profissionais/lista.html` linha 62. `font-semibold underline decoration-dotted underline-offset-2` chama demais a atenção numa coluna que tem 5 ações lado a lado, virando ruído. Proposta: usar mesmo tom dos outros (`text-red-700 hover:text-red-900`) sem underline; o pictograma do separador `|` já basta. Ou mover para um menu kebab.

#### Médio — inconsistências e ajustes de coerência

- **Focus states inconsistentes** — `clientes/form.html` usa `focus:ring-2 focus:ring-stone-400`; `agendamentos/_form_modal.html` usa `focus:border-stone-500`; `auth/login.html` usa `focus:ring focus:border-stone-500`. Proposta única: `focus:outline-none focus:ring-2 focus:ring-stone-400 focus:border-stone-400` em TODOS os `<input>`, `<select>`, `<textarea>`. Visual coeso e consistente com a paleta (stone-400 funciona sobre bege).
- **Border-radius inconsistente** — listas usam `rounded-md` em botões, `rounded` em outros; calendário usa `rounded`; forms misturam `rounded-md` (clientes) e `rounded` (agendamentos). Proposta: padronizar `rounded-md` (6px) para botões e inputs; `rounded-lg` (8px) para cards/tabelas/modais.
- **Tabela sem zebra e linhas muito altas** — listas usam `py-3` em todas as linhas (sem zebra). Visualmente pesado. Proposta: reduzir para `py-2.5`, adicionar `hover:bg-stone-50` na `<tr>` e zebra leve com `even:bg-stone-50/60`:
  - `<tr class="border-t border-stone-200 hover:bg-stone-50 even:bg-stone-50/40 ...">`
- **Linhas inativas com `opacity-60` matam o badge** — o badge "Inativo" também fica esmaecido, perdendo contraste. Proposta: trocar `opacity-60 text-stone-500` por apenas `text-stone-500 bg-stone-50/40` na `<tr>` e manter o badge no contraste cheio. Ou: aplicar opacity só nas células, não na linha, deixando o badge fora do efeito.
- **Toolbar da agenda apertada** — `agendamentos/lista.html` linhas 20-42. As setas (`←` `→`), date input, label e botão estão num único `flex gap-3` sem agrupamento. Proposta: agrupar navegação data em um pill:
  ```html
  <div class="inline-flex items-center bg-white border border-stone-300 rounded-md overflow-hidden">
    <a href="..." class="px-3 py-2 hover:bg-stone-100 border-r border-stone-300">←</a>
    <input type="date" class="px-2 py-2 text-sm focus:outline-none" ... />
    <a href="..." class="px-3 py-2 hover:bg-stone-100 border-l border-stone-300">→</a>
  </div>
  <span class="text-stone-700 font-medium ml-2">{{ data_fmt }}</span>
  ```
- **Header sticky do calendário sem profundidade** — `agendamentos/lista.html` linhas 60 e 82. Sticky `bg-[#ebe1ce]` sem sombra. Quando o usuário scrolla os agendamentos, os blocos passam por baixo do header e o limite fica invisível. Proposta: adicionar `shadow-[0_2px_0_rgba(0,0,0,0.06)]` no header sticky para criar uma "linha viva".
- **Blocos de agendamento sem hierarquia tipográfica forte** — `lista.html` linhas 98-110. Hora `font-bold`, cliente `truncate`, serviços `text-stone-600 truncate`. Em blocos pequenos (30min) o `font-bold` na hora compete com o nome. Proposta: hora em `text-[11px] font-semibold text-stone-600 uppercase tracking-wide`, nome do cliente em `text-sm font-medium text-stone-900`. Cria contraste real.
- **Modais sem hierarquia de rodapé** — `_form_modal.html` linhas 158-168 e `_card.html` linhas 96-106. Botões de ação ficam diretamente no fluxo, sem separação visual. Proposta: envolver em `<div class="-mx-6 -mb-6 px-6 py-4 bg-stone-50 border-t border-stone-200 rounded-b-lg flex items-center gap-3 justify-end">` para criar um rodapé visual claro.
- **Botão × do modal pequeno e descolado** — `agendamentos/lista.html` linha 129. `text-2xl leading-none top-3 right-3 text-stone-500`. Proposta: aumentar área de clique com `p-2 rounded-full hover:bg-stone-200`:
  ```html
  <button class="absolute top-3 right-3 p-2 rounded-full text-stone-500 hover:text-stone-900 hover:bg-stone-200/60 leading-none" aria-label="Fechar">
    <span class="block text-xl leading-none">&times;</span>
  </button>
  ```
- **`max-w-` divergente entre páginas** — listas: `max-w-5xl`. Forms: `max-w-2xl`. Home: `max-w-3xl`. Agenda: `max-w-full`. Aceitável, mas a home com `max-w-3xl` parece arbitrária. Proposta: home com `max-w-5xl` (alinha com listas) ou centralizar com hero visual.
- **Hint `text-xs text-stone-500` sem separação dos inputs** — formularios. Hoje `mt-1`. Em forms longos vira "soup". Proposta: manter `mt-1` mas usar `text-stone-600` (mais legível) e remover o `text-xs` em hints longos (use `text-sm` quando >1 linha).

#### Baixo — refinamentos opcionais

- **Logo só com texto** — `base.html` linha 105. "SalaoApp" sem ícone. Refinamento: adicionar um SVG inline de tesoura/flor à esquerda (12-16px, `text-stone-700`).
- **Badge "Ativo" indistinguível do fundo branco** — `bg-stone-100 text-stone-700`. Proposta: usar tom verdíssimo bem suave `bg-emerald-50 text-emerald-800` para "Ativo" e manter cinza para "Inativo". Cria affordance imediata.
- **`text-stone-700` no body do header** vs `text-stone-600` (linha 106) — escolher um.
- **Cursor de slot da agenda** — `cursor-pointer` em todos os slots da agenda inunda a tela; o `hover:bg-stone-100/50` (linha 88) é discreto demais. Proposta: aumentar para `hover:bg-stone-200/60` para feedback claro de clicabilidade.
- **Drag handle das colunas sem affordance visual** — `prof-header` tem `cursor-grab` mas nenhum ícone. Refinamento: adicionar `⋮⋮` à esquerda do nome (`text-stone-400 mr-1`).
- **`focus-visible` ausente** — todos os `focus:` deveriam ser `focus-visible:` para não acionar ring com mouse-click. Refinamento global.
- **Transições ausentes** — botões sem `transition-colors`. Adicionar `transition-colors` nos botões primários/secundários para suavizar hover.
- **Skeleton/loading inexistente** — HTMX troca conteúdo sem indicador. Refinamento: adicionar `<div class="htmx-indicator">` global com spinner bege.
- **Toast de sucesso ausente** — pós-save volta direto para lista sem feedback. Pode entrar num próximo ciclo.

---

### Quick wins (trivial, sem reorganização)

1. Scrollbar `.scroll-bege` no `<style>` do `base.html` + classe nas áreas roláveis.
2. Header com `py-4 shadow-sm` em `base.html`.
3. Padronizar focus em inputs: `focus:outline-none focus:ring-2 focus:ring-stone-400 focus:border-stone-400` (search/replace em ~6 arquivos).
4. Padronizar `rounded-md` em botões/inputs e `rounded-lg` em cards/modais.
5. Zebra + hover nas tabelas (`even:bg-stone-50/40 hover:bg-stone-50`).
6. Tirar `font-semibold underline decoration-dotted` do "Excluir permanentemente" — virar `text-red-700 hover:text-red-900`.
7. Botão × dos modais virar `p-2 rounded-full hover:bg-stone-200/60`.
8. `hover:bg-stone-200/60` nos slots da agenda (em vez de `stone-100/50`).
9. Shadow no header sticky do calendário: `shadow-[0_2px_0_rgba(0,0,0,0.06)]`.
10. `transition-colors` em todos os botões primário/secundário.
11. Item ativo da sidebar com `font-semibold` em vez de `font-medium`.
12. Badge "Ativo" em `bg-emerald-50 text-emerald-800`.

### Mudanças estruturais (demandam reorganização)

1. **Layout sticky** (sidebar full-height + main como única região rolável) — mexe em `base.html` em 4 pontos (body, wrapper, aside, main) e muda mental model de scroll do app. Validar com a página da agenda (que já tem scroll interno) para evitar duplo scroll incômodo.
2. **Rodapé visual dos modais** (`bg-stone-50 border-t -mx-6 -mb-6 px-6 py-4`) — exige rever todos os blocos `<div class="flex ... pt-2">` finais de formulários dentro de modais (`_form_modal.html`, `_movimentacao_modal.html`, `_modal_excluir.html`, `_card.html`).
3. **Menu kebab para ações secundárias da tabela** — exige novo componente Alpine (popover) e refator das ações em produtos/profissionais. Reduz ruído mas aumenta cliques.
4. **Toolbar da agenda em pill** — pequeno refator em `agendamentos/lista.html` (5-10 linhas).
5. **Hierarquia tipográfica dos blocos do calendário** — mexe em `lista.html` linhas 98-110; deve validar com casos extremos (bloco de 15min mostrando dados truncados).
6. **`htmx-indicator` global** + spinner bege — exige adicionar markup no `base.html` e config de listener em `htmx:beforeRequest`/`afterRequest`.

### Arquivos afetados (resumo para Onda 2)

- `app/templates/base.html` — sidebar, header, scrollbar global, layout sticky
- `app/templates/agendamentos/lista.html` — toolbar, scrollbar class, header sticky shadow, hover dos slots, hierarquia dos blocos
- `app/templates/agendamentos/_form_modal.html`, `_card.html`, `form_edit.html` — focus padronizado, rodapé visual dos modais
- `app/templates/clientes/lista.html`, `profissionais/lista.html`, `servicos/lista.html`, `produtos/lista.html` — zebra/hover, ações padronizadas, badge "Ativo" colorido, "Excluir permanentemente" desinflado
- `app/templates/clientes/form.html`, `profissionais/form.html`, `servicos/form.html`, `produtos/form.html` — focus padronizado, hints
- `app/templates/_modal_excluir.html`, `produtos/_movimentacao_modal.html` — botão × maior, rodapé visual
- `app/templates/auth/login.html` — focus padronizado
