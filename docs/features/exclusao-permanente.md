# Feature: Exclusão permanente de Produtos e Profissionais

## Resumo
Após desativar um Produto ou Profissional, surge a opção de **excluir permanentemente** (hard-delete). Só aparece quando o item já está desativado. Confirmação forte: modal exigindo digitar `EXCLUIR` literalmente.

- **Produtos**: hard-delete em cascade — apaga junto todas as `MovimentacaoEstoque` vinculadas.
- **Profissionais**: hard-delete preservando "fantasma" — agendamentos passados/futuros mantêm o nome do profissional com marcação **(excluído)** no card, mesmo padrão de UX dos inativos hoje. Isso exige adicionar `nome_snapshot` na link table `AgendamentoProfissional`.

## Status
✅ DONE — 2026-05-15

### Débitos técnicos registrados (não bloqueantes)
- **DT-excl-1** `_migrar_schema` engole exceções com `except Exception: pass` em todos os blocos — vale capturar `OperationalError` especificamente e logar; padrão do app todo, fixar em separado
- **DT-excl-2** `onclick` inline com `tojson` no nome é seguro hoje, mas `data-*` + `addEventListener` seria mais CSP-friendly e robusto a mudanças de autoescape do Jinja
- **DT-excl-3** Helper `_calcula_profissionais` em `agendamentos.py` retorna `list[SimpleNamespace]` sem TypedDict — contrato `{id, nome, ativo, excluido}` documentado só em comentário
- **DT-excl-4** Bulk delete de `MovimentacaoEstoque` via loop ORM (consistente com padrão do app); trocar por SQL bulk se virar gargalo
- **DT-excl-5** Tooltip do calendário diz "(is) inativo(s)" mas agora cobre excluídos também — copy ligeiramente impreciso, decisão consciente
- **DT-excl-6** `nome_snapshot == NULL` cai em "(nome perdido)"; vale logar warning quando ocorrer pra detectar regressão

## Impacto estrutural
- `app/models/agendamento.py` — adicionar coluna `nome_snapshot: str | None` em `AgendamentoProfissional`
- `app/database.py` — `_migrar_schema()` ganha bloco que adiciona `nome_snapshot` em `agendamentoprofissional` via `ALTER TABLE` idempotente
- `app/routers/produtos.py` — nova rota `POST /produtos/{id}/excluir`
- `app/routers/profissionais.py` — nova rota `POST /profissionais/{id}/excluir`
- `app/routers/agendamentos.py` — helper `_calcula_profissionais` ajustado pra retornar entradas "fantasma" quando o profissional foi excluído (lê `nome_snapshot` em vez do registro)
- `app/templates/produtos/lista.html` — mostrar "Excluir permanentemente" só nas linhas inativas, com modal de confirmação
- `app/templates/profissionais/lista.html` — idem
- `app/templates/agendamentos/_card.html` e `_form_modal.html` e `form_edit.html` e `lista.html` — onde hoje mostra "(inativo)" pra profissional, passar a mostrar "(excluído)" quando vier do snapshot

## Decisões de UX/UI

### 1. Link "Excluir permanentemente" na coluna Ações

- **Posição:** depois de "Reativar", na MESMA linha do `flex items-center justify-end gap-3` (só aparece em linhas inativas). Ordem final: `Editar | Reativar | Excluir permanentemente`.
- **Separador opcional:** inserir antes do link um `<span class="text-stone-300" aria-hidden="true">|</span>` (padrão já usado em `produtos/lista.html`) pra marcar que é uma ação de natureza diferente. Recomendado.
- **Classes do botão (dentro do `<form>` inline que só abre o modal — não submete):**
  ```
  text-red-800 hover:text-red-900 font-semibold underline decoration-dotted underline-offset-2
  ```
  Justificativa: a linha tem `opacity-60`; precisamos "vencer" sem brigar com a paleta bege/stone. `text-red-800` é um degrau mais escuro que o `text-red-700` do "Desativar" comum, `font-semibold` adiciona peso, e o `underline decoration-dotted` sinaliza "ação fora do fluxo normal" sem virar um botão pesado. Funciona bem em cima do bege `#f5efe4`.
- **Não usar fundo colorido** (ex.: `bg-red-600`) — quebraria a densidade visual da linha da tabela e ficaria ruidoso ao lado das outras ações texto-only.

### 2. Modal de confirmação forte

