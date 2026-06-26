# SalaoApp — Especificação completa de implementação

Documento autocontido para que um time de agentes possa **recriar o app do zero**, sem acesso a este repositório, chegando num resultado funcionalmente idêntico.

---

## 1. Visão geral

**SalaoApp** é um sistema **local** (uso pessoal, single-user, sem login) de gestão de salão de beleza. Roda como um único processo Python na máquina da dona, abre o navegador padrão apontando para `http://localhost:8000` e mantém os dados em um arquivo SQLite na raiz do projeto.

Stack:
- **Python 3.11+**
- **FastAPI** (servidor)
- **SQLModel** (ORM em cima do SQLAlchemy)
- **SQLite** (arquivo `salao.db` na raiz)
- **Jinja2** (templates HTML SSR)
- **HTMX** + **Alpine.js** + **Tailwind CSS** — todos via CDN, **sem build step**
- **SortableJS** (CDN) para drag-and-drop das colunas do calendário
- **PyInstaller** (empacotamento final em `.exe` para Windows)

Filosofia mandatória: **simplicidade extrema**. Sem login/autenticação, sem Docker, sem Postgres/Redis, sem React/Vue/SPA, sem npm/webpack/vite, sem CI/CD, sem testes automatizados (a não ser que explicitamente pedido), sem `async def` nos routers (síncrono, pois SQLite vai melhor síncrono).

Idioma da UI e dos identificadores: **português brasileiro** (snake_case Python; kebab-case nas URLs).

---

## 2. Estrutura de arquivos

```
salao_app/
├── salao.db                     # SQLite — gerado em runtime, não versionar
├── requirements.txt
├── build.spec                   # PyInstaller (opcional para empacotar .exe)
└── app/
    ├── __init__.py              # vazio
    ├── main.py                  # FastAPI, lifespan que chama init_db, mounts /static, includes routers
    ├── database.py              # engine SQLite, init_db, get_session, _migrar_schema
    ├── templating.py            # instância compartilhada de Jinja2Templates
    ├── models/
    │   ├── __init__.py          # vazio
    │   ├── cliente.py
    │   ├── profissional.py
    │   ├── servico.py
    │   └── agendamento.py       # 3 tabelas: Agendamento + 2 link tables
    ├── routers/
    │   ├── __init__.py          # vazio
    │   ├── clientes.py
    │   ├── profissionais.py
    │   ├── servicos.py
    │   └── agendamentos.py
    ├── templates/
    │   ├── base.html            # layout: sidebar + main + modal slot
    │   ├── home.html
    │   ├── clientes/{lista.html, form.html}
    │   ├── profissionais/{lista.html, form.html}
    │   ├── servicos/{lista.html, form.html}
    │   └── agendamentos/
    │       ├── lista.html       # calendário diário
    │       ├── _form_modal.html # parcial HTMX: form de criação no modal
    │       ├── _card.html       # parcial HTMX: card de detalhes/edição rápida no modal
    │       └── form_edit.html   # página completa de edição (rota dedicada)
    └── static/                  # vazio inicialmente; Tailwind via CDN
```

**Convenções:**
- Templates parciais HTMX começam com `_` (ex.: `_form_modal.html`, `_card.html`).
- Rotas são **síncronas** (`def`, não `async def`).
- Models em `app/models/<modulo>.py`, routers em `app/routers/<modulo>.py`, templates em `app/templates/<modulo>/`.

---

