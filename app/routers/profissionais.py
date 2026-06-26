import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models.agendamento import AgendamentoProfissional
from app.models.profissional import Profissional
from app.security import requer_login
from app.templating import templates

router = APIRouter(prefix="/profissionais", dependencies=[Depends(requer_login)])

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


def _agendamentos_com_unico_ativo(session: Session, profissional_id) -> int:
    links = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.profissional_id == profissional_id
        )
    ).all()
    ag_ids = [l.agendamento_id for l in links]
    bloqueados = 0
    for ag_id in ag_ids:
        outros_links = session.exec(
            select(AgendamentoProfissional).where(
                AgendamentoProfissional.agendamento_id == ag_id,
                AgendamentoProfissional.profissional_id != profissional_id,
            )
        ).all()
        outros_ids = [l.profissional_id for l in outros_links]
        ativos_restantes = 0
        if outros_ids:
            outros = session.exec(
                select(Profissional).where(Profissional.id.in_(outros_ids))
            ).all()
            ativos_restantes = sum(1 for p in outros if p.ativo)
        if ativos_restantes == 0:
            bloqueados += 1
    return bloqueados


def _profissional_duplicado(
    session: Session,
    nome,
    email,
    telefone,
    ignorar_id=None,
) -> bool:
    nome_n = _normalizar(nome, lower=True)
    email_n = _normalizar(email, lower=True)
    tel_n = _normalizar(telefone)
    todos = session.exec(select(Profissional)).all()
    for p in todos:
        if ignorar_id is not None and p.id == ignorar_id:
            continue
        if (
            _normalizar(p.nome, lower=True) == nome_n
            and _normalizar(p.email, lower=True) == email_n
            and _normalizar(p.telefone) == tel_n
        ):
            return True
    return False


@router.get("/")
def lista(request: Request, session: Session = Depends(get_session)):
    profissionais = session.exec(select(Profissional).order_by(Profissional.nome)).all()
    return templates.TemplateResponse(
        "profissionais/lista.html",
        {
            "request": request,
            "active": "profissionais",
            "profissionais": profissionais,
            "erro": None,
        },
    )


@router.get("/novo")
def novo(request: Request):
    return templates.TemplateResponse(
        "profissionais/form.html",
        {
            "request": request,
            "active": "profissionais",
            "titulo": "Novo Profissional",
            "action": "/profissionais/",
            "profissional": Profissional(nome=""),
            "erro": None,
        },
    )