- **Reusar o backdrop+container HTMX existente** (`bg-stone-900/40` + card `bg-[#f5efe4] rounded-lg shadow-xl`) — mesmo padrão Alpine `x-data="{open:false}"` + `@open-modal-excluir.window` (evento dedicado pra não colidir com o modal HTMX genérico). Conteúdo é renderizado inline (não vem por HTMX), parametrizado por `x-data` do próprio modal (`nome`, `endpoint`).
- **Largura:** `max-w-md` (~28rem). É um diálogo de confirmação, não um form — `max-w-2xl` do modal HTMX é grande demais.
- **Não usar `@click="$dispatch(...)"`** pra abrir — o disparador (link na linha da tabela) não tem ancestral `x-data`. Usar `onclick="window.dispatchEvent(new CustomEvent('open-modal-excluir', {detail:{nome:'…', endpoint:'…'}}))"` (vanilla, ver `feedback_alpine_dispatch_scope.md`). O `x-data` do modal lê o `detail` no listener.
- **Estrutura interna (top → bottom, com `space-y-4` no wrapper):**
  - **Título:** `text-lg font-semibold text-stone-900` — `Excluir <nome> permanentemente?` (interpolar `nome` via `x-text`).
  - **Parágrafo de aviso:** card destacado `bg-red-50 border border-red-200 text-red-800 rounded-md p-3 text-sm`, conteúdo:
    > Esta ação é **irreversível**. Para produtos, todas as movimentações de estoque deste item serão apagadas. Para profissionais, o nome será preservado nos agendamentos com a marca "(excluído)".
    (Use `font-semibold` apenas em "irreversível".)
  - **Label do input:** `block text-sm font-medium text-stone-700 mb-1`, texto literal: `Para confirmar, digite EXCLUIR abaixo:`
  - **Input:** classes idênticas aos inputs do app:
    ```
    w-full border border-stone-300 rounded px-3 py-2 text-sm bg-white focus:outline-none focus:border-stone-500 font-mono tracking-wide
    ```
    `font-mono tracking-wide` reforça que o usuário está digitando uma palavra-chave literal, não um valor livre. `x-model="texto"` (Alpine), `autocomplete="off"`, `spellcheck="false"`.
  - **Rodapé:** `flex items-center justify-end gap-3 pt-2`
    - **Cancelar:** `<button type="button">` com `px-4 py-2 rounded-md text-sm font-medium bg-stone-200 hover:bg-stone-300 text-stone-800` + `@click="open=false; texto=''"`.
    - **Confirmar:** botão submit do `<form method="post" :action="endpoint">`, com binding condicional:
      ```
      :class="texto === 'EXCLUIR'
        ? 'bg-red-700 hover:bg-red-800 text-white cursor-pointer'
        : 'bg-red-300 text-white cursor-not-allowed'"
      :disabled="texto !== 'EXCLUIR'"
      class="px-4 py-2 rounded-md text-sm font-semibold transition-colors"
      ```
      Texto do botão: `Excluir permanentemente` (não abreviar — reforça a gravidade).
- **Comparação `texto === 'EXCLUIR'`** é case-sensitive (já especificado nos critérios de aceite). Não fazer trim — usuário tem que digitar exatamente.
- **Reset ao fechar:** `texto = ''` tanto no Cancelar quanto no Escape (`@keydown.escape.window="open=false; texto=''"`) — evita botão habilitado vazado se o modal reabrir.
- **Foco automático no input ao abrir:** adicionar `x-init` + `$nextTick(() => $refs.input.focus())` no listener, ou `x-ref="input"` no input + foco no handler do evento.

### 3. Marca visual "(excluído)" em agendamentos

- **Mesmo visual do "(inativo)"** — chips do `_form_modal.html` usam `bg-red-100 text-red-700 italic` e o `_card.html` usa `text-red-700 italic`. Reaproveitar exatamente isso, trocando só o texto pra `(excluído)`.
- **Justificativa:** semanticamente "(inativo)" e "(excluído)" significam a mesma coisa pro usuário olhando um agendamento — "essa pessoa não está mais disponível pra trabalhar". Distinguir visualmente (ex.: `line-through` ou cinza escuro) introduz vocabulário visual extra sem ganho funcional. A diferença operacional (não pode reativar) é irrelevante na tela do agendamento. Simplicidade vence.
- **Implementação:** no template, `{% if p.excluido %}(excluído){% elif not p.ativo %}(inativo){% endif %}` dentro do mesmo `<span class="text-red-700 italic">` (ou `bg-red-100 text-red-700 italic` no chip do form). A flag `excluido` vem do shim do helper `_calcula_profissionais`.

