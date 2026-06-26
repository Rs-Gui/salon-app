import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.cliente import Cliente
from app.security import requer_login
from app.templating import templates

router = APIRouter(prefix="/clientes", dependencies=[Depends(requer_login)])

_RE_TELEFONE = re.compile(r"^\d{8,15}$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _vazio_para_none(valor):
    if valor is None:
        return None
    v = valor.strip()
    return v if v else None


def _normalizar(valor, *, lower=False):
    if valor is None:
        return None
    v = valor.strip()
    if not v:
        return None
    if lower:
        v = v.lower()
    return v


def _validar_contato(telefone, email):
    if telefone is not None and not _RE_TELEFONE.match(telefone):
        return "Telefone deve conter apenas números (8 a 15 dígitos)."
    if email is not None and not _RE_EMAIL.match(email):
        return "E-mail inválido. Use o formato exemplo@dominio.com."
    return None


def _validar_limites(nome, email, observacoes):
    if nome is not None and len(nome) > 200:
        return "Nome muito longo (máximo 200 caracteres)."
    if email is not None and len(email) > 200:
        return "E-mail muito longo (máximo 200 caracteres)."
    if observacoes is not None and len(observacoes) > 2000:
        return "Observações muito longas (máximo 2000 caracteres)."
    return None


def _cliente_duplicado(session, nome, email, telefone, ignorar_id=None):
    nome_n = _normalizar(nome, lower=True)
    email_n = _normalizar(email, lower=True)
    tel_n = _normalizar(telefone)
    clientes = session.exec(select(Cliente)).all()
    for c in clientes:
        if ignorar_id is not None and c.id == ignorar_id:
            continue
        if (
            _normalizar(c.nome, lower=True) == nome_n
            and _normalizar(c.email, lower=True) == email_n
            and _normalizar(c.telefone) == tel_n
        ):
            return True
    return False


@router.get("/")
def lista(request: Request, session: Session = Depends(get_session)):
    clientes = session.exec(select(Cliente).order_by(Cliente.nome)).all()
    return templates.TemplateResponse(
        "clientes/lista.html",
        {"request": request, "active": "clientes", "clientes": clientes},
    )


@router.get("/novo")
def novo(request: Request):
    return templates.TemplateResponse(
        "clientes/form.html",
        {
            "request": request,
            "active": "clientes",
            "titulo": "Novo Cliente",
            "action": "/clientes/",
            "cliente": Cliente(nome=""),
            "erro": None,
        },
    )


@router.get("/{cliente_id}/editar")
def editar(cliente_id: int, request: Request, session: Session = Depends(get_session)):
    cliente = session.get(Cliente, cliente_id)
    if cliente is None:
        return RedirectResponse(url="/clientes/", status_code=303)
    return templates.TemplateResponse(
        "clientes/form.html",
        {
            "request": request,
            "active": "clientes",
            "titulo": "Editar Cliente",
            "action": f"/clientes/{cliente.id}",
            "cliente": cliente,
            "erro": None,
        },
    )


@router.post("/")
def criar(
    request: Request,
    nome: str = Form(...),
    telefone: str = Form(""),
    email: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    nome_limpo = nome.strip()
    telefone_n = _vazio_para_none(telefone)
    if telefone_n is not None and len(telefone_n) > 15:
        telefone_n = telefone_n[:15]
    email_n = _vazio_para_none(email)
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    erro = _validar_limites(nome_limpo, email_n, observacoes_n)
    if erro is None:
        erro = _validar_contato(telefone_n, email_n)
    if erro is None:
        if _cliente_duplicado(session, nome_limpo, email_n, telefone_n):
            erro = "Já existe um cliente com esse mesmo nome, e-mail e telefone."

    if erro:
        cliente_mem = Cliente(
            nome=nome_limpo,
            telefone=telefone_n,
            email=email_n,
            observacoes=observacoes_n,
        )
        return templates.TemplateResponse(
            "clientes/form.html",
            {
                "request": request,
                "active": "clientes",
                "titulo": "Novo Cliente",
                "action": "/clientes/",
                "cliente": cliente_mem,
                "erro": erro,
            },
            status_code=400,
        )

    cliente = Cliente(
        nome=nome_limpo,
        telefone=telefone_n,
        email=email_n,
        observacoes=observacoes_n,
    )
    session.add(cliente)
    session.commit()
    return RedirectResponse(url="/clientes/", status_code=303)


@router.post("/{cliente_id}")
def atualizar(
    cliente_id: int,
    request: Request,
    nome: str = Form(...),
    telefone: str = Form(""),
    email: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    cliente = session.get(Cliente, cliente_id)
    if cliente is None:
        return RedirectResponse(url="/clientes/", status_code=303)

    nome_limpo = nome.strip()
    telefone_n = _vazio_para_none(telefone)
    if telefone_n is not None and len(telefone_n) > 15:
        telefone_n = telefone_n[:15]
    email_n = _vazio_para_none(email)
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    erro = _validar_limites(nome_limpo, email_n, observacoes_n)
    if erro is None:
        erro = _validar_contato(telefone_n, email_n)
    if erro is None:
        if _cliente_duplicado(
            session, nome_limpo, email_n, telefone_n, ignorar_id=cliente.id
        ):
            erro = "Já existe um cliente com esse mesmo nome, e-mail e telefone."

    if erro:
        cliente_mem = Cliente(
            id=cliente.id,
            nome=nome_limpo,
            telefone=telefone_n,
            email=email_n,
            observacoes=observacoes_n,
            ativo=cliente.ativo,
        )
        return templates.TemplateResponse(
            "clientes/form.html",
            {
                "request": request,
                "active": "clientes",
                "titulo": "Editar Cliente",
                "action": f"/clientes/{cliente.id}",
                "cliente": cliente_mem,
                "erro": erro,
            },
            status_code=400,
        )

    cliente.nome = nome_limpo
    cliente.telefone = telefone_n
    cliente.email = email_n
    cliente.observacoes = observacoes_n
    session.add(cliente)
    session.commit()
    return RedirectResponse(url="/clientes/", status_code=303)


@router.post("/{cliente_id}/desativar")
def desativar(cliente_id: int, session: Session = Depends(get_session)):
    cliente = session.get(Cliente, cliente_id)
    if cliente is not None:
        cliente.ativo = False
        session.add(cliente)
        session.commit()
    return RedirectResponse(url="/clientes/", status_code=303)


@router.post("/{cliente_id}/reativar")
def reativar(cliente_id: int, session: Session = Depends(get_session)):
    cliente = session.get(Cliente, cliente_id)
    if cliente is not None:
        cliente.ativo = True
        session.add(cliente)
        session.commit()
    return RedirectResponse(url="/clientes/", status_code=303)
