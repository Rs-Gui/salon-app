from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.produto import Produto
from app.security import requer_login
from app.templating import templates

router = APIRouter(prefix="/produtos", dependencies=[Depends(requer_login)])

_TIPOS_VALIDOS = {"entrada", "saida_uso"}


def _vazio_para_none(valor):
    if valor is None:
        return None
    v = valor.strip()
    return v if v else None


def _parse_preco(valor):
    """Retorna (preco_float, eh_invalido_bool). Vazio → (0.0, False)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 0.0, False
    v = valor.strip().replace(",", ".")
    try:
        f = float(v)
    except (ValueError, TypeError):
        return 0.0, True
    if f < 0:
        return 0.0, True
    return f, False


def _parse_int_positivo(valor, *, permitir_zero=False):
    """Parse de inteiro. Retorna None se inválido.

    Rejeita floats com parte fracionária (ex.: "1.5" -> None).
    Aceita "0" apenas se permitir_zero=True.
    """
    if valor is None:
        return None
    v = valor.strip() if isinstance(valor, str) else valor
    if v == "" or v is None:
        return None
    try:
        n = int(v)
    except (ValueError, TypeError):
        return None
    if permitir_zero:
        if n < 0:
            return None
    else:
        if n <= 0:
            return None
    return n


def _parse_int_nao_negativo(valor):
    """Inteiro >= 0. Retorna None se inválido."""
    return _parse_int_positivo(valor, permitir_zero=True)


def _validar_limites(nome, observacoes):
    if nome is not None and len(nome) > 200:
        return "Nome muito longo (máximo 200 caracteres)."
    if observacoes is not None and len(observacoes) > 2000:
        return "Observações muito longas (máximo 2000 caracteres)."
    return None


def _produto_duplicado(session, nome, ignorar_id=None):
    nome_n = nome.strip().lower()
    if not nome_n:
        return False
    produtos = session.exec(select(Produto)).all()
    for p in produtos:
        if ignorar_id is not None and p.id == ignorar_id:
            continue
        if (p.nome or "").strip().lower() == nome_n:
            return True
    return False


def _preco_input(preco: float) -> str:
    return ("%.2f" % (preco or 0.0)).replace(".", ",")


# ---------- Listagem / form de cadastro ----------


@router.get("/")
def lista(request: Request, session: Session = Depends(get_session)):
    produtos = session.exec(select(Produto).order_by(Produto.nome)).all()
    return templates.TemplateResponse(
        "produtos/lista.html",
        {"request": request, "active": "produtos", "produtos": produtos},
    )


@router.get("/novo")
def novo(request: Request):
    return templates.TemplateResponse(
        "produtos/form.html",
        {
            "request": request,
            "active": "produtos",
            "titulo": "Novo Produto",
            "action": "/produtos/",
            "produto": Produto(nome=""),
            "preco_venda_input": "",
            "custo_input": "",
            "estoque_atual_input": "",
            "estoque_minimo_input": "",
            "eh_edicao": False,
            "erro": None,
        },
    )


@router.get("/{produto_id}/editar")
def editar(produto_id: int, request: Request, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)
    return templates.TemplateResponse(
        "produtos/form.html",
        {
            "request": request,
            "active": "produtos",
            "titulo": "Editar Produto",
            "action": f"/produtos/{produto.id}",
            "produto": produto,
            "preco_venda_input": _preco_input(produto.preco_venda),
            "custo_input": _preco_input(produto.custo),
            "estoque_atual_input": str(produto.estoque_atual),
            "estoque_minimo_input": str(produto.estoque_minimo),
            "eh_edicao": True,
            "erro": None,
        },
    )


@router.post("/")
def criar(
    request: Request,
    nome: str = Form(...),
    preco_venda: str = Form(""),
    custo: str = Form(""),
    estoque_atual: str = Form(""),
    estoque_minimo: str = Form(""),
    unidade: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    nome_limpo = nome.strip()
    preco_venda_val, preco_invalido = _parse_preco(preco_venda)
    custo_val, custo_invalido = _parse_preco(custo)
    unidade_n = unidade.strip() if unidade else ""
    if not unidade_n:
        unidade_n = "un"
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    # Parse de estoque - default 0
    estoque_atual_raw = estoque_atual.strip() if estoque_atual else ""
    estoque_minimo_raw = estoque_minimo.strip() if estoque_minimo else ""
    estoque_atual_val = (
        0 if estoque_atual_raw == "" else _parse_int_nao_negativo(estoque_atual_raw)
    )
    estoque_minimo_val = (
        0 if estoque_minimo_raw == "" else _parse_int_nao_negativo(estoque_minimo_raw)
    )

    erro = None
    if not nome_limpo:
        erro = "Nome é obrigatório."
    elif erro is None:
        erro = _validar_limites(nome_limpo, observacoes_n)

    if erro is None and preco_invalido:
        erro = "Preço de venda inválido."

    if erro is None and custo_invalido:
        erro = "Custo inválido."

    if erro is None:
        if estoque_minimo_val is None:
            erro = "Estoque mínimo não pode ser negativo."

    if erro is None:
        if estoque_atual_val is None:
            erro = "Estoque inicial não pode ser negativo."

    if erro is None:
        if len(unidade_n) > 10:
            erro = "Unidade deve ter no máximo 10 caracteres."

    if erro is None:
        if _produto_duplicado(session, nome_limpo):
            erro = "Já existe um produto com esse nome."

    if erro:
        produto_mem = Produto(
            nome=nome_limpo,
            preco_venda=preco_venda_val if preco_venda_val >= 0 else 0.0,
            custo=custo_val if custo_val >= 0 else 0.0,
            estoque_atual=estoque_atual_val if estoque_atual_val is not None else 0,
            estoque_minimo=estoque_minimo_val if estoque_minimo_val is not None else 0,
            unidade=unidade_n,
            observacoes=observacoes_n,
        )
        return templates.TemplateResponse(
            "produtos/form.html",
            {
                "request": request,
                "active": "produtos",
                "titulo": "Novo Produto",
                "action": "/produtos/",
                "produto": produto_mem,
                "preco_venda_input": preco_venda.strip() if preco_venda else "",
                "custo_input": custo.strip() if custo else "",
                "estoque_atual_input": estoque_atual_raw,
                "estoque_minimo_input": estoque_minimo_raw,
                "eh_edicao": False,
                "erro": erro,
            },
            status_code=400,
        )

    produto = Produto(
        nome=nome_limpo,
        preco_venda=preco_venda_val,
        custo=custo_val,
        estoque_atual=estoque_atual_val,
        estoque_minimo=estoque_minimo_val,
        unidade=unidade_n,
        observacoes=observacoes_n,
    )
    session.add(produto)
    session.commit()
    return RedirectResponse(url="/produtos/", status_code=303)


@router.post("/{produto_id}")
def atualizar(
    produto_id: int,
    request: Request,
    nome: str = Form(...),
    preco_venda: str = Form(""),
    custo: str = Form(""),
    estoque_minimo: str = Form(""),
    unidade: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)

    nome_limpo = nome.strip()
    preco_venda_val, preco_invalido = _parse_preco(preco_venda)
    custo_val, custo_invalido = _parse_preco(custo)
    unidade_n = unidade.strip() if unidade else ""
    if not unidade_n:
        unidade_n = "un"
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    estoque_minimo_raw = estoque_minimo.strip() if estoque_minimo else ""
    estoque_minimo_val = (
        0 if estoque_minimo_raw == "" else _parse_int_nao_negativo(estoque_minimo_raw)
    )

    erro = None
    if not nome_limpo:
        erro = "Nome é obrigatório."
    elif erro is None:
        erro = _validar_limites(nome_limpo, observacoes_n)

    if erro is None and preco_invalido:
        erro = "Preço de venda inválido."

    if erro is None and custo_invalido:
        erro = "Custo inválido."

    if erro is None:
        if estoque_minimo_val is None:
            erro = "Estoque mínimo não pode ser negativo."

    if erro is None:
        if len(unidade_n) > 10:
            erro = "Unidade deve ter no máximo 10 caracteres."

    if erro is None:
        if _produto_duplicado(session, nome_limpo, ignorar_id=produto.id):
            erro = "Já existe um produto com esse nome."

    if erro:
        produto_mem = Produto(
            id=produto.id,
            nome=nome_limpo,
            preco_venda=preco_venda_val if preco_venda_val >= 0 else 0.0,
            custo=custo_val if custo_val >= 0 else 0.0,
            estoque_atual=produto.estoque_atual,  # nunca alterado em update
            estoque_minimo=estoque_minimo_val if estoque_minimo_val is not None else 0,
            unidade=unidade_n,
            ativo=produto.ativo,
            observacoes=observacoes_n,
        )
        return templates.TemplateResponse(
            "produtos/form.html",
            {
                "request": request,
                "active": "produtos",
                "titulo": "Editar Produto",
                "action": f"/produtos/{produto.id}",
                "produto": produto_mem,
                "preco_venda_input": preco_venda.strip() if preco_venda else "",
                "custo_input": custo.strip() if custo else "",
                "estoque_atual_input": str(produto.estoque_atual),
                "estoque_minimo_input": estoque_minimo_raw,
                "eh_edicao": True,
                "erro": erro,
            },
            status_code=400,
        )

    # Edição NÃO altera estoque_atual — mesmo se viesse no form é ignorado
    # (sequer aceitamos o campo no Form acima).
    produto.nome = nome_limpo
    produto.preco_venda = preco_venda_val
    produto.custo = custo_val
    produto.estoque_minimo = estoque_minimo_val
    produto.unidade = unidade_n
    produto.observacoes = observacoes_n
    session.add(produto)
    session.commit()
    return RedirectResponse(url="/produtos/", status_code=303)


@router.post("/{produto_id}/desativar")
def desativar(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is not None:
        produto.ativo = False
        session.add(produto)
        session.commit()
    return RedirectResponse(url="/produtos/", status_code=303)


@router.post("/{produto_id}/reativar")
def reativar(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is not None:
        produto.ativo = True
        session.add(produto)
        session.commit()
    return RedirectResponse(url="/produtos/", status_code=303)


@router.post("/{produto_id}/excluir")
def excluir(produto_id: int, session: Session = Depends(get_session)):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)
    if produto.ativo:
        return Response(
            content="Só é possível excluir produtos desativados.",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )

    # Cascade manual em movimentações + delete do produto numa única transação.
    movimentacoes = session.exec(
        select(MovimentacaoEstoque).where(
            MovimentacaoEstoque.produto_id == produto.id
        )
    ).all()
    for mov in movimentacoes:
        session.delete(mov)
    session.flush()
    session.delete(produto)
    session.commit()
    return RedirectResponse(url="/produtos/", status_code=303)


# ---------- Movimentação de estoque ----------


def _titulo_movimentacao(tipo: str) -> str:
    return "Adicionar ao estoque" if tipo == "entrada" else "Retirar para uso"


@router.get("/{produto_id}/movimentar")
def movimentar_form(
    produto_id: int,
    request: Request,
    tipo: str = "entrada",
    session: Session = Depends(get_session),
):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)

    if tipo not in _TIPOS_VALIDOS:
        # whitelist estrito — força para entrada por default em GET inválido
        tipo = "entrada"

    return templates.TemplateResponse(
        "produtos/_movimentacao_modal.html",
        {
            "request": request,
            "active": "produtos",
            "produto": produto,
            "tipo": tipo,
            "titulo": _titulo_movimentacao(tipo),
            "quantidade": "",
            "observacoes": "",
            "erro": None,
        },
    )


@router.post("/{produto_id}/movimentar")
def movimentar(
    produto_id: int,
    request: Request,
    tipo: str = Form(...),
    quantidade: str = Form(""),
    observacoes: str = Form(""),
    session: Session = Depends(get_session),
):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)

    quantidade_raw = quantidade.strip() if quantidade else ""
    observacoes_n = _vazio_para_none(observacoes)
    if observacoes_n is not None and len(observacoes_n) > 2000:
        observacoes_n = observacoes_n[:2000]

    erro = None
    tipo_valido = tipo if tipo in _TIPOS_VALIDOS else None
    tipo_para_render = tipo_valido or "entrada"

    if tipo_valido is None:
        erro = "Tipo de movimentação inválido."

    quantidade_val = None
    if erro is None:
        quantidade_val = _parse_int_positivo(quantidade_raw)
        if quantidade_val is None:
            erro = "Quantidade deve ser um número inteiro maior que zero."

    if erro is None and not produto.ativo:
        erro = "Não é possível movimentar um produto inativo."

    if erro is None and tipo_valido == "saida_uso":
        if quantidade_val > produto.estoque_atual:
            erro = (
                f"Estoque insuficiente. Disponível: "
                f"{produto.estoque_atual} {produto.unidade}."
            )

    if erro:
        return templates.TemplateResponse(
            "produtos/_movimentacao_modal.html",
            {
                "request": request,
                "active": "produtos",
                "produto": produto,
                "tipo": tipo_para_render,
                "titulo": _titulo_movimentacao(tipo_para_render),
                "quantidade": quantidade_raw,
                "observacoes": observacoes_n or "",
                "erro": erro,
            },
            status_code=400,
        )

    # Sucesso: cria movimentação + ajusta estoque_atual na mesma sessão/transação
    movimentacao = MovimentacaoEstoque(
        produto_id=produto.id,
        tipo=tipo_valido,
        quantidade=quantidade_val,
        observacoes=observacoes_n,
    )
    session.add(movimentacao)

    if tipo_valido == "entrada":
        produto.estoque_atual += quantidade_val
    else:  # saida_uso
        produto.estoque_atual -= quantidade_val
    session.add(produto)

    if tipo_valido == "saida_uso" and produto.estoque_atual < 0:
        # defesa contra race; se chegamos aqui é bug ou concorrência
        session.rollback()
        return templates.TemplateResponse(
            "produtos/_movimentacao_modal.html",
            {
                "request": request,
                "active": "produtos",
                "produto": produto,
                "tipo": tipo_para_render,
                "titulo": _titulo_movimentacao(tipo_para_render),
                "quantidade": quantidade_raw,
                "observacoes": observacoes_n or "",
                "erro": f"Estoque insuficiente. Disponível: {produto.estoque_atual + quantidade_val} {produto.unidade}.",
            },
            status_code=400,
        )

    session.commit()

    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.get("/{produto_id}/movimentacoes")
def historico(
    produto_id: int, request: Request, session: Session = Depends(get_session)
):
    produto = session.get(Produto, produto_id)
    if produto is None:
        return RedirectResponse(url="/produtos/", status_code=303)

    movimentacoes = session.exec(
        select(MovimentacaoEstoque)
        .where(MovimentacaoEstoque.produto_id == produto.id)
        .order_by(MovimentacaoEstoque.criado_em.desc())
    ).all()

    return templates.TemplateResponse(
        "produtos/historico.html",
        {
            "request": request,
            "active": "produtos",
            "produto": produto,
            "movimentacoes": movimentacoes,
        },
    )