### 4. Posição do modal na tela

- **Reusar o backdrop+container do modal HTMX existente** (mesmo overlay full-screen `fixed inset-0 z-50 flex items-start justify-center pt-16 bg-stone-900/40`), mas como um SEGUNDO `<div x-data>` no fim do template, com seu próprio evento (`open-modal-excluir` em vez de `open-modal`). Z-index igual (`z-50`) — os dois modais nunca abrem simultaneamente.
- **Não centralizar verticalmente** (`items-center`) — o `items-start pt-16` do modal existente já é o padrão visual do app; manter consistente. Em telas pequenas o `max-h-[85vh] overflow-y-auto` do container resolve overflow.

## Modelo de dados

### Alteração em `AgendamentoProfissional` (`app/models/agendamento.py`)
```python
class AgendamentoProfissional(SQLModel, table=True):
    agendamento_id: int = Field(foreign_key="agendamento.id", primary_key=True)
    profissional_id: int = Field(foreign_key="profissional.id", primary_key=True)
    nome_snapshot: str | None = None  # preenchido quando o profissional é hard-deleted
```

**Regra:** enquanto o profissional existir, `nome_snapshot` é `None`. Quando hard-delete acontecer, snapshot é populado em todos os link rows ANTES de o profissional ser deletado. A FK pra `profissional.id` fica órfã (SQLite default não enforce, e o app já documenta DT3 de PRAGMA FK OFF — isso permanece consistente).

### Migração em `_migrar_schema()`
Adicionar bloco idempotente que verifica `agendamentoprofissional` via `PRAGMA table_info` e faz `ALTER TABLE agendamentoprofissional ADD COLUMN nome_snapshot TEXT` se a coluna não existir. Padrão idêntico ao bloco existente de `cliente.ativo`.

## Endpoints / contratos

### `POST /produtos/{id}/excluir`
- Form-encoded; sem campos obrigatórios (a confirmação "EXCLUIR" é puramente client-side)
- **Pré-condições:**
  - Produto existe → senão 303 → `/produtos/`
  - Produto está inativo (`ativo == False`) → senão 400 com mensagem "Só é possível excluir produtos desativados." (defesa em profundidade — o botão só aparece em desativados, mas o backend valida)
- **Ação:** dentro de uma transação:
  1. `DELETE FROM movimentacaoestoque WHERE produto_id = X` (cascade manual)
  2. `DELETE FROM produto WHERE id = X`
  3. commit
- **Sucesso:** `RedirectResponse("/produtos/", status_code=303)`

### `POST /profissionais/{id}/excluir`
- Form-encoded
- **Pré-condições:**
  - Profissional existe → senão 303 → `/profissionais/`
  - Profissional está inativo → senão 400 "Só é possível excluir profissionais desativados."
  - **Defesa em profundidade:** garantir que o profissional não é o "único ativo" de nenhum agendamento. Em tese impossível (não estaria inativo), mas validar mesmo assim. Se for, 400 "Não é possível excluir: profissional é o único ativo em N agendamentos."
- **Ação:** dentro de uma transação:
  1. `UPDATE agendamentoprofissional SET nome_snapshot = '<nome>' WHERE profissional_id = X` (preserva fantasma; mantém os link rows)
  2. `DELETE FROM profissional WHERE id = X`
  3. commit
- **Sucesso:** `RedirectResponse("/profissionais/", status_code=303)`

## Helper ajustado: `_calcula_profissionais` em `agendamentos.py`

Hoje (provavelmente) faz algo como: SELECT na link table → SELECT em Profissional pelos ids → retorna lista de objetos `Profissional`.

Nova lógica: para cada link row, se o profissional ainda existe → retorna objeto Profissional real com flag `excluido=False`; se não existe (link órfão) → retorna um shim (dict ou namespace simples) com `{id: profissional_id, nome: link.nome_snapshot, ativo: False, excluido: True}`.

Os templates que listam profissionais de um agendamento (card, blocos do calendário, form de edição) precisam saber lidar com a flag `excluido`. **Profissional excluído nunca volta no dropdown de seleção do form** — mesmo padrão do inativo: só volta em modos de visualização/contexto, não em "campos de seleção pra novo vínculo".

