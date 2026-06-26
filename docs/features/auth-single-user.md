# Feature: Autenticação single-user com senha

Status: 🚧 EM ANDAMENTO — iniciado 2026-05-14

## Contexto e desvio do spec
`implementação.md` explicitamente diz "sem login/autenticação". Esta feature **revoga essa decisão** a pedido do usuário: o app passa a ter **um único usuário** protegido por senha. Não há cadastro de múltiplos usuários, não há recuperação por email, não há "esqueci a senha" (uso local).

## Resumo
- Existe exatamente **um** usuário no sistema.
- No primeiro start (banco sem usuário), `GET /` redireciona para `GET /setup` onde a dona define a senha.
- Depois, qualquer rota protegida exige sessão válida; sem sessão → redireciona para `GET /login`.
- Logout em `POST /logout` limpa a sessão e volta para `/login`.

## Decisões técnicas

### Armazenamento
Tabela nova `usuario`:
```python
class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    senha_hash: str
    criado_em: datetime = Field(default_factory=datetime.now)
    atualizado_em: datetime = Field(default_factory=datetime.now)
```
Invariante: no máximo **uma linha**. O código deve aplicar isso (não criar segunda linha; troca de senha = update da existente).

### Hash de senha
- `passlib[bcrypt]` (adicionar em `requirements.txt`).
- `bcrypt` com rounds padrão (12).

### Sessão
- `starlette.middleware.sessions.SessionMiddleware`.
- `secret_key` lido de variável de ambiente `SALAO_SECRET_KEY`; se ausente, **gerar e persistir** em arquivo `.secret_key` na raiz do projeto na primeira execução (chmod 600 quando possível). Não versionar.
- Sessão guarda apenas `{"autenticado": True}`. Cookie httpOnly, `same_site="lax"`, **sem `max_age`** → vira session cookie (expira ao fechar o navegador). Configurar `SessionMiddleware(..., max_age=None)`.

### Dependency de proteção
```python
def requer_login(request: Request):
    if not request.session.get("autenticado"):
        # 303 redirect para /login preservando ?next= seria ideal,
        # mas para HTMX precisamos responder com HX-Redirect.
        ...
```
Comportamento:
- Request comum → `RedirectResponse("/login", 303)`.
- Request HTMX (header `HX-Request: true`) → `Response(status_code=401, headers={"HX-Redirect": "/login"})`.

Aplicar essa dependency em **todos os routers existentes** (`clientes`, `profissionais`, `servicos`, `agendamentos`, `home`). Exceções: `/login`, `/setup`, `/logout`, `/static`.

### Rotas novas (`app/routers/auth.py`)

| Método | URL | Descrição |
|---|---|---|
| GET | `/setup` | Form de criação da senha. Se já existe usuário, redireciona 303 para `/login`. |
| POST | `/setup` | Cria o usuário (valida: 2 campos `senha` e `senha_confirmacao` iguais, min 6 chars). Faz login automático (seta sessão) e redireciona 303 para `/`. Se já existe usuário, ignora e redireciona para `/login`. |
| GET | `/login` | Form de login. Se não há usuário, redireciona 303 para `/setup`. Se já autenticado, redireciona 303 para `/`. |
| POST | `/login` | Confere senha. Sucesso → seta sessão + 303 para `/`. Falha → re-renderiza `/login` com status 400 e erro "Senha incorreta.". |
| POST | `/logout` | Limpa sessão e redireciona 303 para `/login`. |

### Templates novos
- `app/templates/auth/login.html` — extends `base_auth.html` (layout sem sidebar). Mensagem de erro literal: "Senha incorreta."
- `app/templates/auth/setup.html` — idem. Validações:
  - Senha < 6 chars → "A senha deve ter pelo menos 6 caracteres."
  - Confirmação diferente → "As senhas não conferem."
- `app/templates/base_auth.html` — layout minimalista centralizado (mesma paleta da seção 6 do spec principal), só header com "SalaoApp" e card centralizado.

### Modificações em arquivos existentes (a serem produzidos na onda 1)
- `app/main.py`: adicionar `SessionMiddleware`, registrar `auth` router, aplicar dependency `requer_login` aos demais.
- `app/templates/base.html`: no **rodapé da sidebar** (não no header), adicionar botão "Sair" como `<form method="post" action="/logout">` estilizado igual aos demais itens da nav, mas separado visualmente (border-top + `mt-auto`). A sidebar precisa virar flex-column com altura total para o "Sair" ficar grudado no fim.
- `app/database.py`: importar `usuario` em `init_db`, e em `_migrar_schema` garantir que a tabela existe (já coberto por `create_all`).

### Helpers
```python
def hash_senha(senha: str) -> str
def verificar_senha(senha: str, senha_hash: str) -> bool
def existe_usuario(session) -> bool
def obter_usuario(session) -> Usuario | None
```

## Plano de delegação

Esta feature **antecede** a Onda 2 do plano principal (`salao-app.md`), porque ela toca em `main.py` e `base.html` e adiciona dependency que precisa estar em todos os routers desde o início.

**Reordenação do roadmap:**
1. **Onda 1 (Bootstrap)** — produzir base + auth juntos. Agente backend-architect.
2. **Onda 2 (CRUDs)** — 3 agentes paralelos, cada um já aplica `Depends(requer_login)` no router.
3. **Onda 3 (Agendamentos backend)** — idem, com `Depends(requer_login)`.
4. **Onda 4 (Agendamentos frontend)** — sem mudanças.
5. **Onda 5 (auditoria)** — security-auditor com foco extra em: força do hash, fixação de sessão, CSRF nos POSTs (mitigado por SameSite=Lax, mas auditar), timing-safe compare, secret_key handling.

## Critério de aceite
- Banco vazio → `GET /` redireciona para `/setup`.
- Após `/setup`, usuário é criado, sessão é setada, e `/` mostra a home.
- Logout → `/login`. Sem sessão, qualquer rota protegida redireciona para `/login`.
- Senha errada mostra "Senha incorreta." no form com 400.
- Tentar acessar `/setup` quando já existe usuário cai em `/login`.
- Cookie de sessão é httpOnly e SameSite=Lax.
- `requirements.txt` inclui `passlib[bcrypt]` e `itsdangerous` (dep do SessionMiddleware).
