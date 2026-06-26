import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.database import get_session
from app.security import (
    existe_algum_usuario,
    hash_senha,
    normalizar_nome_usuario,
    obter_usuario_por_nome,
    verificar_senha,
)
from app.models.usuario import Usuario
from app.templating import templates

router = APIRouter()

_RE_NOME = re.compile(r"^[a-z0-9._-]{3,30}$")


def _iniciar_sessao(request: Request, usuario: Usuario) -> None:
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    request.session["papel"] = usuario.papel
    request.session["nome_usuario"] = usuario.nome_usuario
    request.session["nome_exibicao"] = usuario.nome_exibicao or usuario.nome_usuario


def _validar_senha(senha: str, senha_confirmacao: str | None = None) -> str | None:
    if len(senha) > 200:
        return "Senha muito longa."
    if len(senha) < 6:
        return "A senha deve ter pelo menos 6 caracteres."
    if senha_confirmacao is not None and senha != senha_confirmacao:
        return "As senhas não conferem."
    return None


def _validar_nome(nome: str) -> str | None:
    if not _RE_NOME.match(nome):
        return (
            "Nome de usuário inválido. Use de 3 a 30 caracteres: "
            "letras minúsculas, números, ponto, hífen ou sublinhado."
        )
    return None


# ---------- Setup (primeiro acesso → cria o admin) ----------


@router.get("/setup")
def get_setup(request: Request, session: Session = Depends(get_session)):
    if existe_algum_usuario(session):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "auth/setup.html",
        {"request": request, "erro": None, "nome_usuario": ""},
    )


@router.post("/setup")
def post_setup(
    request: Request,
    nome_usuario: str = Form(...),
    senha: str = Form(...),
    senha_confirmacao: str = Form(...),
    session: Session = Depends(get_session),
):
    if existe_algum_usuario(session):
        return RedirectResponse(url="/login", status_code=303)

    nome = normalizar_nome_usuario(nome_usuario)
    erro = _validar_nome(nome) or _validar_senha(senha, senha_confirmacao)

    if erro:
        return templates.TemplateResponse(
            "auth/setup.html",
            {"request": request, "erro": erro, "nome_usuario": nome_usuario},
            status_code=400,
        )

    usuario = Usuario(
        nome_usuario=nome,
        senha_hash=hash_senha(senha),
        papel="admin",
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)

    _iniciar_sessao(request, usuario)
    return RedirectResponse(url="/", status_code=303)


# ---------- Login ----------


@router.get("/login")
def get_login(request: Request, session: Session = Depends(get_session)):
    if not existe_algum_usuario(session):
        return RedirectResponse(url="/setup", status_code=303)
    if request.session.get("usuario_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "erro": None, "nome_usuario": ""},
    )


@router.post("/login")
def post_login(
    request: Request,
    nome_usuario: str = Form(...),
    senha: str = Form(...),
    session: Session = Depends(get_session),
):
    if not existe_algum_usuario(session):
        return RedirectResponse(url="/setup", status_code=303)

    def _erro_generico():
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "erro": "Nome de usuário ou senha incorretos.",
                "nome_usuario": nome_usuario,
            },
            status_code=400,
        )

    if len(senha) > 200:
        return _erro_generico()

    usuario = obter_usuario_por_nome(session, nome_usuario)
    if not usuario or not usuario.ativo or not verificar_senha(senha, usuario.senha_hash):
        return _erro_generico()

    _iniciar_sessao(request, usuario)
    usuario.atualizado_em = datetime.now()
    session.add(usuario)
    session.commit()
    return RedirectResponse(url="/", status_code=303)


# ---------- Logout ----------


@router.post("/logout")
def post_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
