# Feature: Produtos (estoque + movimentações)

## Resumo
Módulo de cadastro de produtos do salão com controle de estoque. Permite registrar **adições** (entrada/reposição) e **retiradas para uso interno** (consumo do salão). Venda de produtos NÃO é escopo desta feature — será integrada ao Financeiro (fechamento do atendimento) numa feature futura.

## Status
✅ DONE — 2026-05-15

### Débitos técnicos registrados (não bloqueantes)
- **DT-produtos-1** Truncamento silencioso de `observacoes` em 2000 chars (consistente com clientes/servicos; vale validar-e-rejeitar futuramente)
- **DT-produtos-2** GET `/produtos/{id}/movimentar?tipo=foo` cai silenciosamente em `entrada` — defesa em profundidade, mas mascara bugs front
- **DT-produtos-3** `PRAGMA foreign_keys=ON` não é emitido em `database.py` — irrelevante hoje (sem rota DELETE), mas blindaria caso alguém adicione no futuro
- **DT-produtos-4** `estoque_atual` denormalizado sem locking — risco de race em multi-aba; mitigado por defesa em profundidade que rollback se ficar < 0 após saída
- **DT-produtos-5** Quando o módulo Financeiro for implementado, ampliar whitelist de `tipo` pra `saida_venda` e adicionar `agendamento_id` opcional em `MovimentacaoEstoque` via `_migrar_schema` (já estava no plano original)

## Impacto estrutural
Nenhum ajuste em monorepo. Segue a estrutura já estabelecida do app:
- `app/models/produto.py` (novo)
- `app/models/movimentacao_estoque.py` (novo)
- `app/routers/produtos.py` (novo)
- `app/templates/produtos/{lista,form,_movimentacao_modal,historico}.html` (novo)
- Registro do router em `app/main.py`
- Link "Produtos" da sidebar (já existe em `base.html`) passa a apontar pra `/produtos/`
- Import dos novos models em `database.py` / `init_db()` pra registrar tabelas

## Decisões de UX/UI

Princípios mantidos da seção 6: paleta bege/stone, badge "Ativo/Inativo" igual aos outros CRUDs (`bg-stone-100 text-stone-700` / `bg-stone-200 text-stone-500`), form de cadastro idêntico a `clientes/form.html` (`max-w-2xl mx-auto`, card branco, banner de erro topo). Os acentos coloridos abaixo são intencionalmente dessaturados (palette `-100/-800`) pra não brigar com o bege do fundo.

### 1. Badges de estoque (lista + página de histórico)

Proposta do plano **confirmada com pequeno ajuste**: amarelo vira `amber` claro pra ler bem sobre o bege; vermelho mantém-se. Não usar bordas — só fill + texto, igual aos badges existentes.

- `estoque_atual == 0`  → "Sem estoque"
  - `inline-block px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800`
- `0 < estoque_atual <= estoque_minimo`  → "Estoque baixo"
  - `inline-block px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800`
- `estoque_atual > estoque_minimo`  → **sem badge** (não poluir; o número é a info)
- Caso `estoque_minimo == 0`: aplicar apenas a regra "Sem estoque". Não mostrar "baixo" quando o mínimo é zero (não faz sentido alertar).

Texto do badge: "Estoque baixo" e "Sem estoque" exatamente (com inicial maiúscula apenas na primeira palavra, mesmo padrão do "Ativo/Inativo").

### 2. Coluna "Estoque" na lista

Ordem fixa: **número** + **unidade** (mesma cor do texto da linha) + **badge** (à direita do par numérico), separados por `gap-2`. Alinhamento à **esquerda** (consistente com Nome/Telefone/Email do `clientes/lista.html`; alinhamento à direita só faz sentido quando a coluna inteira é dinheiro/quantidade pura — aqui temos número+unidade+badge composto e o alinhamento esquerdo fica mais legível).