## 3. `requirements.txt`

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlmodel>=0.0.22
jinja2>=3.1.4
python-multipart>=0.0.12
```

Como rodar em dev:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Doc da API automática em `/docs`.

---

## 4. Banco e sessão

`app/database.py`:
- `DB_PATH = <raiz_do_projeto>/salao.db`
- `DATABASE_URL = f"sqlite:///{DB_PATH}"`
- `engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})` — `check_same_thread=False` é necessário porque FastAPI síncrono pode atender requests em threads diferentes.
- `init_db()`:
  1. Importa todos os módulos de models para registrar tabelas em `SQLModel.metadata` (`cliente`, `profissional`, `servico`, `agendamento`).
  2. Chama `SQLModel.metadata.create_all(engine)`.
  3. Chama `_migrar_schema()`.
- `_migrar_schema()`: migrações idempotentes manuais via `ALTER TABLE`, porque `create_all` só cria tabelas novas — não adiciona colunas a tabelas já existentes. Exemplo concreto que existe: adicionar `cliente.ativo BOOLEAN NOT NULL DEFAULT 1` quando ela não existir. Padrão para qualquer migração futura: consultar `PRAGMA table_info(<tabela>)` e fazer `ALTER TABLE` se a coluna faltar.
- `get_session()`: dependency do FastAPI, `with Session(engine) as session: yield session`.

`app/main.py`:
- Usa `@asynccontextmanager` `lifespan` que chama `init_db()` no startup.
- Cria `STATIC_DIR = app/static/`, garante existência com `mkdir(parents=True, exist_ok=True)` e monta em `/static`.
- Registra os 4 routers (`agendamentos`, `clientes`, `profissionais`, `servicos`).
- Rota `GET /` renderiza `home.html` com `active="home"`.

`app/templating.py`:
- Existe apenas para evitar import circular entre `main.py` e os routers.
- Expõe `templates = Jinja2Templates(directory=str(TEMPLATES_DIR))` apontando para `app/templates/`.

---

## 5. Modelos (schema)

Todos os models herdam de `SQLModel, table=True`, têm `id: int | None = Field(default=None, primary_key=True)` e `criado_em: datetime = Field(default_factory=datetime.now)`.

### 5.1 Cliente — `app/models/cliente.py`
```python
class Cliente(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    telefone: str | None = None
    email: str | None = None
    observacoes: str | None = None
    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.now)
```

### 5.2 Profissional — `app/models/profissional.py`
Estrutura **idêntica** ao Cliente, só muda o nome da classe/tabela:
```python
class Profissional(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    telefone: str | None = None
    email: str | None = None
    observacoes: str | None = None
    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.now)
