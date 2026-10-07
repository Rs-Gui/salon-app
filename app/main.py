from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.database import get_session, init_db
from app.models.agendamento import Agendamento
from app.routers import agendamentos as agendamentos_router
from app.routers import auth as auth_router
from app.routers import clientes as clientes_router
from app.routers import financeiro as financeiro_router
from app.routers import produtos as produtos_router
from app.routers import profissionais as profissionais_router
from app.routers import servicos as servicos_router
from app.routers import usuarios as usuarios_router
from app.security import (
    EM_PRODUCAO,
    RedirectRequired,
    SECRET_KEY,
    montar_resposta_redirect,
    requer_login,
)
from app.templating import templates

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Sem /docs, /redoc e /openapi.json: o app é só HTML e não precisa expor o mapa de rotas.
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="salao_session",
    same_site="lax",
    https_only=EM_PRODUCAO,
    max_age=None,
)


@app.middleware("http")
async def _cabecalhos_seguranca(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if EM_PRODUCAO:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(RedirectRequired)
async def _redirect_required_handler(request: Request, exc: RedirectRequired):
    return montar_resposta_redirect(exc)


# Routers públicos (sem requer_login)
app.include_router(auth_router.router)

# Routers protegidos (requer_login aplicado no próprio router)
app.include_router(agendamentos_router.router)
app.include_router(clientes_router.router)
app.include_router(profissionais_router.router)
app.include_router(servicos_router.router)
app.include_router(produtos_router.router)
app.include_router(financeiro_router.router)
app.include_router(usuarios_router.router)


# Home — protegida
@app.get("/")
def home(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(requer_login),
):
    """Painel inicial (v1 enxuta): contador de agendamentos de hoje +
    lista dos atendimentos a partir de agora. Reusa os helpers da agenda
    para resolver cliente/serviços/profissionais de cada agendamento.
    """
    agora = datetime.now()
    inicio_dia = datetime(agora.year, agora.month, agora.day)
    fim_dia = inicio_dia + timedelta(days=1)

    agendamentos_hoje = session.exec(
        select(Agendamento)
        .where(Agendamento.data_hora >= inicio_dia)
        .where(Agendamento.data_hora < fim_dia)
        .order_by(Agendamento.data_hora)
    ).all()

    proximos = []
    for ag in agendamentos_hoje:
        if ag.data_hora < agora:
            continue  # já passou — fica só na agenda do dia
        cliente = agendamentos_router._calcula_cliente(session, ag)
        servs = agendamentos_router._calcula_servicos(session, ag.id)
        profs = agendamentos_router._calcula_profissionais(session, ag.id)
        proximos.append(
            {
                "hora": ag.data_hora.strftime("%H:%M"),
                "cliente_nome": cliente.nome if cliente is not None else None,
                "servicos": [s.nome for s in servs],
                "profissionais": [p.nome for p in profs],
            }
        )

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "active": "home",
            "total_hoje": len(agendamentos_hoje),
            "proximos": proximos,
        },
    )