Snippet de referência pro frontend-developer:
```html
<td class="px-4 py-3">
  <div class="inline-flex items-baseline gap-2">
    <span class="tabular-nums font-medium text-stone-900">{{ p.estoque_atual }}</span>
    <span class="text-xs text-stone-500">{{ p.unidade }}</span>
    {% if p.estoque_atual == 0 %}
      <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Sem estoque</span>
    {% elif p.estoque_minimo > 0 and p.estoque_atual <= p.estoque_minimo %}
      <span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">Estoque baixo</span>
    {% endif %}
  </div>
</td>
```

`tabular-nums` é importante pra os números das linhas alinharem verticalmente entre si.

### 3. Coluna "Ações" — Adicionar / Retirar / Histórico / Editar / Desativar

Manter o padrão de `clientes/lista.html`: **apenas texto-link**, sem fundos coloridos, agrupados em `flex items-center justify-end gap-3`. A distinção entre "Adicionar" (entrada) e "Retirar" (saída) é feita com **cor de texto sutil + símbolo no rótulo** (`+` e `−`), sem peso extra:

- `+ Adicionar` → `text-emerald-700 hover:text-emerald-900`
- `− Retirar`   → `text-orange-700 hover:text-orange-900`
- `Histórico`   → `text-stone-700 hover:text-stone-900` (neutro, igual a "Editar")
- `Editar`      → `text-stone-700 hover:text-stone-900` (idêntico ao padrão do app)
- `Desativar`   → `text-red-700 hover:text-red-900` (idêntico ao padrão do app)
- `Reativar`    → `text-stone-600 hover:text-stone-900` (idêntico ao padrão do app)

**Separador visual** entre o grupo "movimentação" (Adicionar/Retirar) e o grupo "registro" (Histórico/Editar/Desativar): inserir um `<span class="text-stone-300" aria-hidden="true">|</span>` entre `− Retirar` e `Histórico`. Não usar separadores entre os demais — `gap-3` já basta. O objetivo é deixar claro que as duas primeiras ações **modificam estoque** e as três últimas **navegam/editam metadados**.

Em linha inativa (`opacity-60`), os links coloridos continuam funcionando — a opacidade global já dessatura tudo.

Se o produto está com `estoque_atual == 0`, **não** desabilitar `− Retirar` visualmente — o backend já valida e retorna erro literal no modal. Manter o botão clicável evita a sensação de "botão quebrado".

### 4. Modal de movimentação — `_movimentacao_modal.html`

Estrutura do header (acima do form), antes do banner de erro:

```html
<h2 class="text-xl font-semibold text-stone-900">{{ titulo }}</h2>
<p class="text-sm text-stone-600 mt-0.5">{{ produto.nome }}</p>

<div class="mt-3 mb-4 inline-flex items-baseline gap-2 px-3 py-2 rounded-md
            {% if tipo == 'entrada' %}bg-emerald-50 border border-emerald-100
            {% else %}bg-orange-50 border border-orange-100{% endif %}">
  <span class="text-xs uppercase tracking-wide text-stone-600">Estoque atual</span>
  <span class="text-lg font-semibold tabular-nums text-stone-900">{{ produto.estoque_atual }}</span>
  <span class="text-sm text-stone-600">{{ produto.unidade }}</span>
</div>
```

Onde:
- `titulo` continua sendo "Adicionar ao estoque" ou "Retirar para uso" (já previsto no plano).
- O **chip do estoque atual** é o ponto focal — número grande (`text-lg`, `tabular-nums`), label pequena em uppercase pra hierarquia clara.
- **Diferenciação Adicionar vs. Retirar** acontece em três pontos sutis (sem trocar a paleta do modal — o fundo do modal segue `bg-[#f5efe4]`):
  1. **Fundo do chip de estoque atual** (`emerald-50` vs. `orange-50`).
  2. **Cor do botão primário do form** — manter `bg-stone-900 hover:bg-stone-800 text-white` (mesma do resto do app) e adicionar um **ícone/símbolo no label**: "+ Adicionar" ou "− Retirar". Não tingir o botão de verde/laranja: o padrão visual do app é sempre stone-900 pra ação primária; quebrar isso seria inconsistência.
  3. **Placeholder do campo `quantidade`**: `"Ex.: 5"` (mesmo em ambos) — não adiciona valor diferenciar aqui.