```

### 5.3 Servico — `app/models/servico.py`
```python
class Servico(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    preco: float = Field(default=0.0)            # em reais
    duracao_minutos: int = Field(default=30)
    ativo: bool = Field(default=True)
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
```

### 5.4 Agendamento — `app/models/agendamento.py`
Três tabelas:
```python
class Agendamento(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    data_hora: datetime = Field(index=True)
    cliente_id: int | None = Field(default=None, foreign_key="cliente.id", index=True)
    duracao_override: int | None = None      # minutos; None = usar max dos serviços
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)

class AgendamentoServico(SQLModel, table=True):
    agendamento_id: int = Field(foreign_key="agendamento.id", primary_key=True)
    servico_id:     int = Field(foreign_key="servico.id",     primary_key=True)

class AgendamentoProfissional(SQLModel, table=True):
    agendamento_id:    int = Field(foreign_key="agendamento.id",    primary_key=True)
    profissional_id:   int = Field(foreign_key="profissional.id",   primary_key=True)
```

Não há `SQLModel.Relationship()` — toda navegação é feita por queries explícitas nos routers (helpers `_calcula_servicos`, `_calcula_profissionais`, `_calcula_cliente`).

---

## 6. Layout / Visual

`base.html`:
- Carrega via CDN: Tailwind, HTMX 1.9.12, Alpine.js 3.x.
- Define **dois handlers globais** muito importantes:
  1. `htmx:beforeSwap` — se a resposta tiver status 400 ou 422, força `shouldSwap = true` e `isError = false`. **Sem isso, HTMX não trocaria o conteúdo em 4xx**, e o app usa 400 com fragmento HTML para mostrar erros de validação (banner vermelho dentro do form).
  2. `htmx:afterSwap` — chama `window.Alpine.initTree(evt.detail.target)` após cada swap, porque o Alpine não inicializa automaticamente fragmentos injetados pelo HTMX.
- Paleta:
  - Fundo da página: `bg-[#f5efe4]` (bege claro)
  - Header e sidebar: `bg-[#ebe1ce]`
  - Borda sidebar: `border-[#ddd1b8]`
  - Item ativo da sidebar: `bg-[#d8caab]` + borda esquerda `border-stone-900`
  - Texto principal: `text-stone-900`/`text-stone-700`/`text-stone-600`
  - Botão primário: `bg-stone-900 hover:bg-stone-800 text-white`
  - Botão secundário: `bg-stone-200 hover:bg-stone-300 text-stone-800`
  - Botão destrutivo: texto `text-red-700 hover:text-red-900`
  - Banner de erro: `bg-red-50 border border-red-200 text-red-800`
  - Blocos de agendamento no calendário: `bg-[#f7efde]` com borda esquerda `border-stone-900`; hover `bg-[#f0e5c8]`
- Layout: `<header>` no topo (logo "SalaoApp" + texto "Gestão do salão"), abaixo flex com `<aside class="w-56">` (sidebar) e `<main class="flex-1 p-6">`.
- Sidebar tem links na ordem: **Agendamentos, Clientes, Profissionais, Serviços, Produtos, Financeiro**. "Produtos" e "Financeiro" estão presentes só como itens da nav, ainda **não implementados** (não há router/endpoint). Cada `<a>` recebe destaque visual quando `active == key`.
- O template recebe via contexto `active` (string) para destacar o item correspondente.

`home.html`: simplesmente "Bem-vinda!" + "Use o menu à esquerda…".

---

## 7. Padrão de CRUD (Clientes, Profissionais, Serviços)

Os três módulos seguem o **mesmo formato**, com pequenas diferenças listadas depois.

### 7.1 Rotas

| Método | URL | Função |
|---|---|---|
| GET | `/clientes/` | lista (renderiza `lista.html`) |
| GET | `/clientes/novo` | form de criação (`form.html`) |
| GET | `/clientes/{id}/editar` | form de edição (`form.html`, com objeto preenchido) |
| POST | `/clientes/` | cria (Form encoded) |
| POST | `/clientes/{id}` | atualiza |
| POST | `/clientes/{id}/desativar` | seta `ativo=False` |
| POST | `/clientes/{id}/reativar` | seta `ativo=True` |

Trocar `clientes` por `profissionais` ou `servicos` para os outros módulos. **Não há rota DELETE** — desativação é soft-delete (`ativo=False`). Após cada ação POST, **redireciona com 303** para a listagem (`RedirectResponse(url=..., status_code=303)`).

### 7.2 Listagem (`lista.html`)
- Container `max-w-5xl mx-auto`.
- Header com `<h1>` (ex.: "Clientes") + botão `+ Novo cliente` à direita.
- Se a lista está vazia: card branco centralizado "Nenhum X cadastrado ainda." com link "+ Novo X".
- Senão: tabela HTML branca dentro de `rounded-lg border border-stone-200` com colunas:
  - **Clientes**: Nome, Telefone, Email, Status, Ações
  - **Profissionais**: Nome, Telefone, Email, Status, Ações
  - **Serviços**: Nome, Preço (formatado "R$ X,XX"), Duração (X min), Status, Ações
- Linhas inativas: `opacity-60` + texto cinza.
- Coluna Status: badge "Ativo" (`bg-stone-100`) ou "Inativo" (`bg-stone-200 text-stone-500`).
- Coluna Ações (alinhada à direita): "Editar" (link), seguido de "Desativar" (vermelho, `confirm()` antes) ou "Reativar" (cinza).
- Ações de desativar/reativar são `<form method="post">` inline.
- Listagem ordena por `nome` (case-sensitive, do banco; Python `order_by(Model.nome)`).

### 7.3 Form (`form.html`)
- Container `max-w-2xl mx-auto`.
- `<h1>` recebe `{{ titulo }}` ("Novo Cliente" / "Editar Cliente").
- Banner de erro `{% if erro %}` no topo.
- Card branco com `<form method="post" action="{{ action }}">`.
- Campos por módulo (todos com label e mensagem de ajuda quando aplicável):
  - **Cliente / Profissional**: Nome*, Telefone (`maxlength=15`, `pattern="\d{8,15}"`, `inputmode=numeric`, placeholder `11999998888`), Email (`maxlength=200`, `pattern` simples), Observações (textarea).
  - **Serviço**: Nome*, Preço (text com vírgula decimal, placeholder `0,00`), Duração em minutos* (number, `min=1 max=300 step=1`, placeholder `30`), Observações.
- Rodapé: botão "Salvar" (primário) + link "Cancelar" (secundário) que volta para a listagem.
- Em edição, todos os campos vêm pré-preenchidos com os valores atuais.

### 7.4 Lógica de validação (no router)

**Helpers compartilhados** (cada router define os seus localmente, sem módulo utilitário central):

```python
def _vazio_para_none(valor):  # strip; "" -> None
def _normalizar(valor, *, lower=False):  # strip + opcional lower; "" -> None
```

**Clientes e Profissionais:**
- Regex telefone: `^\d{8,15}$` (apenas dígitos, 8 a 15).
- Regex email: `^[^@\s]+@[^@\s]+\.[^@\s]+$` (formato simples).
- Função `_validar_contato(telefone, email)` retorna mensagem de erro ou `None`. Telefone e email são **opcionais**; só validam se preenchidos.
- Função `_<entidade>_duplicado(session, nome, email, telefone, ignorar_id=None)`: carrega todos os registros e retorna `True` se existir outro com a tripla (nome+email+telefone) idêntica após normalização (lower em nome e email, strip nos três; campos vazios viram `None` e comparam `None == None`).
- Sequência ao criar/atualizar:
  1. `nome_limpo = nome.strip()`.
  2. `erro = _validar_contato(...)`.
  3. Se sem erro ainda, checa duplicidade (`erro = "Já existe um cliente/profissional com esse mesmo nome, e-mail e telefone."`).
  4. Se `erro` → renderiza o **mesmo template `form.html`** com `status_code=400` e contexto contendo o objeto em memória com os valores que o usuário digitou (não persiste), preservando assim o input. Em update, mantém o `id` original.
  5. Senão, salva (`session.add(...); session.commit()`) e redireciona 303 para a listagem.
- Mensagens de erro literais:
  - "Telefone deve conter apenas números (8 a 15 dígitos)."
  - "E-mail inválido. Use o formato exemplo@dominio.com."
  - "Já existe um cliente com esse mesmo nome, e-mail e telefone." (idem para profissional)

**Serviços:**
- `_parse_preco(valor)`: troca `,` por `.` e converte para float; fallback 0.0.
- `_parse_duracao(valor)`: int positivo; retorna `None` se inválido ou ≤ 0.
- `_nome_duplicado(session, nome, ignorar_id=None)`: compara nome após strip+lower.
- Validações em criar/atualizar:
  - `duracao is None` → "Duração é obrigatória e deve ser um número inteiro maior que zero."
  - `duracao > 300` → "Duração não pode passar de 300 minutos (5h)."
  - Nome duplicado → "Já existe um serviço com esse nome."
- Re-renderiza com status 400 + preserva o que o usuário digitou.

**Desativar/Reativar:** simplesmente buscam por id, mudam `ativo`, commit, e redirecionam 303 para `/clientes` (ou `/profissionais`, `/servicos`). Se o id não existe, redirecionam silenciosamente.

---

## 8. Módulo Agendamentos (o mais complexo)

### 8.1 Conceito
- **Calendário diário** com colunas por profissional (ordem alfabética; ordem das colunas pode ser arrastada e é persistida em `localStorage`).
- Cada agendamento tem: data/hora, **N profissionais**, **N serviços**, cliente opcional, duração override opcional, observações.
- Duração efetiva: `duracao_override` se > 0; senão `max(serviço.duracao_minutos)` dos serviços vinculados; senão 60.
- Expediente: **06:00 a 22:00**. Slots de **30 minutos**. Início mínimo 06:00, último início possível 21:30 (porque início deve ser `< 22:00`). Agendamento não pode **terminar** depois das 22:00.
- Duração máxima por agendamento: **300 min (5h)**.

### 8.2 Constantes (no router)
```python
_HORA_MIN = 6
_HORA_MAX = 22
_DURACAO_MAX = 300
```

### 8.3 Helpers internos
- `_vazio_para_none`, `_parse_cliente_id` (vazio ou "0" → None), `_parse_duracao_override` (vazio → None; ≤0 → None), `_parse_data_hora(data, hora)` (combina `YYYY-MM-DD` + `HH:MM` em datetime, retorna None se inválido).
- `_duracao_efetiva(ag, servicos)` — regra acima.
- `_calcula_servicos(session, agendamento_id)`, `_calcula_profissionais(...)`, `_calcula_cliente(session, ag)` — fazem joins via link tables.
- `_horarios_dia()` — gera lista `["06:00", "06:30", "07:00", ..., "21:30"]` (32 slots).
- `_substitui_links(session, agendamento_id, prof_ids, serv_ids)`:
  1. Deleta todos os links existentes (`AgendamentoProfissional` e `AgendamentoServico` desse agendamento).
  2. `session.flush()` para garantir deleções antes dos inserts.
  3. Insere os novos.
- `_conflita_para_profissional(session, profissional_id, inicio, fim, ignorar_agendamento_id=None)`:
  - Restringe candidatos ao **mesmo dia** (intervalo `[00:00 do dia, 00:00 do dia+1)`).
  - Carrega todos os links onde `profissional_id == X`, depois carrega os Agendamentos correspondentes que caem no dia.
  - Para cada candidato, calcula `fim_candidato` a partir dos serviços + override.
  - Detecta overlap por: `ag.data_hora < fim AND ag_fim > inicio`.
  - Retorna o **primeiro** conflito ou None.
- `_contexto_form(session, agendamento, action, titulo, erro=None, data_default="", hora_default="", profissional_id_default=None)`:
  - Carrega clientes/profissionais/serviços **ativos** (`where(Modelo.ativo == True)`, ordenados por nome).
  - Calcula `profissionais_selecionados`, `servicos_selecionados`, `cliente_selecionado_id` a partir dos links do agendamento (se houver).
  - **Detalhe importante:** se o agendamento referencia algum profissional/serviço/cliente **inativo**, esse item é adicionado de volta à lista usada no form (e a lista é reordenada) — senão sumiria do dropdown e perderia o vínculo ao re-salvar. A UI marca esses itens como "inativo" com badge vermelho.
  - Em criação a partir de um slot do calendário, se `profissional_id_default` for fornecido, ele já vem pré-selecionado.

### 8.4 Rotas

| Método | URL | O que faz |
|---|---|---|
| GET | `/agendamentos/` | Página completa — calendário diário (default = hoje, override via `?data=YYYY-MM-DD`) |
| GET | `/agendamentos/novo-modal` | **Fragmento** — `_form_modal.html`. Aceita `?data=&hora=&profissional_id=` opcionais |
| GET | `/agendamentos/{id}/card` | **Fragmento** — `_card.html` com detalhes/quick-edit |
| GET | `/agendamentos/{id}/editar` | Página completa — `form_edit.html` |
| POST | `/agendamentos/` | Cria — sucesso retorna **204 com header `HX-Refresh: true`**; erro retorna **400 com `_form_modal.html`** re-renderizado |
| POST | `/agendamentos/{id}` | Atualiza tudo — sucesso 303 redirect para `/agendamentos?data=<data>`; erro 400 com `form_edit.html` re-renderizado |
| POST | `/agendamentos/{id}/horario` | Inline na _card_: altera apenas data/hora. Sucesso: 204 + `HX-Refresh`. Erro: 400 + `_card.html` |
| POST | `/agendamentos/{id}/duracao` | Inline na _card_: altera apenas `duracao_override`. Sucesso: 204 + `HX-Refresh`. Erro: 400 + `_card.html` |
| POST | `/agendamentos/{id}/excluir` | Apaga links + agendamento. Redirect 303 para `/agendamentos?data=<data_do_agendamento>` |

### 8.5 Validações em criar/atualizar
Mensagens de erro literais (substitua valores entre `{}`):

1. `profissional_ids` vazio → "Selecione pelo menos um profissional."
2. `servico_ids` vazio → "Selecione pelo menos um serviço."
3. `_parse_data_hora` retorna None → "Data e hora inválidas."
4. `not (6 <= data_hora.hour < 22)` → "O horário de início deve estar entre 06:00 e 21:59."
5. `data_hora < datetime.now()` (em criação; em update, só bloqueia se está sendo *trocado* para o passado — se a data já era passado e está sendo mantida, permite editar outros campos) → "Não é possível agendar para uma data/hora no passado." / "Não é possível remarcar para uma data/hora no passado."
6. Duração efetiva > 300 → "A duração total não pode passar de 300 minutos (5h)."
7. `fim > data_hora.replace(hour=22, minute=0)` → "O agendamento termina às {fim}, depois do limite do expediente (22:00). Reduza a duração ou escolha um horário mais cedo."
8. Conflito de horário em qualquer profissional selecionado → "Conflito de horário para {nome_profissional} ({inicio}–{fim_conflito})."

Em update e nas rotas inline `/horario` e `/duracao`, o agendamento sendo editado é ignorado na busca por conflito (via `ignorar_agendamento_id`).

### 8.6 Excluir
Deleta primeiro todos os `AgendamentoProfissional` e `AgendamentoServico` do agendamento (FK), depois o Agendamento. Redireciona 303 para `/agendamentos?data=<data_do_agendamento>` (ou para hoje se o agendamento já não existia).

### 8.7 Template `lista.html` (calendário)
Estrutura do calendário:
- Toolbar no topo: setas `←` `→` (linkam para `?data=anterior`/`?data=próxima`), input `type="date"` que muda a URL ao alterar (`onchange="location.href='/agendamentos?data='+this.value"`), label com data formatada `dd/mm/yyyy`, e botão `+ Novo agendamento` à direita (HTMX GET → `/agendamentos/novo-modal?data=<data>` injetando em `#modal-content` e disparando `open-modal` no window).
- Estado vazio "Nenhum profissional cadastrado." com link para `/profissionais/novo`.
- Grid:
  - Wrapper externo com scroll X e Y: `overflow-auto max-h-[calc(100vh-180px)]`.
  - Container interno `flex` (com `min-width: max-content`), id `calendario-grid`.
  - **Coluna de horários (esquerda, w-16)**: cabeçalho vazio (h-10, sticky top), depois 32 slots de 30px cada (1px = 1min). Mostra HH:00 em destaque (text-xs stone-500) e HH:30 esmaecido (text-[10px] stone-300). Slots de hora cheia ganham borda superior mais escura.
  - **Cada coluna de profissional**: `flex-1 min-w-[100px] border-r border-stone-200 last:border-r-0`, atributo `data-prof-id`. Header sticky com nome (handle de drag, cursor-grab). Body absoluto altura 960px (16h × 60min).
  - **Slots clicáveis (fundo)**: 32 divs absolutos, cada um `top: i*30`, `height: 30px`, com HTMX GET em `/agendamentos/novo-modal?data=...&hora=HH:MM&profissional_id=...`.
  - **Blocos de agendamento**: para cada agendamento do dia/profissional, div absoluto com `top = (hora*60+min) - 360` (porque o dia começa às 6h = 360 min), `height = duracao_efetiva - 2`, conteúdo: hora (negrito), nome do cliente (ou "—"), e se duração >= 60 min, a lista de serviços. HTMX GET em `/agendamentos/<id>/card` → modal.
  - **Drag-and-drop das colunas**: SortableJS via CDN. `draggable: '[data-prof-id]'`, `handle: '.prof-header'`. Salva a ordem em `localStorage` sob chave `agendamentos:colOrder` (array de strings com ids). Ao carregar a página, lê a ordem salva e re-anexa as colunas; profissionais novos (sem entrada na ordem salva) vão para o final.
- **Modal único** no fim da página, controlado por Alpine: `<div x-data="{open:false}">` com eventos `@open-modal.window="open=true; body.overflow=hidden"`, `@close-modal.window="open=false; body.overflow=''"`, `@keydown.escape.window`. `x-show="open"`, fundo `bg-stone-900/40`, conteúdo `max-w-2xl`. Tem botão `×` no canto. Slot interno `<div id="modal-content" class="p-6">` recebe o fragmento via HTMX. Inclui `<style>[x-cloak]{display:none!important}</style>`.

### 8.8 Template `_form_modal.html` (criar agendamento, fragmento)
Estrutura do form (todos os campos abaixo):
- Título "Novo agendamento" (vem de `titulo`).
- Banner de erro condicional.
- `<form hx-post="/agendamentos" hx-target="#modal-content" hx-swap="innerHTML">`.
- Campos:
  1. **Data**\* (`<input type="date" name="data" required value="{{ data_default or data }}">`).
  2. **Hora**\* (`<input type="time" name="hora" required value="{{ hora_default }}">`).
  3. **Profissionais**\* — multi-select customizado com Alpine: chips dos selecionados (com `×` para remover), input de busca com dropdown filtrado por nome (case-insensitive); itens inativos não aparecem na busca mas, se já estavam selecionados (edição), aparecem como chip marcado "inativo" em vermelho/itálico. Hidden inputs `name="profissional_ids"` (um por seleção) — geram lista no submit. O catálogo é renderizado inline em JSON via Jinja: `[{id, nome, nomeLower, ativo}]`.
  4. **Serviços**\* — mesma UX dos profissionais (chips + busca), mas o chip mostra "(N min)" ao lado do nome. O componente Alpine externo armazena `selecionados` dos serviços e expõe um getter `sugestao` (máx duração entre os selecionados; "—" se vazio).
  5. **Cliente** — `<select name="cliente_id">` com `<option value="">— Sem cliente —</option>` + opções dos clientes (mostra " (inativo)" no rótulo se aplicável).
  6. **Duração (min)** — `<input type="number" name="duracao_override" min="1" max="300">` com placeholder dinâmico ligado ao Alpine: mostra a `sugestao` (ex.: "60 min"). Texto auxiliar: "Sugerido pelos serviços: X min. Deixe vazio para usar o valor calculado."
  7. **Observações** — `<textarea name="observacoes" rows="3">`.
- Rodapé: "Criar agendamento" (primário) + "Cancelar" (dispara `close-modal`).

Importante na renderização do contexto JS: usar o filtro `|tojson` para nomes (evita escape errado), e renderizar arrays Python como literais JS.

### 8.9 Template `form_edit.html` (página completa de edição)
Mesma estrutura visual do `_form_modal.html`, mas é uma página completa (extends `base.html`) e o título é "Editar Agendamento". O `action` é `/agendamentos/{id}`. Em sucesso, o backend redireciona 303 para `/agendamentos?data=<nova_data>`. Em erro, re-renderiza essa mesma página com 400.

### 8.10 Template `_card.html` (modal de detalhes/quick-edit)
- Cabeçalho: nome do cliente (`— Sem cliente —` se nulo), profissionais (lista joined por vírgula), serviços (idem).
- Banner de erro condicional.
- Seção **Horário**: form `hx-post="/agendamentos/{id}/horario"` com inputs date/hora pré-preenchidos + botão "Atualizar horário". Em sucesso: HX-Refresh.
- Seção **Duração**: form `hx-post="/agendamentos/{id}/duracao"` com input number `duracao_override` (placeholder "Calculada: X min"), botão "Atualizar duração". Texto auxiliar: "Duração efetiva atual: X min. Deixe vazio para usar a duração calculada pelos serviços (X min)."
- Observações (se houver).
- Rodapé: link "Editar tudo" → `/agendamentos/{id}/editar` (página completa) + form `POST /agendamentos/{id}/excluir` com `onclick="return confirm('Excluir este agendamento?')"`, botão "Excluir" em vermelho.

---

## 9. Padrões transversais (siga sempre)

1. **Rotas síncronas**: `def`, não `async def`. SQLite não ganha nada com async.
2. **Form-encoded** em POST (HTML clássico), nunca JSON.
3. **Após mutação bem-sucedida vinda de form não-HTMX**: `RedirectResponse(url=..., status_code=303)`.
4. **Após mutação bem-sucedida vinda de form HTMX que precisa reload completo**: `Response(status_code=204, headers={"HX-Refresh": "true"})`.
5. **Em erro de validação**: renderiza o mesmo template (parcial ou completo) com `status_code=400` e variável `erro` no contexto contendo a mensagem. Preservar todos os valores que o usuário digitou.
6. **HTMX precisa ser autorizado a swappar 4xx** (handler global em `base.html` — não esquecer).
7. **Após cada swap HTMX, Alpine precisa ser re-iniciado** no fragmento (handler global em `base.html`).
8. **Soft-delete** em todo lugar (Cliente, Profissional, Serviço usam `ativo`). Agendamento é o único com hard-delete.
9. **Itens inativos vinculados a agendamentos não somem** — eles voltam ao contexto do form e são marcados visualmente como "inativo".
10. **Filtros de lista no calendário/forms**: só `ativos`. Filtros nas listas próprias (`/clientes`, etc.): mostram todos (ativos e inativos), com badge de status.
11. **Sem 404 customizado em redirecionamentos pós-ação**: se um id de cliente/serviço/profissional não existir, simplesmente redireciona para a lista.
12. **Ordenação padrão**: por `nome` (alfabética).
13. **Mensagens de erro/UX em português**.

---

## 10. Empacotamento (opcional)

`build.spec` (PyInstaller) deve gerar `dist/SalaoApp.exe` que ao ser executado:
1. Sobe o FastAPI em `localhost:8000`.
2. Abre o navegador padrão automaticamente (`webbrowser.open("http://localhost:8000")` em um hook do startup).
3. Mantém rodando até o usuário fechar o terminal.

Não é necessário implementar isso para o teste de re-criação funcional — o `uvicorn app.main:app` já é suficiente.

---

## 11. Sugestão de divisão para 6 agentes

| Agente | Responsabilidade |
|---|---|
| 1 — Bootstrap | `requirements.txt`, `app/__init__.py`, `app/main.py`, `app/database.py`, `app/templating.py`, `app/templates/base.html`, `app/templates/home.html` |
| 2 — Clientes | `app/models/cliente.py`, `app/routers/clientes.py`, `app/templates/clientes/{lista,form}.html` |
| 3 — Profissionais | `app/models/profissional.py`, `app/routers/profissionais.py`, `app/templates/profissionais/{lista,form}.html` |
| 4 — Serviços | `app/models/servico.py`, `app/routers/servicos.py`, `app/templates/servicos/{lista,form}.html` |
| 5 — Agendamentos backend | `app/models/agendamento.py`, `app/routers/agendamentos.py` (toda a lógica de conflito, duração efetiva, validações) |
| 6 — Agendamentos frontend | `app/templates/agendamentos/{lista,_form_modal,_card,form_edit}.html` (calendário, modal, drag-and-drop, multi-selects Alpine) |

Ordem recomendada: 1 → (2, 3, 4 em paralelo) → 5 → 6. Os agentes 5 e 6 devem alinhar o **contrato dos endpoints e nomes de campos do form** antes de começarem.

---

## 12. Critério de aceitação ("pronto" significa)

- Servidor sobe com `uvicorn app.main:app --reload` sem erros.
- `salao.db` é criado automaticamente no primeiro start.
- `GET /` mostra a home com a sidebar.
- CRUD completo funciona para Clientes, Profissionais e Serviços (criar, editar, desativar, reativar; validações de telefone/email/duplicidade/duração/nome único conforme seção 7.4 disparam com mensagens literais).
- Calendário diário em `/agendamentos` mostra colunas por profissional, slots clicáveis abrem o modal pré-preenchendo data/hora/profissional, blocos de agendamento abrem o card de detalhes.
- Criação de agendamento valida: profissional/serviço obrigatórios, intervalo do expediente, não-passado, duração ≤ 300 min, não termina depois das 22h, sem conflito por profissional. Cada validação mostra a mensagem exata da seção 8.5.
- Quick-edit de horário e duração funciona no card sem fechar o modal em caso de erro.
- Exclusão remove links e agendamento e volta para a agenda do dia correspondente.
- Drag-and-drop das colunas funciona e persiste ordem no `localStorage` da chave `agendamentos:colOrder`.
- Errors HTMX 400 são exibidos dentro do modal/parcial sem que a página recarregue.
- Visual fiel à paleta bege/stone descrita na seção 6.
