# Feature: Correções e melhorias no form de Agendamento

## Resumo
4 problemas/melhorias no formulário de criar/editar agendamento (`_form_modal.html` + `form_edit.html`):

1. **Busca de Profissionais não funciona** — dropdown não traz/filtra resultados
2. **Busca de Serviços não funciona** — idem
3. **Campo Cliente** — hoje é `<select>` HTML; trocar pelo mesmo `multiselect` (em modo single-select) usado pra prof/serv
4. **Duração** — sugestão automática (placeholder + texto auxiliar) não está funcionando

## Status
✅ DONE — 2026-05-15

### CAUSA RAIZ REAL (descoberta na 4ª iteração via console do browser)
O `<script>` inline no `<head>` do `base.html` chamava `document.body.addEventListener('htmx:beforeSwap', ...)` na primeira linha. Como o script roda durante o parse do `<head>`, `document.body` ainda é `null` → `TypeError` → o RESTO DO SCRIPT (incluindo `window.multiselect = ...` e o registro do store `agServicos`) NUNCA EXECUTA.

Sintomas encadeados: Alpine processa `x-data='multiselect(...)'` → `multiselect is not defined` → form fica todo quebrado (busca, duração, submit). Como Alpine grita só "multiselect is not defined", as 3 iterações anteriores focaram em Alpine/eventos/click.away — diagnóstico errado.

Correção: trocar `document.body.addEventListener` por `document.addEventListener` nas 2 chamadas. Eventos HTMX bubble até `document`. Registrado em `feedback_script_no_head_documentbody.md`.

### Outras correções (mantidas, eram problemas reais menores)
- **Busca de profs/servs/cliente NÃO funcionava (verdadeira causa-raiz, identificada na 2ª iteração)**: `@click.away` estava no `<div>` do dropdown, mas o `<input>` de busca é IRMÃO (não descendente) do dropdown. Click no input contava como "fora do dropdown" → fechava antes do dropdown aparecer. Correção: mover `@click.away` do dropdown para o container `<div class="relative">` que envolve input+dropdown. Bug encadeava em "submit não faz nada" porque sem seleção, hidden inputs ficam vazios e o backend retornava 400 com banner re-renderizado visualmente igual ao modal anterior.
- Correção anterior do `@mousedown.prevent` nos itens do dropdown foi mantida (defesa adicional contra blur do input no clique do item), mas não era o bug principal.
- Registrado como aprendizado em `feedback_click_away_irmao.md`.
- **Duração não reativa**: o wrapper do bloco Duração não tinha `x-data` ancestral, então o `:placeholder` e o `x-text="$store.agServicos.sugestao"` ficavam como atributos literais sem reatividade. Correção: adicionar `<div x-data>` vazio no wrapper. Registrado como aprendizado em `feedback_alpine_bindings_precisam_xdata.md`.

### Decisões aplicadas
- **Cliente single-select**: extensão `single: true` no `window.multiselect` faz `adicionar()` substituir em vez de empilhar. Hidden único `name="cliente_id" :value="selecionados[0] || ''"`. Vazio = sem cliente.
- Filtro defensivo em `selecionados` no `init` do multiselect (descarta `null/undefined/''`).

## Impacto estrutural
- `app/templates/agendamentos/_form_modal.html` (modal de criação)
- `app/templates/agendamentos/form_edit.html` (página de edição)
- `app/templates/base.html` — possivelmente o componente `multiselect` JS (acrescentar modo `single` ou criar variante)
- Sem mudanças em backend — o nome do campo continua `cliente_id` (com 0/1 valor), e o backend já aceita esse contrato

## Diagnóstico inicial (a confirmar pelo implementador)

### Itens 1 e 2 (busca quebrada)
Suspeitas:
- O catálogo `profs_json`/`servs_json` pode estar chegando vazio no template (verificar via "view source" do fragmento HTMX após abrir o modal)
- O Alpine pode não estar inicializando o componente após o swap HTMX (`htmx:afterSwap` chama `Alpine.initTree(target)`, mas pode falhar silenciosamente)
- `@click.away="aberto=false"` pode estar fechando o dropdown antes do `@click="adicionar(item.id)"` disparar (race no propagation)
- O dropdown está dentro de um container `min-h-[42px]` com `relative` — `z-20` deveria bastar mas pode estar atrás de outros elementos do modal

**Investigação obrigatória:** abrir o modal, inspecionar elemento, verificar:
- (a) HTML do `x-data` do multiselect tem o catálogo populado?
- (b) Ao focar o input, `aberto` vira `true`? (DOM mostra `x-show`?)
- (c) `filtrados` retorna lista não-vazia quando catálogo tem itens e busca está vazia?
- (d) Console do browser tem algum erro Alpine?