Em erro de "Estoque insuficiente": o chip de estoque atual continua visível e funciona como reforço visual da informação do erro ("Disponível: X un.").

### 5. Página de histórico — `/produtos/{id}/movimentacoes`

#### Card de info do produto (topo)

Reutilizar o mesmo chip do modal (cor neutra aqui, sem entrada/saída):
```html
<div class="bg-white rounded-lg border border-stone-200 p-4 mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1">
  <div>
    <span class="text-xs uppercase tracking-wide text-stone-500">Estoque atual</span>
    <span class="ml-2 text-lg font-semibold tabular-nums text-stone-900">{{ produto.estoque_atual }}</span>
    <span class="text-sm text-stone-600">{{ produto.unidade }}</span>
  </div>
  <div>
    <span class="text-xs uppercase tracking-wide text-stone-500">Mínimo</span>
    <span class="ml-2 text-sm tabular-nums text-stone-700">{{ produto.estoque_minimo }}</span>
  </div>
</div>
```

#### Tabela de movimentações

Colunas: **Data/hora** (esquerda), **Tipo** (esquerda, badge), **Quantidade** (à **direita**, com sinal), **Observações** (esquerda, `text-stone-600`).

Badges de tipo (decisão final, coerente com o resto):
- Entrada → `inline-block px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800` — texto `"Entrada"`
- Saída (uso) → `inline-block px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800` — texto `"Saída"` (sem "_uso" — o usuário não precisa ver o enum cru)

Decisão: **manter `emerald` em vez de `green`** porque `emerald-100/800` casa melhor com o bege quente do fundo (`green` puro fica esverdeado-frio demais ao lado do `#f5efe4`). `orange` (em vez de `amber` ou `red`) porque amber já significa "estoque baixo" — não pode haver colisão semântica; e `red` é destrutivo (desativar/erro), saída de uso não é destrutiva.

Coluna Quantidade — alinhada à **direita** (regra clássica de números em tabela), formato:
```html
<td class="px-4 py-3 text-right">
  <span class="tabular-nums font-medium
        {% if m.tipo == 'entrada' %}text-emerald-700{% else %}text-orange-700{% endif %}">
    {% if m.tipo == 'entrada' %}+{% else %}−{% endif %}{{ m.quantidade }}
  </span>
  <span class="text-xs text-stone-500 ml-1">{{ produto.unidade }}</span>
</td>
```

Usar o caractere `−` (U+2212, MINUS SIGN), não o hífen ASCII — fica mais legível e visualmente alinhado com o `+`.

#### Observações longas
`max-w-[28ch] truncate` na célula com `title="{{ m.observacoes }}"` para evitar tabela quebrando layout.

### 6. Notas para o form (`produtos/form.html`)

