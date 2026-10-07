import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models.usuario import Usuario
from app.security import (
    PAPEIS_ATRIBUIVEIS,
    hash_senha,
    impressao_senha,
    normalizar_nome_usuario,
    obter_usuario_por_nome,
    pode_alterar_papel,
    pode_criar_com_papel,
    pode_gerenciar_alvo,
    pode_redefinir_senha,
    requer_admin,
)
from app.templating import templates

router = APIRouter(prefix="/usuarios", dependencies=[Depends(requer_admin)])

_RE_NOME = re.compile(r"^[a-z0-9._-]{3,30}$")


def _redirect(msg: str | None = None, erro: str | None = None) -> RedirectResponse:
    params = []
    if msg:
        params.append(f"msg={msg}")
    if erro:
        params.append(f"erro={erro}")
    url = "/usuarios" + ("?" + "&".join(params) if params else "")
    return RedirectResponse(url=url, status_code=303)


def _limpar(valor: str | None) -> str | None:
    if valor is None:
        return None
    v = valor.strip()
    return v or None


@router.get("")
def listar(
    request: Request,
    msg: str | None = None,
    erro: str | None = None,
    session: Session = Depends(get_session),
    ator: Usuario = Depends(requer_admin),
):
    usuarios = session.exec(
        select(Usuario).order_by(Usuario.papel, Usuario.nome_usuario)
    ).all()
    return templates.TemplateResponse(
        "usuarios/list.html",
        {
            "request": request,
            "active": "usuarios",
            "usuarios": usuarios,
            "ator": ator,
            "pode_alterar_papel": pode_alterar_papel(ator),
            "msg": msg,
            "erro": erro,
        },
    )


@router.post("")
def criar(
    nome_usuario: str = Form(...),
    senha: str = Form(...),
    papel: str = Form("comum"),
    nome_exibicao: str = Form(""),
    ator: Usuario = Depends(requer_admin),
    session: Session = Depends(get_session),
):
    nome = normalizar_nome_usuario(nome_usuario)
    if not _RE_NOME.match(nome):
        return _redirect(erro="Nome inválido (3-30: minúsculas, números, . _ -).")
    if papel not in PAPEIS_ATRIBUIVEIS:
        return _redirect(erro="Papel inválido.")
    if not pode_criar_com_papel(ator, papel):
        return _redirect(erro="Apenas o super admin pode criar administradores.")
    if len(senha) < 6 or len(senha) > 200:
        return _redirect(erro="A senha deve ter de 6 a 200 caracteres.")
    if obter_usuario_por_nome(session, nome):
        return _redirect(erro="Já existe um usuário com esse nome.")

    session.add(
        Usuario(
            nome_usuario=nome,
            nome_exibicao=_limpar(nome_exibicao),
            senha_hash=hash_senha(senha),
            papel=papel,
        )
    )
    session.commit()
    return _redirect(msg=f"Usuário '{nome}' criado.")


@router.post("/{usuario_id}/senha")
def redefinir_senha(
    request: Request,
    usuario_id: int,
    senha: str = Form(...),
    ator: Usuario = Depends(requer_admin),
    session: Session = Depends(get_session),
):
    alvo = session.get(Usuario, usuario_id)
    if alvo is None:
        return _redirect(erro="Usuário não encontrado.")
    ok, motivo = pode_redefinir_senha(ator, alvo)
    if not ok:
        return _redirect(erro=motivo or "Sem permissão.")
    if len(senha) < 6 or len(senha) > 200:
        return _redirect(erro="A senha deve ter de 6 a 200 caracteres.")
    alvo.senha_hash = hash_senha(senha)
    session.add(alvo)
    session.commit()
    # A troca derruba as sessões do alvo; quem trocou a própria senha continua logado.
    if alvo.id == ator.id:
        request.session["senha_fp"] = impressao_senha(alvo.senha_hash)
    return _redirect(msg=f"Senha de '{alvo.nome_usuario}' redefinida.")


@router.post("/{usuario_id}/papel")
def alterar_papel(
    usuario_id: int,
    papel: str = Form(...),
    ator: Usuario = Depends(requer_admin),
    session: Session = Depends(get_session),
):
    # Somente o superadmin altera papéis; e nunca para 'superadmin'.
    if not pode_alterar_papel(ator):
        return _redirect(erro="Apenas o super admin pode alterar papéis.")
    if papel not in PAPEIS_ATRIBUIVEIS:
        return _redirect(erro="Papel inválido.")
    alvo = session.get(Usuario, usuario_id)
    if alvo is None:
        return _redirect(erro="Usuário não encontrado.")
    if alvo.papel == "superadmin":
        return _redirect(erro="O papel do super admin não pode ser alterado.")
    alvo.papel = papel
    session.add(alvo)
    session.commit()
    return _redirect(msg=f"Papel de '{alvo.nome_usuario}' atualizado.")


@router.post("/{usuario_id}/ativo")
def alternar_ativo(
    usuario_id: int,
    ator: Usuario = Depends(requer_admin),
    session: Session = Depends(get_session),
):
    alvo = session.get(Usuario, usuario_id)
    if alvo is None:
        return _redirect(erro="Usuário não encontrado.")
    ok, motivo = pode_gerenciar_alvo(ator, alvo)
    if not ok:
        return _redirect(erro=motivo or "Sem permissão.")
    alvo.ativo = not alvo.ativo
    session.add(alvo)
    session.commit()
    estado = "ativado" if alvo.ativo else "desativado"
    return _redirect(msg=f"Usuário '{alvo.nome_usuario}' {estado}.")