### Impacto nos forms de agendamento (criação/edição)
Hoje `_contexto_form` adiciona profissionais inativos de volta no select se já estavam vinculados. Para profissional **excluído** (não existe mais), a entrada vem do snapshot e deve aparecer como chip já selecionado, marcado `(excluído)` em vermelho/itálico, **não removível** (porque não dá pra re-adicionar). Decisão UX a confirmar com `ui-designer`: pode ser removível (e nesse caso o vínculo some no save) — minha sugestão é deixar removível, pois "remover do agendamento" continua sendo uma operação válida.

### Impacto no calendário
- Profissional excluído: sem coluna (igual inativo)
- Blocos com profissional excluído + outro vinculado: aparecem na coluna do outro, dimmed (mesmo `opacity-60 grayscale` do inativo)
- Blocos só com profissional excluído (edge case): mesmo tratamento dos blocos só com inativo — não aparece em coluna nenhuma. **Atenção** se essa rota é possível: seria, pois um agendamento futuro pode ter sido feito com profissional A (depois desativado, depois excluído). O bloco simplesmente some do calendário. Aceitável — o usuário pode acessar via `/agendamentos/{id}/editar` direto (link salvo, ou via outra rota futura de listagem).

## Validações

### Excluir Produto
1. Produto inexistente → 303 silencioso pra `/produtos/`
2. Produto ativo → 400 "Só é possível excluir produtos desativados."
3. Nenhuma outra validação (cascade incondicional em movimentações)

### Excluir Profissional
1. Profissional inexistente → 303 silencioso pra `/profissionais/`
2. Profissional ativo → 400 "Só é possível excluir profissionais desativados."
3. Profissional é único ativo em algum agendamento → 400 "Não é possível excluir: profissional é o único ativo em {n} agendamento(s). Reagende ou exclua o(s) agendamento(s) primeiro." (DEFESA EM PROFUNDIDADE — só deveria ocorrer se houver bug em outra rota)

Em erro 400 nessas rotas, redireciono 303 pra lista correspondente (sem template re-renderizado — não há input do usuário a preservar; a mensagem precisa chegar via flash? **NÃO temos flash messages no app**). Decisão pragmática: o erro só pode acontecer se o usuário "burlar" a UI. Pra simplificar, retornar JSON/texto simples com status 400 ou redirecionar silenciosamente. Eu prefiro **bloquear na UI** (botão só aparece quando inativo) e **no backend, retornar 400 com mensagem em texto puro** que ninguém vai ver na prática — defesa em profundidade pura.

## Telas/componentes

### `produtos/lista.html` e `profissionais/lista.html`
- Na coluna Ações, em linhas inativas:
  - Hoje: `Editar | Reativar`
  - Novo: `Editar | Reativar | Excluir permanentemente`
- O link "Excluir permanentemente" dispara abertura de um modal Alpine de confirmação forte (não usa `confirm()` simples)

### Modal de confirmação (componente Alpine, embutido no template da lista)
- Aberto via evento `open-confirm-exclusao` carregando id, nome e endpoint do item
- Estrutura:
  ```
  Excluir [nome] permanentemente?
  
  Esta ação é IRREVERSÍVEL.
  - Para Produtos: todas as movimentações de estoque deste produto serão apagadas.
  - Para Profissionais: o nome será mantido em agendamentos passados/futuros marcado como "(excluído)".
  
  Para confirmar, digite EXCLUIR abaixo:
  [_____________]
  
  [Cancelar]  [Excluir permanentemente] ← só habilita quando input == "EXCLUIR"
  ```
- O modal contém o `<form method="post" action="<endpoint>">` que dispara o POST quando o botão é clicado. Botão `disabled` enquanto `texto !== "EXCLUIR"` (binding Alpine).
- Pode reusar o componente modal Alpine de `agendamentos/lista.html` (mesmo padrão de `x-data="{open:false}"` + `@open-modal.window`) — mas como o conteúdo é diferente (não vem por HTMX, vem inline parametrizado), provavelmente vale um modal dedicado pra essa confirmação.

### `agendamentos/_card.html` + `_form_modal.html` + `form_edit.html` + `lista.html`
- Onde hoje renderiza `(inativo)` em vermelho/itálico pra profissional, adicionar lógica de `(excluído)` com mesma marca visual (a `ui-designer` decide se diferencia estilo)
- A flag vem do `excluido` retornado por `_calcula_profissionais`