Segue 1:1 o padrão de `clientes/form.html`. Únicos pontos específicos de Produtos:
- Campos numéricos (`preco_venda`, `custo`, `estoque_inicial`, `estoque_minimo`) em **grid 2 colunas** (`grid grid-cols-2 gap-3`) pra densidade — Preço/Custo na primeira linha, Estoque inicial/mínimo na segunda. Unidade fica em linha própria, com `max-w-[120px]` no input (campo curto não deve ocupar largura inteira).
- Helper text abaixo de "Estoque mínimo": `<p class="text-xs text-stone-500 mt-1">Deixe 0 para não receber alertas de estoque baixo.</p>`
- Na edição, o campo "Estoque inicial" simplesmente **não é renderizado** (não esconder com `disabled` — remover do DOM). Substituir por uma linha informativa: `<p class="text-xs text-stone-500">Estoque atual: {{ produto.estoque_atual }} {{ produto.unidade }} — alterações de estoque só via "Adicionar" / "Retirar" na lista.</p>

## Modelo de dados

### `Produto` (`app/models/produto.py`)
```python
class Produto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    preco_venda: float = Field(default=0.0)        # R$
    custo: float = Field(default=0.0)              # R$
    estoque_atual: int = Field(default=0)          # unidades inteiras
    estoque_minimo: int = Field(default=0)         # alerta visual quando estoque_atual <= estoque_minimo
    unidade: str = Field(default="un")             # texto curto: "un", "ml", "g", "kg", etc. max 10
    ativo: bool = Field(default=True)
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
```

### `MovimentacaoEstoque` (`app/models/movimentacao_estoque.py`)
```python
class MovimentacaoEstoque(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produto.id", index=True)
    tipo: str = Field(index=True)                  # "entrada" | "saida_uso"
    quantidade: int                                # sempre positivo; tipo define o sinal
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
```

**Regra:** `estoque_atual` do produto é fonte da verdade (denormalizado pra leitura barata). Toda movimentação ajusta `produto.estoque_atual` na mesma transação em que cria a `MovimentacaoEstoque`.

## Endpoints / contratos

| Método | URL | Função | Resposta |
|---|---|---|---|
| GET | `/produtos/` | Lista (todos, ativos+inativos), com badges | HTML completo |
| GET | `/produtos/novo` | Form criar | HTML completo |
| GET | `/produtos/{id}/editar` | Form editar | HTML completo |
| POST | `/produtos/` | Cria produto | 303 → `/produtos/` (sucesso) ou 400 + form (erro) |
| POST | `/produtos/{id}` | Atualiza produto (dados cadastrais — NÃO mexe em estoque) | 303 → `/produtos/` ou 400 + form |
| POST | `/produtos/{id}/desativar` | Soft-delete | 303 → `/produtos/` |
| POST | `/produtos/{id}/reativar` | Reativa | 303 → `/produtos/` |
| GET | `/produtos/{id}/movimentar` | Fragmento modal — form de movimentação. Query `?tipo=entrada` ou `?tipo=saida_uso` define o modo do modal | HTML fragmento (`_movimentacao_modal.html`) |
| POST | `/produtos/{id}/movimentar` | Cria movimentação + atualiza `estoque_atual` | Sucesso: `204 + HX-Refresh: true`. Erro: 400 + `_movimentacao_modal.html` re-renderizado |
| GET | `/produtos/{id}/movimentacoes` | Histórico (página) | HTML completo |

### Contrato do form de produto (POST `/produtos/` e `/produtos/{id}`)
Form-encoded:
- `nome` (str, obrigatório)
- `preco_venda` (str, aceita vírgula decimal; default 0)
- `custo` (str, aceita vírgula decimal; default 0)
- `estoque_atual` (int, default 0) — só editável na **criação**; na edição este campo NÃO aparece no form (estoque só muda via movimentação)
- `estoque_minimo` (int, default 0)
- `unidade` (str, default "un", max 10)
- `observacoes` (str, opcional)

### Contrato do form de movimentação (POST `/produtos/{id}/movimentar`)
Form-encoded:
- `tipo` (str, obrigatório, ∈ {"entrada", "saida_uso"}) — hidden no form
- `quantidade` (int, obrigatório, > 0)
- `observacoes` (str, opcional)

## Validações

### Produto (criar/atualizar)
1. `nome` strip → vazio → "Nome é obrigatório."
2. `preco_venda` parse (vírgula→ponto) → inválido ou < 0 → "Preço de venda inválido."
3. `custo` parse → inválido ou < 0 → "Custo inválido."
4. `estoque_minimo` < 0 → "Estoque mínimo não pode ser negativo."
5. `estoque_atual` (só na criação) < 0 → "Estoque inicial não pode ser negativo."
6. `unidade` strip, default "un" se vazio. `len(unidade) > 10` → "Unidade deve ter no máximo 10 caracteres."
7. Nome duplicado (strip + lower, ignorando o próprio em update) → "Já existe um produto com esse nome."

Em erro: re-renderiza `form.html` com 400 + objeto em memória preservando input + variável `erro`.

### Movimentação
1. `tipo` ∉ {"entrada", "saida_uso"} → "Tipo de movimentação inválido."
2. `quantidade` parse → inválido ou ≤ 0 → "Quantidade deve ser um número inteiro maior que zero."
3. Se `tipo == "saida_uso"` e `quantidade > produto.estoque_atual` → "Estoque insuficiente. Disponível: {estoque_atual} {unidade}."
4. Se produto está inativo → "Não é possível movimentar um produto inativo." (vale pra entrada também — produto desativado fica congelado)

Em erro: 400 + `_movimentacao_modal.html` re-renderizado com `erro` no contexto, preservando `quantidade` e `observacoes` digitados.

Em sucesso: cria `MovimentacaoEstoque`, ajusta `produto.estoque_atual` (`+= quantidade` se entrada, `-= quantidade` se saída), commit, retorna `Response(status_code=204, headers={"HX-Refresh": "true"})`.

## Telas/componentes

### `/produtos/` — lista
- Container `max-w-5xl mx-auto`
- Header `<h1>Produtos</h1>` + `+ Novo produto`
- Estado vazio: card "Nenhum produto cadastrado ainda." com link
- Tabela com colunas: **Nome**, **Estoque** (mostra `estoque_atual unidade`, com badge "Baixo" em amarelo/vermelho quando `<= estoque_minimo`), **Preço** (R$ X,XX), **Status** (Ativo/Inativo), **Ações**
- Linhas inativas: `opacity-60`
- Coluna Ações (alinhada direita):
  - `+ Adicionar` (HTMX GET → `/produtos/{id}/movimentar?tipo=entrada` → `#modal-content`, dispara `open-modal`)
  - `− Retirar` (idem, `?tipo=saida_uso`)
  - `Histórico` (link → `/produtos/{id}/movimentacoes`)
  - `Editar` (link → `/produtos/{id}/editar`)
  - `Desativar`/`Reativar` (form inline; desativar com `confirm()`)
- Inclui o **modal Alpine** no final do template (mesmo padrão de agendamentos: `@open-modal.window`, `@close-modal.window`, `<div id="modal-content">`)
- **Atenção:** o link "Produtos" na sidebar do `base.html` hoje é placeholder; precisa virar link real apontando pra `/produtos/` e receber destaque via `active="produtos"`.

### `/produtos/novo` e `/produtos/{id}/editar` — form
- `max-w-2xl mx-auto`, card branco, banner de erro condicional, padrão dos outros CRUDs
- Campos: Nome*, Preço de venda, Custo, **Estoque inicial** (apenas na criação), Estoque mínimo, Unidade, Observações (textarea)

### `/produtos/{id}/movimentar` — fragmento `_movimentacao_modal.html`
- Título dinâmico: "Adicionar ao estoque" ou "Retirar para uso" (baseado em `tipo`)
- Mostra o nome do produto e o **estoque atual** no topo (info contextual)
- Banner de erro condicional
- Form `hx-post="/produtos/{id}/movimentar" hx-target="#modal-content" hx-swap="innerHTML"`
- Hidden `tipo`
- Campo `quantidade` (number, min=1, required, autofocus)
- Campo `observacoes` (textarea, opcional, placeholder contextual: "Ex.: compra na fornecedora X" ou "Ex.: usado no atendimento de Y")
- Rodapé: botão primário ("Adicionar" / "Retirar") + "Cancelar" (dispara `close-modal`)

### `/produtos/{id}/movimentacoes` — histórico
- `max-w-4xl mx-auto`
- Header: "Movimentações — {nome}" + link "← Voltar para produtos"
- Card com info do produto: estoque atual, mínimo, unidade
- Tabela: **Data/hora** (formatada `dd/mm/yyyy HH:MM`), **Tipo** (badge: "Entrada" verde, "Saída" laranja), **Quantidade** (com sinal `+` / `−`), **Observações**
- Ordem: `criado_em DESC`
- Estado vazio: "Nenhuma movimentação registrada ainda."

## Riscos de segurança
Pontos pro `security-auditor`:
- Form-encoded de input numérico (preco_venda, custo, quantidade) — validar parse robusto, sem `eval` ou cast cego
- `tipo` da movimentação vem de form/query — **whitelist obrigatório** ({"entrada", "saida_uso"}), nunca interpolar direto
- Concorrência: `estoque_atual` é denormalizado. Em ambiente single-user local o risco é baixíssimo, mas vale registrar débito se não tratar.
- Soft-delete já é padrão do app, mas confirmar que rotas de movimentação rejeitam produto inativo
- Sessão/auth já é tratada por middleware global do `auth-single-user`; nenhuma rota nova precisa de tratamento especial — só confirmar que `/produtos/*` está atrás do mesmo guard
- Sem XSS via Jinja autoescape padrão; nas movimentações `observacoes` é texto livre — garantir que é renderizado em `{{ }}` e nunca `{{ ... | safe }}`

## Plano de delegação (ondas)

**Onda 0 — Estrutura:** não necessária. Estrutura existente comporta sem ajustes de monorepo.

**Onda 1 — Design (`ui-designer`):**
- Definir: cor/estilo exato do badge "Estoque baixo" (proposta: amarelo `bg-amber-100 text-amber-800` quando `<= mínimo` e `> 0`; vermelho `bg-red-100 text-red-800` quando `== 0`)
- Layout fino dos ícones/labels das ações na coluna (`+ Adicionar` e `− Retirar` devem ser distinguíveis visualmente — verde/laranja-discretos? só texto?)
- Header do modal de movimentação (mostrar estoque atual em destaque) — tipografia/espacamento
- Layout da página de histórico (badge de tipo, alinhamento da quantidade)
- Output: trecho descritivo (classes Tailwind específicas) que o frontend-developer consome direto

**Onda 2 — Implementação (paralela, após Onda 1):**
- `backend-architect`: models, router, registro em `main.py` e `database.py`, validações, helpers de parse, regra de atualização atômica de `estoque_atual`
- `frontend-developer`: 4 templates (`lista`, `form`, `_movimentacao_modal`, `historico`), ajuste do link "Produtos" na sidebar do `base.html`, integração HTMX/Alpine com o modal

**Onda 3 — Auditoria (paralela):**
- `security-auditor`
- `code-reviewer`

**Onda 4 — Correções (se houver).**

## Critérios de aceite
- [ ] `GET /produtos/` lista produtos com badges corretos (estoque baixo, status)
- [ ] Criar produto valida nome obrigatório, preço/custo numérico, duplicidade de nome
- [ ] Edição NÃO permite alterar estoque_atual direto (campo não existe no form de edição)
- [ ] Adicionar estoque via modal soma à quantidade; retirar subtrai; ambos criam registro em `MovimentacaoEstoque`
- [ ] Tentar retirar mais do que tem dá erro literal "Estoque insuficiente. Disponível: X unidade."
- [ ] Produto inativo bloqueia qualquer movimentação com mensagem clara
- [ ] Histórico mostra movimentações em ordem cronológica descendente
- [ ] Sidebar destaca "Produtos" quando navegando em qualquer rota `/produtos/*`
- [ ] Sucesso da movimentação fecha modal e atualiza a lista (HX-Refresh)
- [ ] Erro de movimentação re-renderiza o modal preservando input + mensagem
- [ ] Code review e security audit sem achados críticos pendentes

## Notas para Financeiro (futuro, fora do escopo)
- Quando o módulo Financeiro for implementado, o "fechamento do atendimento" vai adicionar produtos vendidos e isso deverá gerar uma **saída do tipo `saida_venda`** (novo enum) vinculada ao atendimento — vai exigir migração ALTER pra ampliar o whitelist do campo `tipo` e provavelmente adicionar `agendamento_id` opcional em `MovimentacaoEstoque`. Registrado pra não esquecer.