@router.get("/{profissional_id}/editar")
def editar(
    profissional_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    profissional = session.get(Profissional, profissional_id)
    if profissional is None:
        return RedirectResponse(url="/profissionais/", status_code=303)
    return templates.TemplateResponse(
        "profissionais/form.html",
        {
            "request": request,
            "active": "profissionais",
            "titulo": "Editar Profissional",
            "action": f"/profissionais/{profissional.id}",
            "profissional": profissional,
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
    nome_limpo = (nome or "").strip()
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
    if erro is None and _profissional_duplicado(
        session, nome_limpo, email_n, telefone_n
    ):
        erro = "Já existe um profissional com esse mesmo nome, e-mail e telefone."

    if erro:
        profissional_mem = Profissional(
            nome=nome_limpo,
            telefone=telefone_n,
            email=email_n,
            observacoes=observacoes_n,
        )
        return templates.TemplateResponse(
            "profissionais/form.html",
            {
                "request": request,
                "active": "profissionais",
                "titulo": "Novo Profissional",
                "action": "/profissionais/",
                "profissional": profissional_mem,
                "erro": erro,
            },
            status_code=400,
        )

    profissional = Profissional(
        nome=nome_limpo,
        telefone=telefone_n,
        email=email_n,
        observacoes=observacoes_n,
    )
    session.add(profissional)
    session.commit()
    return RedirectResponse(url="/profissionais/", status_code=303)


@router.post("/{profissional_id}")
def atualizar(
    profissional_id: int,
    request: Request,
    nome: str = Form(...),
    telefone: str = Form(""),
    email: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    profissional = session.get(Profissional, profissional_id)
    if profissional is None:
        return RedirectResponse(url="/profissionais/", status_code=303)

    nome_limpo = (nome or "").strip()
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
    if erro is None and _profissional_duplicado(
        session, nome_limpo, email_n, telefone_n, ignorar_id=profissional.id
    ):
        erro = "Já existe um profissional com esse mesmo nome, e-mail e telefone."

    if erro:
        profissional_mem = Profissional(
            id=profissional.id,
            nome=nome_limpo,
            telefone=telefone_n,
            email=email_n,
            observacoes=observacoes_n,
            ativo=profissional.ativo,
            criado_em=profissional.criado_em,
        )
        return templates.TemplateResponse(
            "profissionais/form.html",
            {
                "request": request,
                "active": "profissionais",
                "titulo": "Editar Profissional",
                "action": f"/profissionais/{profissional.id}",
                "profissional": profissional_mem,
                "erro": erro,
            },
            status_code=400,
        )

    profissional.nome = nome_limpo
    profissional.telefone = telefone_n
    profissional.email = email_n
    profissional.observacoes = observacoes_n
    session.add(profissional)
    session.commit()
    return RedirectResponse(url="/profissionais/", status_code=303)


@router.post("/{profissional_id}/desativar")
def desativar(
    profissional_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    profissional = session.get(Profissional, profissional_id)
    if profissional is None:
        return RedirectResponse(url="/profissionais/", status_code=303)

    # Bloqueia desativação se este profissional é o único ativo em algum agendamento.
    bloqueados = _agendamentos_com_unico_ativo(session, profissional.id)

    if bloqueados > 0:
        profissionais = session.exec(
            select(Profissional).order_by(Profissional.nome)
        ).all()
        erro = (
            f"Não é possível desativar {profissional.nome}: ele é o único "
            f"profissional ativo em {bloqueados} agendamento(s). "
            "Reatribua ou exclua antes."
        )
        return templates.TemplateResponse(
            "profissionais/lista.html",
            {
                "request": request,
                "active": "profissionais",
                "profissionais": profissionais,
                "erro": erro,
            },
            status_code=400,
        )

    profissional.ativo = False
    session.add(profissional)
    session.commit()
    return RedirectResponse(url="/profissionais/", status_code=303)


@router.post("/{profissional_id}/reativar")
def reativar(profissional_id: int, session: Session = Depends(get_session)):
    profissional = session.get(Profissional, profissional_id)
    if profissional is not None:
        profissional.ativo = True
        session.add(profissional)
        session.commit()
    return RedirectResponse(url="/profissionais/", status_code=303)


@router.post("/{profissional_id}/excluir")
def excluir(profissional_id: int, session: Session = Depends(get_session)):
    profissional = session.get(Profissional, profissional_id)
    if profissional is None:
        return RedirectResponse(url="/profissionais/", status_code=303)

    if profissional.ativo:
        return Response(
            content="Só é possível excluir profissionais desativados.",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )

    # Defesa em profundidade: garantir que não é "único ativo" em nenhum agendamento.
    # Em tese impossível (já está inativo), mas valida mesmo assim.
    bloqueados = _agendamentos_com_unico_ativo(session, profissional.id)

    if bloqueados > 0:
        return Response(
            content=(
                f"Não é possível excluir: profissional é o único ativo em "
                f"{bloqueados} agendamento(s). Reagende ou exclua o(s) "
                "agendamento(s) primeiro."
            ),
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )

    # Transação única: snapshot do nome em todos os link rows + delete do profissional.
    links_proprios = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.profissional_id == profissional.id
        )
    ).all()
    for link in links_proprios:
        link.nome_snapshot = profissional.nome
        session.add(link)
    session.flush()
    session.delete(profissional)
    session.commit()
    return RedirectResponse(url="/profissionais/", status_code=303)