## Riscos de segurança
Pro `security-auditor`:
- Hard-delete via POST form-encoded — confirmar que está atrás do guard `requer_login` (mesmo padrão dos outros endpoints)
- Validação dupla (UI esconde + backend confere `ativo == False`) — confirmar que a checagem backend NÃO confia no estado do frontend
- Cascade em produtos: confirmar que está numa transação (1 commit pros dois DELETEs) pra não deixar movimentações órfãs em caso de falha entre os deletes
- Snapshot em profissionais: confirmar que o UPDATE acontece ANTES do DELETE, mesma transação
- FK órfã na link table de profissional excluído: já é débito conhecido (PRAGMA FK off). Confirmar que `_calcula_profissionais` não quebra com `profissional_id` apontando pra registro inexistente.
- Defesa em profundidade da regra "único ativo" antes de excluir: vale checar
- Bypass da confirmação "EXCLUIR" — é puramente client-side; backend não valida nada disso. Aceitável porque o ataque é "usuário se enganando" (single-user local). Mas mencionar.

## Plano de delegação (ondas)

**Onda 0 — Estrutura:** não necessária. Estrutura existente comporta.

**Onda 1 — Design (`ui-designer`):**
- Definir layout/cor do link "Excluir permanentemente" na coluna Ações (distinguir do "Desativar" comum sem virar feio)
- Definir layout do modal de confirmação forte: tipografia, espaçamento, posição do input "digite EXCLUIR", estado disabled do botão final
- Decidir se badge "(excluído)" em agendamentos tem visual diferente de "(inativo)" ou compartilha o mesmo estilo
- Output: classes Tailwind concretas em uma seção atualizada deste arquivo

**Onda 2 — Implementação (paralela, após Onda 1):**
- `backend-architect`:
  - Alteração do model `AgendamentoProfissional` + migração em `_migrar_schema`
  - Rotas `POST /produtos/{id}/excluir` e `POST /profissionais/{id}/excluir`
  - Helper `_calcula_profissionais` em `agendamentos.py` ajustado pra emitir shim "excluído"
  - Garantir que `_contexto_form` em agendamentos continua funcionando (profissional excluído entra no chip selecionado mas não no dropdown de seleção)
- `frontend-developer`:
  - Botão "Excluir permanentemente" + modal de confirmação em `produtos/lista.html` e `profissionais/lista.html` (componente Alpine compartilhado, mesmo código duplicado ou via include — preferência: include via `{% include %}` se for limpo, senão duplicar pra manter simples)
  - Ajuste de templates de agendamentos pra exibir `(excluído)` onde hoje exibe `(inativo)`, baseado na flag vinda do helper

**Onda 3 — Auditoria (paralela):** `security-auditor` ‖ `code-reviewer`

**Onda 4 — Correções (se houver).**

## Critérios de aceite
- [ ] Em `/produtos/`, linhas ativas mostram `Editar | Desativar`; linhas inativas mostram `Editar | Reativar | Excluir permanentemente`
- [ ] Mesmo padrão em `/profissionais/`
- [ ] Click em "Excluir permanentemente" abre modal Alpine; botão final está disabled até o usuário digitar `EXCLUIR` (case-sensitive); cancelar fecha sem ação
- [ ] Submeter excluir produto → produto e TODAS suas movimentações somem (verificável em SELECT no banco); redirect 303 pra `/produtos/`
- [ ] Submeter excluir profissional → profissional some; link rows em `agendamentoprofissional` mantêm `nome_snapshot` preenchido
- [ ] Card de um agendamento que tinha profissional excluído mostra o nome com tag `(excluído)`
- [ ] Calendário não cria coluna pra profissional excluído; blocos com excluído + outro ativo aparecem dimmed na coluna do ativo (igual inativo)
- [ ] Tentar bater direto no endpoint com produto ativo → 400 (defesa em profundidade)
- [ ] `_migrar_schema` adiciona `nome_snapshot` em banco existente sem quebrar (testar com `salao.db` já populado)
- [ ] Auditoria sem achados críticos/altos pendentes

## Notas pra implementadores
- O snapshot vai pra dentro da LINK table (`AgendamentoProfissional.nome_snapshot`), NÃO numa tabela nova de "profissional excluído". Decisão consciente: simplifica queries, evita JOIN, e link row é exatamente onde o nome é exibido (no contexto do agendamento).
- A coluna `profissional_id` permanece como PK composta junto com `agendamento_id`. Apontando pra id que não existe mais. Em SQLite default isso funciona sem erro.
- Quando um profissional excluído for visualizado num agendamento, o objeto retornado pelo helper precisa expor `.nome`, `.id`, `.ativo`, `.excluido` — usar `SimpleNamespace` ou um pequeno dataclass interno. Templates Jinja consomem por atributo.