### Item 3 (cliente como multiselect single)

Hoje:
```html
<select name="cliente_id">
  <option value="">— Sem cliente —</option>
  ...
</select>
```

Substituir por componente análogo aos profs/servs, mas com regra "no máximo 1 selecionado". Duas abordagens:

**Abordagem A — variante "single" no `multiselect`:**
- Adicionar opção `single: true` ao componente `window.multiselect` em `base.html`
- Quando `single=true`, `adicionar(id)` faz `this.selecionados = [id]` (substitui em vez de empilhar)
- Hidden input renderiza com `name="cliente_id"` em vez de array
- Vazio = "sem cliente" (selecionados=[])

**Abordagem B — componente novo `singleselect`:**
- Cria função paralela ao `multiselect`
- Evita complicar o `multiselect`
- Mais código duplicado

**Recomendação:** A. Mantém UX consistente, código central, baixo custo.

Atenção: o backend espera `cliente_id` como string única (form-encoded), não array. O componente deve renderizar UM hidden:
```html
<input type="hidden" name="cliente_id" :value="selecionados[0] || ''" />
```

Comportamento esperado: input de busca "Buscar cliente..."; quando 1 cliente selecionado, chip aparece (com `×` pra limpar); novo clique em outro cliente do dropdown substitui o anterior; chip vazio = "sem cliente".

### Item 4 (duração funcionar direito)

O input já tem o binding `:placeholder="$store.agServicos.sugestao + ' min'"` e o texto auxiliar `<span x-text="$store.agServicos.sugestao"></span>`.

Suspeitas:
- O store global `agServicos` pode não estar inicializando antes do `multiselect.init()` rodar
- O input de duração está em escopo Alpine separado (sem `x-data` ancestral), então `$store.agServicos` pode estar `undefined` no momento do render
- O `init()` do multiselect dispara `_onChange(this.sugestao)` que escreve no store, mas isso roda DEPOIS do swap, pode haver flash com placeholder estranho

**Investigação obrigatória:**
- Verificar no console se `Alpine.store('agServicos').sugestao` muda quando o usuário adiciona/remove serviço
- Verificar se o input de duração reage ao novo valor do store (binding `$store.agServicos.sugestao`)
- Verificar se o placeholder mostra a sugestão correta quando há serviços pré-selecionados (edição) ou após selecionar manualmente (criação)

**O que "funcionar direito" deve significar:**
- Sem nenhum serviço selecionado: placeholder e texto auxiliar mostram "— min" (ou esconder o hint completamente — decisão do implementador)
- Com 1+ serviço selecionado: placeholder mostra `max(duracao_minutos)` ex.: "60 min"; texto auxiliar idem
- Em edição de agendamento existente: já carrega com serviços pré-selecionados → placeholder e texto devem mostrar a sugestão imediatamente, sem precisar interagir
- O `value` do input continua sendo apenas o `duracao_override` (se houver) — placeholder mostra sugestão visual; usuário NÃO precisa digitar pra usar o cálculo automático no backend (o backend já calcula quando duracao_override é vazio)

**Decisão de borda:** se o input está vazio e o usuário não quer digitar, OK — vai vazio para o backend, que calcula. Não precisa popular o `value` do input automaticamente; o placeholder + texto auxiliar já comunicam claramente.

## Critérios de aceite
- [ ] Modal de criação: clicar no input de busca de profissionais abre dropdown com todos os ativos; digitar filtra por nome
- [ ] Modal de criação: idem para serviços
- [ ] Selecionar item adiciona chip; clicar no `×` do chip remove; chip removido volta ao dropdown
- [ ] Página de edição: mesmo comportamento, com chips pré-preenchidos a partir do agendamento existente
- [ ] Cliente: agora aparece como input de busca + chip único; selecionar cliente substitui o anterior; clicar no `×` deixa "sem cliente"; backend recebe `cliente_id` correto (vazio ou id)
- [ ] Duração: ao selecionar 1+ serviço, placeholder mostra "X min" onde X = max das durações dos serviços selecionados; texto auxiliar idem; ao desmarcar todos, volta para "— min"
- [ ] Em edição de agendamento com serviços já vinculados: ao abrir a página, placeholder e texto auxiliar já mostram a sugestão correta

## Plano de delegação
Onda única — `frontend-developer`. Sem backend.
Após implementação, validação rápida com `code-reviewer` opcional (só pra confirmar que não quebrou contrato com backend).
