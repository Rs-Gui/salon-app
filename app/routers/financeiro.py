from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models.agendamento import Agendamento
from app.models.categoria_financeira import CategoriaFinanceira
from app.models.lancamento_financeiro import LancamentoFinanceiro
from app.models.profissional import Profissional
from app.models.usuario import Usuario
from app.routers.agendamentos import (
    _calcula_cliente,
    _calcula_profissionais,
    _estornar_pagamento,
)
from app.security import requer_login
from app.templating import templates

router = APIRouter(prefix="/financeiro", dependencies=[Depends(requer_login)])

_TIPOS_VALIDOS = {"receita", "despesa"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vazio_para_none(valor):
    if valor is None:
        return None
    v = valor.strip()
    return v if v else None


def _parse_valor(valor):
    """Retorna (valor_float, eh_invalido). Aceita vírgula. Exige > 0."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 0.0, True
    v = valor.strip().replace(".", "").replace(",", ".") if "," in valor else valor.strip()
    try:
        f = float(v)
    except (ValueError, TypeError):
        return 0.0, True
    if f <= 0:
        return 0.0, True
    return round(f, 2), False


def _parse_data(valor) -> date | None:
    v = (valor or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_mes(valor) -> date:
    """Primeiro dia do mês pedido (YYYY-MM). Default: mês corrente."""
    v = (valor or "").strip()
    if v:
        try:
            return datetime.strptime(v, "%Y-%m").date().replace(day=1)
        except ValueError:
            pass
    hoje = date.today()
    return hoje.replace(day=1)


def _proximo_mes(primeiro: date) -> date:
    if primeiro.month == 12:
        return primeiro.replace(year=primeiro.year + 1, month=1)
    return primeiro.replace(month=primeiro.month + 1)


def _mes_anterior(primeiro: date) -> date:
    if primeiro.month == 1:
        return primeiro.replace(year=primeiro.year - 1, month=12)
    return primeiro.replace(month=primeiro.month - 1)


_MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _rotulo_mes(primeiro: date) -> str:
    return f"{_MESES_PT[primeiro.month - 1].capitalize()} {primeiro.year}"


def _categorias(session: Session, tipo: str | None = None, *, so_ativas=True):
    stmt = select(CategoriaFinanceira)
    if tipo is not None:
        stmt = stmt.where(CategoriaFinanceira.tipo == tipo)
    if so_ativas:
        stmt = stmt.where(CategoriaFinanceira.ativo == True)  # noqa: E712
    return session.exec(stmt.order_by(CategoriaFinanceira.nome)).all()


def _mapa_categorias(session: Session) -> dict[int, CategoriaFinanceira]:
    return {c.id: c for c in session.exec(select(CategoriaFinanceira)).all()}


def _categoria_em_uso(session: Session, categoria_id: int) -> bool:
    return (
        session.exec(
            select(LancamentoFinanceiro.id)
            .where(LancamentoFinanceiro.categoria_id == categoria_id)
            .limit(1)
        ).first()
        is not None
    )


# ---------------------------------------------------------------------------
# Painel + lista de lançamentos
# ---------------------------------------------------------------------------


@router.get("/")
def lista(
    request: Request,
    mes: str | None = None,
    session: Session = Depends(get_session),
):
    primeiro = _parse_mes(mes)
    proximo = _proximo_mes(primeiro)

    lancamentos = session.exec(
        select(LancamentoFinanceiro)
        .where(LancamentoFinanceiro.data >= primeiro)
        .where(LancamentoFinanceiro.data < proximo)
        .order_by(LancamentoFinanceiro.data.desc(), LancamentoFinanceiro.id.desc())
    ).all()

    cats = _mapa_categorias(session)

    total_entradas = 0.0
    total_saidas = 0.0
    entradas_por_cat: dict[str, float] = {}
    n_despesas = 0
    linhas = []
    for l in lancamentos:
        cat = cats.get(l.categoria_id)
        # Categoria viva (reflete renomeações) → senão o snapshot deixado na remoção → senão "—".
        cat_nome = cat.nome if cat is not None else (l.categoria_nome or "—")
        if l.tipo == "receita":
            total_entradas += l.valor
            entradas_por_cat[cat_nome] = entradas_por_cat.get(cat_nome, 0.0) + l.valor
        else:
            total_saidas += l.valor
            n_despesas += 1
        linhas.append(
            {
                "id": l.id,
                "tipo": l.tipo,
                "valor": l.valor,
                "data": l.data,
                "data_fmt": l.data.strftime("%d/%m"),
                "categoria": cat_nome,
                "descricao": l.descricao or ("Receita" if l.tipo == "receita" else "Despesa"),
                "do_agendamento": l.agendamento_id is not None,
                "usuario": l.usuario_nome,
            }
        )

    # Top categorias de entrada (para o resumo do card "Entradas").
    top_entradas = sorted(entradas_por_cat.items(), key=lambda kv: kv[1], reverse=True)[:2]

    return templates.TemplateResponse(
        "financeiro/lista.html",
        {
            "request": request,
            "active": "financeiro",
            "linhas": linhas,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "saldo": total_entradas - total_saidas,
            "n_despesas": n_despesas,
            "top_entradas": top_entradas,
            "mes_str": primeiro.strftime("%Y-%m"),
            "mes_label": _rotulo_mes(primeiro),
            "mes_anterior": _mes_anterior(primeiro).strftime("%Y-%m"),
            "mes_proximo": proximo.strftime("%Y-%m"),
            "total_lancamentos": len(linhas),
        },
    )


# ---------------------------------------------------------------------------
# Comandas — receitas de agendamento reagrupadas por atendimento
# ---------------------------------------------------------------------------
#
# Uma comanda = todos os lançamentos de receita de um mesmo agendamento_id
# (serviços + produtos, cada um com bruto/desconto/líquido). Histórico completo.


def _linha_comanda(l: LancamentoFinanceiro, cats: dict) -> dict:
    bruto = l.valor_bruto if l.valor_bruto is not None else l.valor
    desc = l.desconto_valor or 0.0
    pct = None
    if l.desconto_tipo == "pct" and bruto:
        pct = round(desc / bruto * 100)
    cat = cats.get(l.categoria_id)
    cat_nome = cat.nome if cat is not None else (l.categoria_nome or "")
    return {
        "nome": l.descricao or "Item",
        "bruto": bruto,
        "desconto": desc,
        "tipo": l.desconto_tipo,
        "pct": pct,
        "liquido": l.valor,
        "is_produto": cat_nome == "Produtos",
    }


def _comanda_de(session: Session, ag_id: int, lancs: list, cats: dict) -> dict:
    ag = session.get(Agendamento, ag_id)
    cliente = _calcula_cliente(session, ag) if ag is not None else None
    profs = _calcula_profissionais(session, ag.id) if ag is not None else []
    linhas = [_linha_comanda(l, cats) for l in lancs]
    servicos = [x for x in linhas if not x["is_produto"]]
    produtos = [x for x in linhas if x["is_produto"]]
    data = max((l.data for l in lancs), default=None)
    # Autoria: os lançamentos de uma comanda são criados juntos no pagamento,
    # então o usuário é o mesmo — pega o primeiro não-nulo.
    usuario = next((l.usuario_nome for l in lancs if l.usuario_nome), None)
    return {
        "agendamento_id": ag_id,
        "cliente": cliente.nome if cliente is not None else "— Sem cliente —",
        "profissionais": [p.nome for p in profs],
        "usuario": usuario,
        "data": data,
        "data_fmt": data.strftime("%d/%m/%y") if data else "—",
        "data_iso": data.isoformat() if data else "",
        "hora": ag.data_hora.strftime("%H:%M") if ag is not None else "",
        "servicos": servicos,
        "produtos": produtos,
        "n_serv": len(servicos),
        "n_prod": sum(1 for _ in produtos),
        "bruto": sum(x["bruto"] for x in linhas),
        "desconto": sum(x["desconto"] for x in linhas),
        "total": sum(x["liquido"] for x in linhas),
        "sub_serv": sum(x["liquido"] for x in servicos),
        "sub_prod": sum(x["liquido"] for x in produtos),
    }


def _grupos_comanda(session: Session) -> list:
    """Todas as comandas (receitas de agendamento), mais recente primeiro."""
    lancs = session.exec(
        select(LancamentoFinanceiro)
        .where(LancamentoFinanceiro.agendamento_id != None)  # noqa: E711
        .where(LancamentoFinanceiro.tipo == "receita")
        .order_by(LancamentoFinanceiro.data.desc(), LancamentoFinanceiro.id.desc())
    ).all()
    cats = _mapa_categorias(session)
    grupos: dict[int, list] = {}
    for l in lancs:
        grupos.setdefault(l.agendamento_id, []).append(l)
    comandas = [_comanda_de(session, aid, ls, cats) for aid, ls in grupos.items()]
    comandas.sort(key=lambda c: (c["data"] or date.min), reverse=True)
    return comandas


@router.get("/comandas")
def comandas(request: Request, session: Session = Depends(get_session)):
    comandas = _grupos_comanda(session)
    faturado = sum(c["total"] for c in comandas)
    return templates.TemplateResponse(
        "financeiro/comandas.html",
        {
            "request": request,
            "active": "financeiro",
            "comandas": comandas,
            "n_comandas": len(comandas),
            "faturado": faturado,
            "fat_serv": sum(c["sub_serv"] for c in comandas),
            "fat_prod": sum(c["sub_prod"] for c in comandas),
            "desconto_total": sum(c["desconto"] for c in comandas),
            "ticket": faturado / len(comandas) if comandas else 0.0,
        },
    )


@router.get("/comandas/{agendamento_id:int}")
def comanda_detalhe(
    agendamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    lancs = session.exec(
        select(LancamentoFinanceiro)
        .where(LancamentoFinanceiro.agendamento_id == agendamento_id)
        .where(LancamentoFinanceiro.tipo == "receita")
        .order_by(LancamentoFinanceiro.id)
    ).all()
    if not lancs:
        return Response(
            "<p style='padding:8px'>Comanda não encontrada (pagamento estornado).</p>",
            status_code=404,
            media_type="text/html",
        )
    cats = _mapa_categorias(session)
    comanda = _comanda_de(session, agendamento_id, lancs, cats)
    return templates.TemplateResponse(
        "financeiro/_comanda_modal.html",
        {"request": request, "c": comanda},
    )


@router.post("/comandas/{agendamento_id:int}/estornar")
def comanda_estornar(
    agendamento_id: int,
    session: Session = Depends(get_session),
):
    _estornar_pagamento(session, agendamento_id)
    session.commit()
    # Recarrega a lista de comandas (o pagamento deixou de existir).
    return Response(status_code=204, headers={"HX-Refresh": "true"})


# ---------------------------------------------------------------------------
# Comissões — serviços pagos agrupados por profissional (3ª aba do Financeiro)
# ---------------------------------------------------------------------------
#
# Relatório SÓ-LEITURA: por profissional, os serviços JÁ PAGOS no mês, pelo
# valor LÍQUIDO recebido. Produtos NÃO entram. Atendimento com mais de um
# profissional credita o serviço a CADA um (marcado "compartilhado"). Pagar a
# comissão = lançar uma despesa no Financeiro (botão "Lançar pagamento" no modal,
# que abre /financeiro/novo já com descrição e valor). Sem cálculo de % e sem
# alteração de banco — só lê o que já existe.


def _comissoes_do_mes(session: Session, primeiro: date, proximo: date) -> list:
    lancs = session.exec(
        select(LancamentoFinanceiro)
        .where(LancamentoFinanceiro.tipo == "receita")
        .where(LancamentoFinanceiro.agendamento_id != None)  # noqa: E711
        .where(LancamentoFinanceiro.data >= primeiro)
        .where(LancamentoFinanceiro.data < proximo)
        .order_by(LancamentoFinanceiro.data, LancamentoFinanceiro.id)
    ).all()
    cats = _mapa_categorias(session)
    ag_cache: dict = {}      # agendamento_id -> (profissionais, cliente)
    por_prof: dict = {}      # profissional_id -> dados agregados
    for l in lancs:
        cat = cats.get(l.categoria_id)
        cat_nome = cat.nome if cat is not None else (l.categoria_nome or "")
        if cat_nome != "Serviços":
            continue  # produtos/outros não entram em comissão
        ag_id = l.agendamento_id
        if ag_id not in ag_cache:
            ag = session.get(Agendamento, ag_id)
            profs = _calcula_profissionais(session, ag_id) if ag is not None else []
            cliente = _calcula_cliente(session, ag) if ag is not None else None
            ag_cache[ag_id] = (profs, cliente)
        profs, cliente = ag_cache[ag_id]
        shared = len(profs) > 1
        for p in profs:
            d = por_prof.setdefault(p.id, {
                "id": p.id, "nome": p.nome, "ativo": p.ativo,
                "total": 0.0, "servicos": [],
            })
            d["total"] += l.valor
            d["servicos"].append({
                "data_fmt": l.data.strftime("%d/%m"),
                "servico": l.descricao or "Serviço",
                "cliente": cliente.nome if cliente is not None else "Sem cliente",
                "valor": l.valor,
                "shared": shared,
                "com": ", ".join(x.nome for x in profs if x.id != p.id),
            })
    return sorted(
        por_prof.values(),
        key=lambda d: (-d["total"], (d["nome"] or "").lower()),
    )


@router.get("/comissoes")
def comissoes(
    request: Request,
    mes: str | None = None,
    session: Session = Depends(get_session),
):
    primeiro = _parse_mes(mes)
    proximo = _proximo_mes(primeiro)
    lista = _comissoes_do_mes(session, primeiro, proximo)
    return templates.TemplateResponse(
        "financeiro/comissoes.html",
        {
            "request": request,
            "active": "financeiro",
            "comissoes": lista,
            "n_prof": len(lista),
            "total_geral": sum(d["total"] for d in lista),
            "mes_str": primeiro.strftime("%Y-%m"),
            "mes_label": _rotulo_mes(primeiro),
            "mes_anterior": _mes_anterior(primeiro).strftime("%Y-%m"),
            "mes_proximo": proximo.strftime("%Y-%m"),
        },
    )


@router.get("/comissoes/{profissional_id:int}")
def comissao_detalhe(
    profissional_id: int,
    request: Request,
    mes: str | None = None,
    session: Session = Depends(get_session),
):
    primeiro = _parse_mes(mes)
    proximo = _proximo_mes(primeiro)
    lista = _comissoes_do_mes(session, primeiro, proximo)
    c = next((d for d in lista if d["id"] == profissional_id), None)
    if c is None:
        prof = session.get(Profissional, profissional_id)
        c = {
            "id": profissional_id,
            "nome": prof.nome if prof is not None else "—",
            "total": 0.0,
            "servicos": [],
        }
    return templates.TemplateResponse(
        "financeiro/_comissao_modal.html",
        {"request": request, "c": c, "mes_label": _rotulo_mes(primeiro)},
    )


# ---------------------------------------------------------------------------
# Form de lançamento avulso (criar / editar)
# ---------------------------------------------------------------------------


def _contexto_form(
    session: Session,
    request: Request,
    *,
    titulo: str,
    action: str,
    tipo: str,
    valor_input: str,
    data_input: str,
    categoria_id: int | None,
    descricao: str,
    observacoes: str,
    erro: str | None,
) -> dict:
    return {
        "request": request,
        "active": "financeiro",
        "titulo": titulo,
        "action": action,
        "tipo": tipo,
        "valor_input": valor_input,
        "data_input": data_input,
        "categoria_id": categoria_id,
        "descricao": descricao,
        "observacoes": observacoes,
        "categorias_receita": _categorias(session, "receita"),
        "categorias_despesa": _categorias(session, "despesa"),
        "erro": erro,
    }


@router.get("/novo")
def novo(
    request: Request,
    tipo: str = "despesa",
    descricao: str = "",
    valor: str = "",
    session: Session = Depends(get_session),
):
    # `descricao`/`valor` permitem pré-preencher o form (ex.: "Lançar pagamento"
    # de uma comissão abre aqui já com a descrição e o total).
    tipo = tipo if tipo in _TIPOS_VALIDOS else "despesa"
    return templates.TemplateResponse(
        "financeiro/form.html",
        _contexto_form(
            session,
            request,
            titulo="Novo lançamento",
            action="/financeiro/",
            tipo=tipo,
            valor_input=(valor or "").strip(),
            data_input=date.today().strftime("%Y-%m-%d"),
            categoria_id=None,
            descricao=(descricao or "").strip()[:200],
            observacoes="",
            erro=None,
        ),
    )


@router.get("/{lancamento_id:int}/editar")
def editar(
    lancamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    lanc = session.get(LancamentoFinanceiro, lancamento_id)
    if lanc is None:
        return RedirectResponse(url="/financeiro/", status_code=303)
    if lanc.agendamento_id is not None:
        # Receita vinda de agendamento é gerida pelo pagamento na agenda.
        return RedirectResponse(url="/financeiro/", status_code=303)
    return templates.TemplateResponse(
        "financeiro/form.html",
        _contexto_form(
            session,
            request,
            titulo="Editar lançamento",
            action=f"/financeiro/{lanc.id}",
            tipo=lanc.tipo,
            valor_input=("%.2f" % lanc.valor).replace(".", ","),
            data_input=lanc.data.strftime("%Y-%m-%d"),
            categoria_id=lanc.categoria_id,
            descricao=lanc.descricao or "",
            observacoes=lanc.observacoes or "",
            erro=None,
        ),
    )


@router.get("/{lancamento_id:int}/detalhe")
def detalhe(
    lancamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Fragmento HTMX — detalhe de um lançamento (modal clicável na lista)."""
    l = session.get(LancamentoFinanceiro, lancamento_id)
    if l is None:
        return Response(
            "<p style='padding:8px'>Lançamento não encontrado.</p>",
            status_code=404,
            media_type="text/html",
        )
    cat = session.get(CategoriaFinanceira, l.categoria_id) if l.categoria_id else None
    cat_nome = cat.nome if cat is not None else (l.categoria_nome or "—")
    bruto = l.valor_bruto if l.valor_bruto is not None else l.valor
    pct = None
    if l.desconto_tipo == "pct" and bruto:
        pct = round((l.desconto_valor or 0.0) / bruto * 100)
    det = {
        "id": l.id,
        "tipo": l.tipo,
        "valor": l.valor,
        "bruto": bruto,
        "desconto": l.desconto_valor or 0.0,
        "desc_tipo": l.desconto_tipo,
        "pct": pct,
        "data_fmt": l.data.strftime("%d/%m/%Y"),
        "categoria": cat_nome,
        "descricao": l.descricao or ("Receita" if l.tipo == "receita" else "Despesa"),
        "observacoes": l.observacoes,
        "usuario": l.usuario_nome,
        "do_agendamento": l.agendamento_id is not None,
        "agendamento_id": l.agendamento_id,
    }
    return templates.TemplateResponse(
        "financeiro/_lancamento_modal.html",
        {"request": request, "l": det},
    )


def _validar_e_montar(
    session: Session,
    *,
    tipo: str,
    valor: str,
    data: str,
    categoria_id: str,
    descricao: str,
    observacoes: str,
):
    """Retorna (erro, dados_normalizados). dados é dict pronto p/ persistir."""
    tipo_n = tipo if tipo in _TIPOS_VALIDOS else None
    valor_val, valor_invalido = _parse_valor(valor)
    data_val = _parse_data(data)
    descricao_n = _vazio_para_none(descricao)
    if descricao_n is not None and len(descricao_n) > 200:
        descricao_n = descricao_n[:200]
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    cat_id = None
    try:
        cat_id = int(categoria_id) if categoria_id and categoria_id.strip() else None
    except (ValueError, TypeError):
        cat_id = None

    erro = None
    if tipo_n is None:
        erro = "Tipo inválido."
    elif valor_invalido:
        erro = "Informe um valor maior que zero."
    elif data_val is None:
        erro = "Data inválida."
    else:
        cat = session.get(CategoriaFinanceira, cat_id) if cat_id else None
        if cat is None or cat.tipo != tipo_n:
            erro = "Selecione uma categoria válida para esse tipo."
        else:
            cat_id = cat.id

    dados = {
        "tipo": tipo_n,
        "valor": valor_val,
        "data": data_val,
        "categoria_id": cat_id,
        "descricao": descricao_n,
        "observacoes": observacoes_n,
    }
    return erro, dados


@router.post("/")
def criar(
    request: Request,
    tipo: str = Form("despesa"),
    valor: str = Form(""),
    data: str = Form(""),
    categoria_id: str = Form(""),
    descricao: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(requer_login),
):
    erro, dados = _validar_e_montar(
        session,
        tipo=tipo,
        valor=valor,
        data=data,
        categoria_id=categoria_id,
        descricao=descricao,
        observacoes=observacoes,
    )
    if erro:
        return templates.TemplateResponse(
            "financeiro/form.html",
            _contexto_form(
                session,
                request,
                titulo="Novo lançamento",
                action="/financeiro/",
                tipo=tipo if tipo in _TIPOS_VALIDOS else "despesa",
                valor_input=valor.strip(),
                data_input=(data or "").strip() or date.today().strftime("%Y-%m-%d"),
                categoria_id=int(categoria_id) if categoria_id.strip().isdigit() else None,
                descricao=descricao,
                observacoes=observacoes,
                erro=erro,
            ),
            status_code=400,
        )

    lanc = LancamentoFinanceiro(**dados)
    lanc.usuario_id = usuario.id
    lanc.usuario_nome = usuario.nome_exibicao or usuario.nome_usuario
    session.add(lanc)
    session.commit()
    return RedirectResponse(
        url=f"/financeiro/?mes={dados['data'].strftime('%Y-%m')}", status_code=303
    )


@router.post("/{lancamento_id:int}")
def atualizar(
    lancamento_id: int,
    request: Request,
    tipo: str = Form("despesa"),
    valor: str = Form(""),
    data: str = Form(""),
    categoria_id: str = Form(""),
    descricao: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    lanc = session.get(LancamentoFinanceiro, lancamento_id)
    if lanc is None or lanc.agendamento_id is not None:
        return RedirectResponse(url="/financeiro/", status_code=303)

    erro, dados = _validar_e_montar(
        session,
        tipo=tipo,
        valor=valor,
        data=data,
        categoria_id=categoria_id,
        descricao=descricao,
        observacoes=observacoes,
    )
    if erro:
        return templates.TemplateResponse(
            "financeiro/form.html",
            _contexto_form(
                session,
                request,
                titulo="Editar lançamento",
                action=f"/financeiro/{lanc.id}",
                tipo=tipo if tipo in _TIPOS_VALIDOS else "despesa",
                valor_input=valor.strip(),
                data_input=(data or "").strip() or lanc.data.strftime("%Y-%m-%d"),
                categoria_id=int(categoria_id) if categoria_id.strip().isdigit() else None,
                descricao=descricao,
                observacoes=observacoes,
                erro=erro,
            ),
            status_code=400,
        )

    lanc.tipo = dados["tipo"]
    lanc.valor = dados["valor"]
    lanc.data = dados["data"]
    lanc.categoria_id = dados["categoria_id"]
    lanc.descricao = dados["descricao"]
    lanc.observacoes = dados["observacoes"]
    session.add(lanc)
    session.commit()
    return RedirectResponse(
        url=f"/financeiro/?mes={dados['data'].strftime('%Y-%m')}", status_code=303
    )


@router.post("/{lancamento_id:int}/excluir")
def excluir(lancamento_id: int, session: Session = Depends(get_session)):
    lanc = session.get(LancamentoFinanceiro, lancamento_id)
    if lanc is None:
        return RedirectResponse(url="/financeiro/", status_code=303)
    if lanc.agendamento_id is not None:
        # Receita de agendamento só é removida pelo estorno na agenda.
        return RedirectResponse(
            url=f"/financeiro/?mes={lanc.data.strftime('%Y-%m')}", status_code=303
        )
    mes = lanc.data.strftime("%Y-%m")
    session.delete(lanc)
    session.commit()
    return RedirectResponse(url=f"/financeiro/?mes={mes}", status_code=303)


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------


@router.get("/categorias")
def categorias(
    request: Request,
    erro: str | None = None,
    session: Session = Depends(get_session),
):
    receitas = _categorias(session, "receita", so_ativas=False)
    despesas = _categorias(session, "despesa", so_ativas=False)
    em_uso = {
        c.id: _categoria_em_uso(session, c.id) for c in (*receitas, *despesas)
    }
    return templates.TemplateResponse(
        "financeiro/categorias.html",
        {
            "request": request,
            "active": "financeiro",
            "categorias_receita": receitas,
            "categorias_despesa": despesas,
            "em_uso": em_uso,
            "erro": erro,
        },
    )


def _categoria_duplicada(session, nome, tipo, ignorar_id=None) -> bool:
    nome_n = (nome or "").strip().lower()
    for c in _categorias(session, tipo, so_ativas=False):
        if ignorar_id is not None and c.id == ignorar_id:
            continue
        if (c.nome or "").strip().lower() == nome_n:
            return True
    return False


@router.post("/categorias")
def criar_categoria(
    tipo: str = Form(""),
    nome: str = Form(""),
    session: Session = Depends(get_session),
):
    tipo_n = tipo if tipo in _TIPOS_VALIDOS else None
    nome_n = (nome or "").strip()
    erro = None
    if tipo_n is None:
        erro = "Tipo inválido."
    elif not nome_n:
        erro = "Informe um nome para a categoria."
    elif len(nome_n) > 60:
        erro = "Nome muito longo (máximo 60 caracteres)."
    elif _categoria_duplicada(session, nome_n, tipo_n):
        erro = f"Já existe uma categoria de {tipo_n} com esse nome."

    if erro:
        return RedirectResponse(
            url=f"/financeiro/categorias?erro={erro}", status_code=303
        )

    session.add(CategoriaFinanceira(nome=nome_n, tipo=tipo_n, ativo=True))
    session.commit()
    return RedirectResponse(url="/financeiro/categorias", status_code=303)


@router.post("/categorias/{categoria_id}/renomear")
def renomear_categoria(
    categoria_id: int,
    nome: str = Form(""),
    session: Session = Depends(get_session),
):
    cat = session.get(CategoriaFinanceira, categoria_id)
    if cat is None:
        return RedirectResponse(url="/financeiro/categorias", status_code=303)
    nome_n = (nome or "").strip()
    erro = None
    if not nome_n:
        erro = "Informe um nome para a categoria."
    elif len(nome_n) > 60:
        erro = "Nome muito longo (máximo 60 caracteres)."
    elif _categoria_duplicada(session, nome_n, cat.tipo, ignorar_id=cat.id):
        erro = f"Já existe uma categoria de {cat.tipo} com esse nome."

    if erro:
        return RedirectResponse(
            url=f"/financeiro/categorias?erro={erro}", status_code=303
        )

    cat.nome = nome_n
    session.add(cat)
    session.commit()
    return RedirectResponse(url="/financeiro/categorias", status_code=303)


@router.post("/categorias/{categoria_id}/excluir")
def excluir_categoria(categoria_id: int, session: Session = Depends(get_session)):
    cat = session.get(CategoriaFinanceira, categoria_id)
    if cat is None:
        return RedirectResponse(url="/financeiro/categorias", status_code=303)

    # Os lançamentos que usavam a categoria não a perdem: guardam o nome como
    # snapshot (observação) e ficam sem vínculo vivo.
    usados = session.exec(
        select(LancamentoFinanceiro).where(
            LancamentoFinanceiro.categoria_id == cat.id
        )
    ).all()
    for l in usados:
        l.categoria_nome = cat.nome
        l.categoria_id = None
        session.add(l)
    session.delete(cat)
    session.commit()
    return RedirectResponse(url="/financeiro/categorias", status_code=303)
