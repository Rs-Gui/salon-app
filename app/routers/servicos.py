from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.servico import Servico
from app.security import requer_login
from app.templating import templates

router = APIRouter(prefix="/servicos", dependencies=[Depends(requer_login)])


def _vazio_para_none(valor):
    if valor is None:
        return None
    v = valor.strip()
    return v if v else None


def _parse_preco(valor):
    if valor is None:
        return 0.0
    v = valor.strip()
    if not v:
        return 0.0
    v = v.replace(",", ".")
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _parse_duracao(valor):
    if valor is None:
        return None
    v = valor.strip() if isinstance(valor, str) else valor
    if v == "" or v is None:
        return None
    try:
        n = int(v)
    except (ValueError, TypeError):
        return None
    if n <= 0:
        return None
    return n


def _servico_duplicado(session, nome, ignorar_id=None):
    if nome is None:
        return False
    nome_n = nome.strip().lower()
    if not nome_n:
        return False
    servicos = session.exec(select(Servico)).all()
    for s in servicos:
        if ignorar_id is not None and s.id == ignorar_id:
            continue
        if (s.nome or "").strip().lower() == nome_n:
            return True
    return False


def _validar_limites(nome, observacoes):
    if nome is not None and len(nome) > 200:
        return "Nome muito longo (máximo 200 caracteres)."
    if observacoes is not None and len(observacoes) > 2000:
        return "Observações muito longas (máximo 2000 caracteres)."
    return None


def _preco_formatado(preco: float) -> str:
    return "R$ " + ("%.2f" % (preco or 0.0)).replace(".", ",")


def _preco_input(preco: float) -> str:
    return ("%.2f" % (preco or 0.0)).replace(".", ",")


@router.get("/")
def lista(request: Request, session: Session = Depends(get_session)):
    servicos = session.exec(select(Servico).order_by(Servico.nome)).all()
    return templates.TemplateResponse(
        "servicos/lista.html",
        {
            "request": request,
            "active": "servicos",
            "servicos": servicos,
        },
    )


@router.get("/novo")
def novo(request: Request):
    return templates.TemplateResponse(
        "servicos/form.html",
        {
            "request": request,
            "active": "servicos",
            "titulo": "Novo Serviço",
            "action": "/servicos/",
            "servico": Servico(nome="", preco=0.0, duracao_minutos=30),
            "preco_input": "",
            "duracao_input": "",
            "erro": None,
        },
    )


@router.get("/{servico_id}/editar")
def editar(servico_id: int, request: Request, session: Session = Depends(get_session)):
    servico = session.get(Servico, servico_id)
    if servico is None:
        return RedirectResponse(url="/servicos/", status_code=303)
    return templates.TemplateResponse(
        "servicos/form.html",
        {
            "request": request,
            "active": "servicos",
            "titulo": "Editar Serviço",
            "action": f"/servicos/{servico.id}",
            "servico": servico,
            "preco_input": _preco_input(servico.preco),
            "duracao_input": str(servico.duracao_minutos),
            "erro": None,
        },
    )


@router.post("/")
def criar(
    request: Request,
    nome: str = Form(...),
    preco: str = Form(""),
    duracao_minutos: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    nome_limpo = nome.strip()
    preco_val = _parse_preco(preco)
    duracao_val = _parse_duracao(duracao_minutos)
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    erro = _validar_limites(nome_limpo, observacoes_n)
    if erro is None:
        if duracao_val is None:
            erro = "Duração é obrigatória e deve ser um número inteiro maior que zero."
        elif duracao_val < 15:
            erro = "Duração mínima é de 15 minutos."
        elif duracao_val > 300:
            erro = "Duração não pode passar de 300 minutos (5h)."
        elif _servico_duplicado(session, nome_limpo):
            erro = "Já existe um serviço com esse nome."

    if erro:
        servico_mem = Servico(
            nome=nome_limpo,
            preco=preco_val,
            duracao_minutos=duracao_val or 0,
            observacoes=observacoes_n,
        )
        return templates.TemplateResponse(
            "servicos/form.html",
            {
                "request": request,
                "active": "servicos",
                "titulo": "Novo Serviço",
                "action": "/servicos/",
                "servico": servico_mem,
                "preco_input": preco.strip() if preco else "",
                "duracao_input": duracao_minutos.strip() if duracao_minutos else "",
                "erro": erro,
            },
            status_code=400,
        )

    servico = Servico(
        nome=nome_limpo,
        preco=preco_val,
        duracao_minutos=duracao_val,
        observacoes=observacoes_n,
    )
    session.add(servico)
    session.commit()
    return RedirectResponse(url="/servicos/", status_code=303)


@router.post("/{servico_id}")
def atualizar(
    servico_id: int,
    request: Request,
    nome: str = Form(...),
    preco: str = Form(""),
    duracao_minutos: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    servico = session.get(Servico, servico_id)
    if servico is None:
        return RedirectResponse(url="/servicos/", status_code=303)

    nome_limpo = nome.strip()
    preco_val = _parse_preco(preco)
    duracao_val = _parse_duracao(duracao_minutos)
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    erro = _validar_limites(nome_limpo, observacoes_n)
    if erro is None:
        if duracao_val is None:
            erro = "Duração é obrigatória e deve ser um número inteiro maior que zero."
        elif duracao_val < 15:
            erro = "Duração mínima é de 15 minutos."
        elif duracao_val > 300:
            erro = "Duração não pode passar de 300 minutos (5h)."
        elif _servico_duplicado(session, nome_limpo, ignorar_id=servico.id):
            erro = "Já existe um serviço com esse nome."

    if erro:
        servico_mem = Servico(
            id=servico.id,
            nome=nome_limpo,
            preco=preco_val,
            duracao_minutos=duracao_val or 0,
            observacoes=observacoes_n,
            ativo=servico.ativo,
        )
        return templates.TemplateResponse(
            "servicos/form.html",
            {
                "request": request,
                "active": "servicos",
                "titulo": "Editar Serviço",
                "action": f"/servicos/{servico.id}",
                "servico": servico_mem,
                "preco_input": preco.strip() if preco else "",
                "duracao_input": duracao_minutos.strip() if duracao_minutos else "",
                "erro": erro,
            },
            status_code=400,
        )

    servico.nome = nome_limpo
    servico.preco = preco_val
    servico.duracao_minutos = duracao_val
    servico.observacoes = observacoes_n
    session.add(servico)
    session.commit()
    return RedirectResponse(url="/servicos/", status_code=303)


@router.post("/{servico_id}/desativar")
def desativar(servico_id: int, session: Session = Depends(get_session)):
    servico = session.get(Servico, servico_id)
    if servico is not None:
        servico.ativo = False
        session.add(servico)
        session.commit()
    return RedirectResponse(url="/servicos/", status_code=303)


@router.post("/{servico_id}/reativar")
def reativar(servico_id: int, session: Session = Depends(get_session)):
    servico = session.get(Servico, servico_id)
    if servico is not None:
        servico.ativo = True
        session.add(servico)
        session.commit()
    return RedirectResponse(url="/servicos/", status_code=303)
