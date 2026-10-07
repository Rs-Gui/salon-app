from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models.agendamento import (
    Agendamento,
    AgendamentoProfissional,
    AgendamentoServico,
)
from app.models.categoria_financeira import CategoriaFinanceira
from app.models.cliente import Cliente
from app.models.lancamento_financeiro import LancamentoFinanceiro
from app.models.movimentacao_estoque import MovimentacaoEstoque
from app.models.produto import Produto
from app.models.profissional import Profissional
from app.models.servico import Servico
from app.models.usuario import Usuario
from app.security import requer_admin, requer_login
from app.templating import templates

router = APIRouter(prefix="/agendamentos", dependencies=[Depends(requer_login)])

_HORA_MIN = 6
_HORA_MAX = 22
_DURACAO_MAX = 480


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vazio_para_none(valor):
    if valor is None:
        return None
    v = valor.strip()
    return v if v else None


def _parse_cliente_id(valor):
    v = _vazio_para_none(valor)
    if v is None or v == "0":
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _parse_duracao_override(valor):
    v = _vazio_para_none(valor)
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _parse_data_hora(data: str, hora: str) -> Optional[datetime]:
    data = (data or "").strip()
    hora = (hora or "").strip()
    if not data or not hora:
        return None
    try:
        return datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _parse_ids_lista(valores) -> List[int]:
    """Converte uma lista de strings vindas de Form em uma lista de ints únicos preservando ordem."""
    if not valores:
        return []
    vistos: set[int] = set()
    saida: List[int] = []
    for v in valores:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        try:
            n = int(s)
        except ValueError:
            continue
        if n in vistos:
            continue
        vistos.add(n)
        saida.append(n)
    return saida


def _duracao_efetiva(ag: Agendamento, servicos: list) -> int:
    if ag.duracao_override is not None and ag.duracao_override > 0:
        return ag.duracao_override
    if servicos:
        return max(s.duracao_minutos for s in servicos)
    return 60


def _calcula_servicos(session: Session, agendamento_id: int) -> List[Servico]:
    if agendamento_id is None:
        return []
    links = session.exec(
        select(AgendamentoServico).where(
            AgendamentoServico.agendamento_id == agendamento_id
        )
    ).all()
    ids = [l.servico_id for l in links]
    if not ids:
        return []
    rows = session.exec(select(Servico).where(Servico.id.in_(ids))).all()
    return sorted(rows, key=lambda s: (s.nome or "").lower())


def _calcula_profissionais(session: Session, agendamento_id: int) -> list:
    """Retorna lista de "visões" de profissionais vinculados a um agendamento.

    Cada item é um SimpleNamespace com atributos: id, nome, ativo, excluido.
    - Se o profissional ainda existe no banco: dados reais, excluido=False.
    - Se foi hard-deleted: shim a partir de nome_snapshot, ativo=False, excluido=True.

    Templates leem por atributo (`.id`, `.nome`, `.ativo`, `.excluido`).
    """
    if agendamento_id is None:
        return []
    links = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.agendamento_id == agendamento_id
        )
    ).all()
    if not links:
        return []
    ids = [l.profissional_id for l in links]
    rows = session.exec(select(Profissional).where(Profissional.id.in_(ids))).all()
    por_id = {p.id: p for p in rows}

    saida = []
    for link in links:
        prof = por_id.get(link.profissional_id)
        if prof is not None:
            saida.append(
                SimpleNamespace(
                    id=prof.id,
                    nome=prof.nome,
                    ativo=prof.ativo,
                    excluido=False,
                )
            )
        else:
            saida.append(
                SimpleNamespace(
                    id=link.profissional_id,
                    nome=link.nome_snapshot or "(nome perdido)",
                    ativo=False,
                    excluido=True,
                )
            )
    return sorted(saida, key=lambda p: (p.nome or "").lower())


def _calcula_cliente(session: Session, ag: Agendamento) -> Optional[Cliente]:
    if ag is None or ag.cliente_id is None:
        return None
    return session.get(Cliente, ag.cliente_id)


def _horarios_dia() -> List[str]:
    saida = []
    for h in range(_HORA_MIN, _HORA_MAX):
        saida.append(f"{h:02d}:00")
        saida.append(f"{h:02d}:30")
    return saida


def _substitui_links(
    session: Session,
    agendamento_id: int,
    prof_ids: List[int],
    serv_ids: List[int],
) -> None:
    # Deleta existentes
    existentes_prof = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.agendamento_id == agendamento_id
        )
    ).all()
    for link in existentes_prof:
        session.delete(link)
    existentes_serv = session.exec(
        select(AgendamentoServico).where(
            AgendamentoServico.agendamento_id == agendamento_id
        )
    ).all()
    for link in existentes_serv:
        session.delete(link)

    # Flush é obrigatório: sem ele os INSERTs ocorrem antes dos DELETEs e disparam
    # violação de unique constraint na PK composta.
    session.flush()

    for pid in prof_ids:
        session.add(
            AgendamentoProfissional(agendamento_id=agendamento_id, profissional_id=pid)
        )
    for sid in serv_ids:
        session.add(
            AgendamentoServico(agendamento_id=agendamento_id, servico_id=sid)
        )


def _conflita_para_profissional(
    session: Session,
    profissional_id: int,
    inicio: datetime,
    fim: datetime,
    ignorar_agendamento_id: Optional[int] = None,
) -> Optional[Agendamento]:
    inicio_dia = datetime(inicio.year, inicio.month, inicio.day)
    fim_dia = inicio_dia + timedelta(days=1)

    links = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.profissional_id == profissional_id
        )
    ).all()
    ag_ids = [l.agendamento_id for l in links]
    if not ag_ids:
        return None

    candidatos = session.exec(
        select(Agendamento)
        .where(Agendamento.id.in_(ag_ids))
        .where(Agendamento.data_hora >= inicio_dia)
        .where(Agendamento.data_hora < fim_dia)
        .order_by(Agendamento.data_hora)
    ).all()

    for cand in candidatos:
        if ignorar_agendamento_id is not None and cand.id == ignorar_agendamento_id:
            continue
        if cand.encaixe:
            continue
        servs = _calcula_servicos(session, cand.id)
        dur = _duracao_efetiva(cand, servs)
        fim_cand = cand.data_hora + timedelta(minutes=dur)
        if cand.data_hora < fim and fim_cand > inicio:
            return cand
    return None


def _distribui_faixas(blocos: list) -> list:
    """Encaixes: blocos que se sobrepõem na mesma coluna ficam lado a lado.
    Devolve cópias com lane (0..) e lanes (nº de faixas do grupo sobreposto)."""
    ordenados = sorted(blocos, key=lambda b: (b["top_px"], -b["duracao_efetiva"]))
    saida, grupo, fim_grupo = [], [], None

    def fecha(grupo):
        fins = []  # fim de cada faixa já ocupada
        for b in grupo:
            for i, fim in enumerate(fins):
                if b["top_px"] >= fim:
                    fins[i] = b["top_px"] + b["duracao_efetiva"]
                    b["lane"] = i
                    break
            else:
                fins.append(b["top_px"] + b["duracao_efetiva"])
                b["lane"] = len(fins) - 1
        for b in grupo:
            b["lanes"] = len(fins)
        saida.extend(grupo)

    for b in ordenados:
        b = dict(b)
        if grupo and b["top_px"] >= fim_grupo:
            fecha(grupo)
            grupo = []
        grupo.append(b)
        fim = b["top_px"] + b["duracao_efetiva"]
        fim_grupo = fim if len(grupo) == 1 else max(fim_grupo, fim)
    if grupo:
        fecha(grupo)
    return saida


def _ordena_por_nome(itens):
    return sorted(itens, key=lambda x: (x.nome or "").lower())


def _contexto_form(
    session: Session,
    agendamento: Agendamento,
    action: str,
    titulo: str,
    request: Request,
    erro: Optional[str] = None,
    data_default: str = "",
    hora_default: str = "",
    profissional_id_default: Optional[int] = None,
    duracao_default: Optional[int] = None,
    observacoes_default: Optional[str] = None,
    cliente_id_default: Optional[int] = None,
    profissional_ids_default: Optional[List[int]] = None,
    servico_ids_default: Optional[List[int]] = None,
) -> dict:
    """Monta o contexto compartilhado por _form_modal.html e form_edit.html.

    Contrato (chaves no contexto):
      - request: fastapi.Request
      - active: "agendamentos"
      - action: str (URL POST do form)
      - titulo: str
      - agendamento: Agendamento (em criação tem id=None)
      - clientes: list[Cliente] (ativos + qualquer cliente inativo vinculado, ordenado por nome)
      - profissionais: list[Profissional] (ativos + inativos vinculados, ordenado por nome)
      - servicos: list[Servico] (ativos + inativos vinculados, ordenado por nome)
      - profissionais_selecionados: list[int] (ids pré-marcados)
      - servicos_selecionados: list[int] (ids pré-marcados)
      - cliente_selecionado_id: int | None
      - erro: str | None
      - data_default: str (YYYY-MM-DD)
      - hora_default: str (HH:MM)
      - duracao_default: int | None  (valor a preencher no input de duração)
      - observacoes_default: str  (texto a preencher no textarea)
      - data_cancelar: str (YYYY-MM-DD) — data a ser usada pelo link "Cancelar"
            no template. Em edição com input inválido, mantém a data original do
            agendamento (não a string vazia/inválida do form), para que o link
            volte para a agenda correta. Em criação, espelha data_default ou hoje.
    """
    ativos_cli = session.exec(
        select(Cliente).where(Cliente.ativo == True).order_by(Cliente.nome)  # noqa: E712
    ).all()
    ativos_prof = session.exec(
        select(Profissional)
        .where(Profissional.ativo == True)  # noqa: E712
        .order_by(Profissional.nome)
    ).all()
    ativos_serv = session.exec(
        select(Servico).where(Servico.ativo == True).order_by(Servico.nome)  # noqa: E712
    ).all()

    # Vínculos existentes (em edição)
    profs_vinc = _calcula_profissionais(session, agendamento.id) if agendamento and agendamento.id else []
    servs_vinc = _calcula_servicos(session, agendamento.id) if agendamento and agendamento.id else []
    cliente_vinc = _calcula_cliente(session, agendamento) if agendamento and agendamento.id else None

    # Garante que itens inativos vinculados não sumam (senão re-save perderia o vínculo)
    ids_cli_ativos = {c.id for c in ativos_cli}
    clientes = list(ativos_cli)
    if cliente_vinc is not None and cliente_vinc.id not in ids_cli_ativos:
        clientes.append(cliente_vinc)
        clientes = _ordena_por_nome(clientes)

    # Profissionais vinculados podem ser: ativos (já no dropdown), inativos
    # (re-injetar como Profissional real) ou excluídos (shim do helper, NÃO
    # entra no dropdown de seleção — só nos chips já selecionados).
    ids_prof_ativos = {p.id for p in ativos_prof}
    profissionais = [
        SimpleNamespace(id=p.id, nome=p.nome, ativo=p.ativo, excluido=False)
        for p in ativos_prof
    ]
    ids_no_dropdown = set(ids_prof_ativos)
    for p in profs_vinc:
        if getattr(p, "excluido", False):
            # Shim vai pro contexto pra renderizar chip selecionado com "(excluído)",
            # mas NÃO entra no dropdown de seleção pra novos vínculos.
            profissionais.append(p)
            continue
        if p.id not in ids_no_dropdown:
            # Inativo vinculado: re-injeta no dropdown
            profissionais.append(
                SimpleNamespace(id=p.id, nome=p.nome, ativo=p.ativo, excluido=False)
            )
            ids_no_dropdown.add(p.id)
    profissionais = _ordena_por_nome(profissionais)

    ids_serv_ativos = {s.id for s in ativos_serv}
    servicos = list(ativos_serv)
    for s in servs_vinc:
        if s.id not in ids_serv_ativos:
            servicos.append(s)
            ids_serv_ativos.add(s.id)
    servicos = _ordena_por_nome(servicos)

    # Seleções pré-marcadas
    if profissional_ids_default is not None:
        profissionais_selecionados = list(profissional_ids_default)
    else:
        profissionais_selecionados = [p.id for p in profs_vinc]
        if (
            (agendamento is None or agendamento.id is None)
            and profissional_id_default is not None
            and profissional_id_default not in profissionais_selecionados
        ):
            profissionais_selecionados = [profissional_id_default]

    if servico_ids_default is not None:
        servicos_selecionados = list(servico_ids_default)
    else:
        servicos_selecionados = [s.id for s in servs_vinc]

    if cliente_id_default is not None:
        cliente_selecionado_id = cliente_id_default
    else:
        cliente_selecionado_id = cliente_vinc.id if cliente_vinc is not None else None

    # Defaults de data/hora para os inputs
    if not data_default and agendamento is not None and agendamento.id is not None:
        data_default = agendamento.data_hora.strftime("%Y-%m-%d")
    if not hora_default and agendamento is not None and agendamento.id is not None:
        hora_default = agendamento.data_hora.strftime("%H:%M")

    if duracao_default is None and agendamento is not None:
        duracao_default = agendamento.duracao_override

    if observacoes_default is None and agendamento is not None:
        observacoes_default = agendamento.observacoes or ""

    # data_cancelar: usado pelo link "Cancelar" no template. Se em edição, sempre
    # cai para a data original do agendamento (independente do que o usuário digitou
    # — que pode ser inválido). Em criação, usa data_default ou hoje.
    if agendamento is not None and agendamento.id is not None:
        data_cancelar = agendamento.data_hora.strftime("%Y-%m-%d")
    elif data_default:
        data_cancelar = data_default
    else:
        data_cancelar = date.today().strftime("%Y-%m-%d")

    return {
        "request": request,
        "active": "agendamentos",
        "action": action,
        "titulo": titulo,
        "agendamento": agendamento,
        "clientes": clientes,
        "profissionais": profissionais,
        "servicos": servicos,
        "profissionais_selecionados": profissionais_selecionados,
        "servicos_selecionados": servicos_selecionados,
        "cliente_selecionado_id": cliente_selecionado_id,
        "erro": erro,
        "data_default": data_default,
        "hora_default": hora_default,
        "duracao_default": duracao_default,
        "observacoes_default": observacoes_default or "",
        "data_cancelar": data_cancelar,
    }


def _parse_data_query(data_str: Optional[str]) -> date:
    if data_str:
        try:
            return datetime.strptime(data_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _validar_agendamento(
    session: Session,
    *,
    profissional_ids: List[int],
    servico_ids: List[int],
    data_hora: Optional[datetime],
    duracao_override: Optional[int],
    modo: str,  # "criar" | "atualizar" | "horario" | "duracao"
    ag_atual: Optional[Agendamento] = None,
    encaixe: bool = False,
) -> tuple[Optional[str], Optional[datetime], Optional[int]]:
    """Retorna (erro, fim, duracao_efetiva).

    Realiza as validações na ordem da seção 8.5. ag_atual é obrigatório para
    atualizar/horario/duracao (usado para ignorar o próprio agendamento na
    detecção de conflito e para a regra de "passado").
    """
    if not profissional_ids:
        return "Selecione pelo menos um profissional.", None, None
    # Pelo menos um dos profissionais selecionados precisa estar ativo.
    profs_selecionados = session.exec(
        select(Profissional).where(Profissional.id.in_(profissional_ids))
    ).all()
    if not any(p.ativo for p in profs_selecionados):
        return (
            "Pelo menos um profissional ativo precisa estar vinculado ao agendamento.",
            None,
            None,
        )
    if not servico_ids:
        return "Selecione pelo menos um serviço.", None, None
    if data_hora is None:
        return "Data e hora inválidas.", None, None
    if not (_HORA_MIN <= data_hora.hour < _HORA_MAX):
        return "O horário de início deve estar entre 06:00 e 21:59.", None, None

    agora = datetime.now()
    if modo == "criar":
        if data_hora < agora:
            return "Não é possível agendar para uma data/hora no passado.", None, None
    else:
        # update/horario/duracao: só bloqueia se está sendo *trocado* para o passado
        antigo = ag_atual.data_hora if ag_atual is not None else None
        if data_hora < agora and data_hora != antigo:
            return "Não é possível remarcar para uma data/hora no passado.", None, None

    # Carrega serviços para duração efetiva
    servicos = session.exec(select(Servico).where(Servico.id.in_(servico_ids))).all()
    ag_temp = Agendamento(data_hora=data_hora, duracao_override=duracao_override)
    dur = _duracao_efetiva(ag_temp, servicos)
    if dur < 15:
        return "A duração mínima é de 15 minutos.", None, None
    if dur > _DURACAO_MAX:
        return "A duração total não pode passar de 480 minutos (8h).", None, None

    fim = data_hora + timedelta(minutes=dur)
    limite = data_hora.replace(hour=_HORA_MAX, minute=0, second=0, microsecond=0)
    if fim > limite:
        return (
            f"O agendamento termina às {fim.strftime('%H:%M')}, depois do limite do "
            "expediente (22:00). Reduza a duração ou escolha um horário mais cedo."
        ), None, None

    # Conflito por profissional (encaixe sobrepõe de propósito: não checa)
    ignorar_id = ag_atual.id if ag_atual is not None else None
    for pid in ([] if encaixe else profissional_ids):
        conflito = _conflita_para_profissional(
            session, pid, data_hora, fim, ignorar_agendamento_id=ignorar_id
        )
        if conflito is not None:
            prof = session.get(Profissional, pid)
            prof_nome = prof.nome if prof is not None else f"#{pid}"
            servs_c = _calcula_servicos(session, conflito.id)
            dur_c = _duracao_efetiva(conflito, servs_c)
            fim_c = conflito.data_hora + timedelta(minutes=dur_c)
            return (
                f"Conflito de horário para {prof_nome} "
                f"({conflito.data_hora.strftime('%H:%M')}–{fim_c.strftime('%H:%M')})."
            ), None, None

    return None, fim, dur


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


def _agendamentos_pendentes(session: Session) -> List[Agendamento]:
    """Atendimentos anteriores a hoje (data_hora < início de hoje) ainda SEM
    pagamento (nenhum LancamentoFinanceiro vinculado). Mais recentes primeiro."""
    hoje = date.today()
    inicio_hoje = datetime(hoje.year, hoje.month, hoje.day)
    pagos = set(
        session.exec(
            select(LancamentoFinanceiro.agendamento_id).where(
                LancamentoFinanceiro.agendamento_id != None  # noqa: E711
            )
        ).all()
    )
    ags = session.exec(
        select(Agendamento)
        .where(Agendamento.data_hora < inicio_hoje)
        .order_by(Agendamento.data_hora.desc())
    ).all()
    return [a for a in ags if a.id not in pagos]


@router.get("/")
def lista(
    request: Request,
    data: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Calendário diário.

    Contrato do contexto entregue a `agendamentos/lista.html`:
      - request: Request
      - active: "agendamentos"
      - data: datetime.date  (dia exibido)
      - data_str: str        (YYYY-MM-DD)
      - data_fmt: str        (dd/mm/yyyy)
      - data_anterior: str   (YYYY-MM-DD, dia -1)
      - data_proxima:  str   (YYYY-MM-DD, dia +1)
      - profissionais: list[Profissional]  (ativos, ordenados por nome)
      - horarios: list[str]  (32 slots "HH:MM" entre 06:00 e 21:30)
      - blocos_por_profissional: dict[int, list[dict]] onde cada bloco tem:
            { id: int,
              hora: str ("HH:MM"),
              cliente_nome: str | None,
              servicos: list[str] (nomes),
              top_px: int  ((hora*60+min) - 360),
              height_px: int  (duracao_efetiva - 2),
              duracao_efetiva: int }
    """
    dia = _parse_data_query(data)
    inicio_dia = datetime(dia.year, dia.month, dia.day)
    fim_dia = inicio_dia + timedelta(days=1)

    profissionais = session.exec(
        select(Profissional)
        .where(Profissional.ativo == True)  # noqa: E712
        .order_by(Profissional.nome)
    ).all()

    # Carrega todos os agendamentos do dia
    agendamentos_dia = session.exec(
        select(Agendamento)
        .where(Agendamento.data_hora >= inicio_dia)
        .where(Agendamento.data_hora < fim_dia)
        .order_by(Agendamento.data_hora)
    ).all()

    # Indexa profissional -> [agendamento]
    blocos_por_profissional: dict[int, list[dict]] = {p.id: [] for p in profissionais}
    # Apenas profissionais ativos exibem coluna no calendário.

    for ag in agendamentos_dia:
        servs = _calcula_servicos(session, ag.id)
        profs = _calcula_profissionais(session, ag.id)
        dur = _duracao_efetiva(ag, servs)
        cliente = _calcula_cliente(session, ag)
        minutos = ag.data_hora.hour * 60 + ag.data_hora.minute
        tem_inativo = any(not p.ativo for p in profs)
        bloco = {
            "id": ag.id,
            "hora": ag.data_hora.strftime("%H:%M"),
            "cliente_nome": cliente.nome if cliente is not None else None,
            "servicos": [s.nome for s in servs],
            "top_px": minutos - 360,
            "height_px": max(dur - 2, 1),
            "duracao_efetiva": dur,
            "tem_inativo": tem_inativo,
            "encaixe": ag.encaixe,
        }
        for p in profs:
            if p.id in blocos_por_profissional:
                blocos_por_profissional[p.id].append(bloco)

    blocos_por_profissional = {
        pid: _distribui_faixas(blocos) for pid, blocos in blocos_por_profissional.items()
    }

    data_anterior = (dia - timedelta(days=1)).strftime("%Y-%m-%d")
    data_proxima = (dia + timedelta(days=1)).strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        "agendamentos/lista.html",
        {
            "request": request,
            "active": "agendamentos",
            "data": dia,
            "data_str": dia.strftime("%Y-%m-%d"),
            "data_fmt": dia.strftime("%d/%m/%Y"),
            "data_anterior": data_anterior,
            "data_proxima": data_proxima,
            "profissionais": profissionais,
            "horarios": _horarios_dia(),
            "blocos_por_profissional": blocos_por_profissional,
            "pendentes_count": len(_agendamentos_pendentes(session)),
        },
    )


@router.get("/a-receber")
def a_receber(request: Request, session: Session = Depends(get_session)):
    """Lista de atendimentos passados (antes de hoje) ainda não pagos.
    Cada linha abre direto o modal de pagamento (reusa o fluxo da agenda)."""
    pendentes = _agendamentos_pendentes(session)
    linhas = []
    total_previsto = 0.0
    for ag in pendentes:
        servs = _calcula_servicos(session, ag.id)
        profs = _calcula_profissionais(session, ag.id)
        cliente = _calcula_cliente(session, ag)
        valor = sum((s.preco or 0.0) for s in servs)
        total_previsto += valor
        linhas.append(
            {
                "id": ag.id,
                "data_fmt": ag.data_hora.strftime("%d/%m/%Y"),
                "hora": ag.data_hora.strftime("%H:%M"),
                "cliente": cliente.nome if cliente is not None else None,
                "profissionais": ", ".join(p.nome for p in profs) if profs else "—",
                "servicos": ", ".join(s.nome for s in servs) if servs else "—",
                "valor": valor,
                "tem_inativo": any(not p.ativo for p in profs),
            }
        )
    return templates.TemplateResponse(
        "agendamentos/a_receber.html",
        {
            "request": request,
            "active": "agendamentos",
            "linhas": linhas,
            "n": len(linhas),
            "total_previsto": total_previsto,
        },
    )


@router.get("/novo-modal")
def novo_modal(
    request: Request,
    data: Optional[str] = None,
    hora: Optional[str] = None,
    profissional_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    ag = Agendamento(data_hora=datetime.now())
    ag.id = None
    data_default = (data or "").strip()
    if not data_default:
        data_default = date.today().strftime("%Y-%m-%d")
    hora_default = (hora or "").strip()
    contexto = _contexto_form(
        session,
        ag,
        action="/agendamentos/",
        titulo="Novo agendamento",
        data_default=data_default,
        hora_default=hora_default,
        profissional_id_default=profissional_id,
        request=request,
    )
    return templates.TemplateResponse("agendamentos/_form_modal.html", contexto)


@router.get("/{agendamento_id}/card")
def card(
    agendamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    """Fragmento _card.html — modal de detalhes/quick-edit.

    Contrato do contexto:
      - request: Request
      - active: "agendamentos"
      - agendamento: Agendamento
      - cliente: Cliente | None
      - profissionais: list[Profissional]
      - servicos: list[Servico]
      - duracao_efetiva: int
      - duracao_calculada: int (= max(servico.duracao_minutos) ou 60 se vazio)
      - data_default: str (YYYY-MM-DD)
      - hora_default: str (HH:MM)
      - erro: str | None
    """
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)
    return _render_card(request, session, ag, erro=None)


def _render_card(
    request: Request,
    session: Session,
    ag: Agendamento,
    erro: Optional[str],
    *,
    data_default: Optional[str] = None,
    hora_default: Optional[str] = None,
    duracao_default: Optional[int] = None,
    status_code: int = 200,
) -> Response:
    servs = _calcula_servicos(session, ag.id)
    profs = _calcula_profissionais(session, ag.id)
    cliente = _calcula_cliente(session, ag)
    dur = _duracao_efetiva(ag, servs)
    if servs:
        try:
            dur_calc = max(s.duracao_minutos for s in servs)
        except ValueError:
            dur_calc = 60
    else:
        dur_calc = 60
    contexto = {
        "request": request,
        "active": "agendamentos",
        "agendamento": ag,
        "cliente": cliente,
        "profissionais": profs,
        "servicos": servs,
        "duracao_efetiva": dur,
        "duracao_calculada": dur_calc,
        "data_default": data_default or ag.data_hora.strftime("%Y-%m-%d"),
        "hora_default": hora_default or ag.data_hora.strftime("%H:%M"),
        "duracao_default": (
            duracao_default
            if duracao_default is not None
            else ag.duracao_override
        ),
        "erro": erro,
    }
    contexto.update(_info_pagamento(session, ag.id))
    return templates.TemplateResponse(
        "agendamentos/_card.html",
        contexto,
        status_code=status_code,
    )


@router.get("/{agendamento_id}/editar")
def editar(
    agendamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)
    contexto = _contexto_form(
        session,
        ag,
        action=f"/agendamentos/{ag.id}",
        titulo="Editar Agendamento",
        request=request,
    )
    return templates.TemplateResponse("agendamentos/form_edit.html", contexto)


@router.post("/")
def criar(
    request: Request,
    data: str = Form(""),
    hora: str = Form(""),
    cliente_id: str = Form(""),
    duracao_override: str = Form(""),
    observacoes: str = Form(""),
    profissional_ids: List[str] = Form(default=[]),
    servico_ids: List[str] = Form(default=[]),
    encaixe: str = Form(""),
    session: Session = Depends(get_session),
):
    prof_ids = _parse_ids_lista(profissional_ids)
    serv_ids = _parse_ids_lista(servico_ids)
    data_hora = _parse_data_hora(data, hora)
    cli_id = _parse_cliente_id(cliente_id)
    dur_override = _parse_duracao_override(duracao_override)
    obs = _vazio_para_none(observacoes)
    if obs is not None and len(obs) > 2000:
        obs = obs[:2000]
    eh_encaixe = bool(encaixe)

    erro, _fim, _dur = _validar_agendamento(
        session,
        profissional_ids=prof_ids,
        servico_ids=serv_ids,
        data_hora=data_hora,
        duracao_override=dur_override,
        modo="criar",
        encaixe=eh_encaixe,
    )

    if erro:
        agendamento_mem = Agendamento(
            data_hora=data_hora or datetime.now(),
            cliente_id=cli_id,
            duracao_override=dur_override,
            observacoes=obs,
            encaixe=eh_encaixe,
        )
        agendamento_mem.id = None
        contexto = _contexto_form(
            session,
            agendamento_mem,
            action="/agendamentos/",
            titulo="Novo agendamento",
            erro=erro,
            data_default=(data or "").strip(),
            hora_default=(hora or "").strip(),
            request=request,
            duracao_default=dur_override,
            observacoes_default=obs or "",
            cliente_id_default=cli_id,
            profissional_ids_default=prof_ids,
            servico_ids_default=serv_ids,
        )
        return templates.TemplateResponse(
            "agendamentos/_form_modal.html",
            contexto,
            status_code=400,
        )

    ag = Agendamento(
        data_hora=data_hora,
        cliente_id=cli_id,
        duracao_override=dur_override,
        observacoes=obs,
        encaixe=eh_encaixe,
    )
    session.add(ag)
    session.flush()  # garante ag.id
    _substitui_links(session, ag.id, prof_ids, serv_ids)
    session.commit()
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.post("/{agendamento_id}")
def atualizar(
    agendamento_id: int,
    request: Request,
    data: str = Form(""),
    hora: str = Form(""),
    cliente_id: str = Form(""),
    duracao_override: str = Form(""),
    observacoes: str = Form(""),
    profissional_ids: List[str] = Form(default=[]),
    servico_ids: List[str] = Form(default=[]),
    encaixe: str = Form(""),
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)

    prof_ids = _parse_ids_lista(profissional_ids)
    serv_ids = _parse_ids_lista(servico_ids)
    data_hora = _parse_data_hora(data, hora)
    cli_id = _parse_cliente_id(cliente_id)
    dur_override = _parse_duracao_override(duracao_override)
    obs = _vazio_para_none(observacoes)
    if obs is not None and len(obs) > 2000:
        obs = obs[:2000]
    eh_encaixe = bool(encaixe)

    erro, _fim, _dur = _validar_agendamento(
        session,
        profissional_ids=prof_ids,
        servico_ids=serv_ids,
        data_hora=data_hora,
        duracao_override=dur_override,
        modo="atualizar",
        ag_atual=ag,
        encaixe=eh_encaixe,
    )

    if erro:
        agendamento_mem = Agendamento(
            data_hora=data_hora or ag.data_hora,
            cliente_id=cli_id,
            duracao_override=dur_override,
            observacoes=obs,
            encaixe=eh_encaixe,
        )
        agendamento_mem.id = ag.id
        contexto = _contexto_form(
            session,
            agendamento_mem,
            action=f"/agendamentos/{ag.id}",
            titulo="Editar Agendamento",
            erro=erro,
            data_default=(data or "").strip(),
            hora_default=(hora or "").strip(),
            request=request,
            duracao_default=dur_override,
            observacoes_default=obs or "",
            cliente_id_default=cli_id,
            profissional_ids_default=prof_ids,
            servico_ids_default=serv_ids,
        )
        return templates.TemplateResponse(
            "agendamentos/form_edit.html",
            contexto,
            status_code=400,
        )

    ag.data_hora = data_hora
    ag.cliente_id = cli_id
    ag.duracao_override = dur_override
    ag.observacoes = obs
    ag.encaixe = eh_encaixe
    session.add(ag)
    _substitui_links(session, ag.id, prof_ids, serv_ids)
    session.commit()
    data_str = ag.data_hora.strftime("%Y-%m-%d")
    return RedirectResponse(url=f"/agendamentos/?data={data_str}", status_code=303)


@router.post("/{agendamento_id}/horario")
def atualizar_horario(
    agendamento_id: int,
    request: Request,
    data: str = Form(""),
    hora: str = Form(""),
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)

    data_hora = _parse_data_hora(data, hora)
    prof_ids = [p.id for p in _calcula_profissionais(session, ag.id)]
    serv_ids = [s.id for s in _calcula_servicos(session, ag.id)]

    erro, _fim, _dur = _validar_agendamento(
        session,
        profissional_ids=prof_ids,
        servico_ids=serv_ids,
        data_hora=data_hora,
        duracao_override=ag.duracao_override,
        modo="horario",
        ag_atual=ag,
        encaixe=ag.encaixe,
    )

    if erro:
        return _render_card(
            request,
            session,
            ag,
            erro=erro,
            data_default=(data or "").strip(),
            hora_default=(hora or "").strip(),
            status_code=400,
        )

    ag.data_hora = data_hora
    session.add(ag)
    session.commit()
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.post("/{agendamento_id}/duracao")
def atualizar_duracao(
    agendamento_id: int,
    request: Request,
    duracao_override: str = Form(""),
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)

    dur_override = _parse_duracao_override(duracao_override)
    prof_ids = [p.id for p in _calcula_profissionais(session, ag.id)]
    serv_ids = [s.id for s in _calcula_servicos(session, ag.id)]

    erro, _fim, _dur = _validar_agendamento(
        session,
        profissional_ids=prof_ids,
        servico_ids=serv_ids,
        data_hora=ag.data_hora,
        duracao_override=dur_override,
        modo="duracao",
        ag_atual=ag,
        encaixe=ag.encaixe,
    )

    if erro:
        return _render_card(
            request,
            session,
            ag,
            erro=erro,
            duracao_default=dur_override,
            status_code=400,
        )

    ag.duracao_override = dur_override
    session.add(ag)
    session.commit()
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.post("/{agendamento_id}/excluir")
def excluir(
    agendamento_id: int,
    session: Session = Depends(get_session),
    _ator: Usuario = Depends(requer_admin),
):
    # Somente admin/superadmin excluem agendamentos. requer_admin redireciona
    # para "/" (ou HX-Redirect) quem não tem permissão antes de chegar aqui.
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        data_str = date.today().strftime("%Y-%m-%d")
        return RedirectResponse(
            url=f"/agendamentos/?data={data_str}", status_code=303
        )

    data_str = ag.data_hora.strftime("%Y-%m-%d")

    # Estorna o pagamento (se houver): remove lançamentos e devolve estoque das
    # vendas vinculadas — senão sobrariam receitas órfãs apontando p/ agendamento inexistente.
    _estornar_pagamento(session, ag.id)

    # Deleta links primeiro
    links_serv = session.exec(
        select(AgendamentoServico).where(
            AgendamentoServico.agendamento_id == ag.id
        )
    ).all()
    for l in links_serv:
        session.delete(l)
    links_prof = session.exec(
        select(AgendamentoProfissional).where(
            AgendamentoProfissional.agendamento_id == ag.id
        )
    ).all()
    for l in links_prof:
        session.delete(l)
    session.flush()
    session.delete(ag)
    session.commit()

    return RedirectResponse(url=f"/agendamentos/?data={data_str}", status_code=303)


# ---------------------------------------------------------------------------
# Pagamento (receita gerada a partir do agendamento)
# ---------------------------------------------------------------------------
#
# "Pago" = existe ao menos um lançamento de receita com este agendamento_id.
# O pagamento gera: uma receita de Serviços (valor editável) + uma receita de
# Produtos por item vendido (cada uma com baixa de estoque via saida_venda).


def _parse_valor_money(valor):
    """Retorna (valor_float, eh_invalido). Aceita vírgula. Vazio → (0.0, False)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return 0.0, False
    v = valor.strip()
    v = v.replace(".", "").replace(",", ".") if "," in v else v
    try:
        f = float(v)
    except (ValueError, TypeError):
        return 0.0, True
    if f < 0:
        return 0.0, True
    return round(f, 2), False


def _calc_desconto(bruto, tipo_raw, valor_raw):
    """Calcula o desconto de um item. Retorna (tipo, desconto_R$, liquido).

    tipo "pct" → desconto = bruto * %/100 (% clampado em 100).
    tipo "brl" → desconto = valor em R$ (clampado ao bruto).
    Nunca confia na conta do cliente: recalcula a partir do bruto do servidor.
    """
    tipo = str(tipo_raw or "").strip().lower()
    if tipo not in ("brl", "pct"):
        tipo = "brl"
    val, invalido = _parse_valor_money(valor_raw)
    if invalido:
        val = 0.0
    bruto = round(bruto or 0.0, 2)
    if tipo == "pct":
        pct = min(max(val, 0.0), 100.0)
        desc = bruto * pct / 100.0
    else:
        desc = min(max(val, 0.0), bruto)
    desc = round(desc, 2)
    net = round(bruto - desc, 2)
    if net < 0:
        net = 0.0
    return tipo, desc, net


def _lancamentos_do_agendamento(session: Session, agendamento_id: int):
    return session.exec(
        select(LancamentoFinanceiro).where(
            LancamentoFinanceiro.agendamento_id == agendamento_id
        )
    ).all()


def _info_pagamento(session: Session, agendamento_id: int) -> dict:
    if agendamento_id is None:
        return {"pago": False, "total_pago": 0.0}
    lancs = _lancamentos_do_agendamento(session, agendamento_id)
    total = sum(l.valor for l in lancs if l.tipo == "receita")
    return {"pago": len(lancs) > 0, "total_pago": total}


def _categoria_receita(session: Session, nome: str) -> CategoriaFinanceira:
    """Categoria de receita por nome (Serviços/Produtos); cria se não existir."""
    cat = session.exec(
        select(CategoriaFinanceira)
        .where(CategoriaFinanceira.tipo == "receita")
        .where(CategoriaFinanceira.nome == nome)
    ).first()
    if cat is None:
        cat = CategoriaFinanceira(nome=nome, tipo="receita", ativo=True)
        session.add(cat)
        session.flush()
    return cat


def _estornar_pagamento(session: Session, agendamento_id: int) -> None:
    """Remove lançamentos do agendamento e devolve ao estoque as vendas vinculadas."""
    for l in _lancamentos_do_agendamento(session, agendamento_id):
        session.delete(l)
    vendas = session.exec(
        select(MovimentacaoEstoque)
        .where(MovimentacaoEstoque.agendamento_id == agendamento_id)
        .where(MovimentacaoEstoque.tipo == "saida_venda")
    ).all()
    for mov in vendas:
        produto = session.get(Produto, mov.produto_id)
        if produto is not None:
            produto.estoque_atual += mov.quantidade
            session.add(produto)
        session.delete(mov)
    session.flush()


def _render_pagamento(
    request: Request,
    session: Session,
    ag: Agendamento,
    erro: Optional[str],
    *,
    data_default: Optional[str] = None,
    status_code: int = 200,
) -> Response:
    servs = _calcula_servicos(session, ag.id)
    cliente = _calcula_cliente(session, ag)
    profs = _calcula_profissionais(session, ag.id)
    total_servicos = sum((s.preco or 0.0) for s in servs)
    servs_json = [
        {"id": s.id, "nome": s.nome, "preco": round(s.preco or 0.0, 2)}
        for s in servs
    ]
    # Lista TODOS os produtos ativos (inclusive estoque 0): os sem estoque
    # aparecem desabilitados no seletor em vez de sumir.
    produtos = session.exec(
        select(Produto)
        .where(Produto.ativo == True)  # noqa: E712
        .order_by(Produto.nome)
    ).all()
    produtos_json = [
        {
            "id": p.id,
            "nome": p.nome,
            "preco": round(p.preco_venda or 0.0, 2),
            "estoque": p.estoque_atual,
        }
        for p in produtos
    ]
    contexto = {
        "request": request,
        "active": "agendamentos",
        "agendamento": ag,
        "cliente": cliente,
        "profissionais": profs,
        "servicos": servs,
        "total_servicos": total_servicos,
        "servs_json": servs_json,
        "produtos_json": produtos_json,
        "data_default": data_default or date.today().strftime("%Y-%m-%d"),
        "hora": ag.data_hora.strftime("%H:%M"),
        "erro": erro,
    }
    return templates.TemplateResponse(
        "agendamentos/_pagamento_modal.html", contexto, status_code=status_code
    )


@router.get("/{agendamento_id}/pagamento")
def pagamento_form(
    agendamento_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)
    if _info_pagamento(session, ag.id)["pago"]:
        # Já pago — volta para o card (que mostra o selo e o botão de estorno).
        return _render_card(request, session, ag, erro=None)
    return _render_pagamento(request, session, ag, erro=None)


@router.post("/{agendamento_id}/pagamento")
def pagamento(
    agendamento_id: int,
    request: Request,
    data: str = Form(""),
    servico_id: List[str] = Form(default=[]),
    servico_desc_tipo: List[str] = Form(default=[]),
    servico_desc_valor: List[str] = Form(default=[]),
    produto_id: List[str] = Form(default=[]),
    quantidade: List[str] = Form(default=[]),
    produto_desc_tipo: List[str] = Form(default=[]),
    produto_desc_valor: List[str] = Form(default=[]),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(requer_login),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)

    # Autoria — quem está fechando a comanda (carimbada em cada lançamento).
    usuario_nome = usuario.nome_exibicao or usuario.nome_usuario

    if _info_pagamento(session, ag.id)["pago"]:
        return _render_pagamento(
            request, session, ag,
            erro="Este agendamento já tem pagamento registrado.",
            status_code=400,
        )

    data_val = _parse_data_query(data)  # default hoje

    # --- Serviços do atendimento (bruto = preço de catálogo) + desconto por item ---
    servs = _calcula_servicos(session, ag.id)
    preco_serv = {s.id: round(s.preco or 0.0, 2) for s in servs}
    nome_serv = {s.id: s.nome for s in servs}
    pct_serv = {s.id: s.comissao_pct or 0.0 for s in servs}
    serv_linhas = []  # (bruto, tipo, desc, net, nome, comissao_pct)
    for sid_raw, t_raw, v_raw in zip(servico_id, servico_desc_tipo, servico_desc_valor):
        try:
            sid = int(str(sid_raw).strip())
        except (ValueError, TypeError):
            continue
        if sid not in preco_serv:
            continue
        bruto = preco_serv[sid]
        if bruto <= 0:
            continue  # serviço sem preço não gera lançamento
        tipo, desc, net = _calc_desconto(bruto, t_raw, v_raw)
        serv_linhas.append(
            (bruto, tipo, desc, net, nome_serv.get(sid, "Serviço"), pct_serv[sid])
        )

    # --- Produtos vendidos + desconto por item (valida estoque antes de gravar) ---
    pares = zip(produto_id, quantidade, produto_desc_tipo, produto_desc_valor)
    vendas = []  # (produto, qtd, bruto, tipo, desc, net)
    for pid_raw, qtd_raw, t_raw, v_raw in pares:
        try:
            pid = int(str(pid_raw).strip())
        except (ValueError, TypeError):
            continue
        try:
            qtd = int(str(qtd_raw).strip())
        except (ValueError, TypeError):
            qtd = 0
        if qtd <= 0:
            continue
        produto = session.get(Produto, pid)
        if produto is None or not produto.ativo:
            return _render_pagamento(
                request, session, ag, erro="Produto inválido na venda.",
                data_default=data.strip(), status_code=400,
            )
        if qtd > produto.estoque_atual:
            return _render_pagamento(
                request, session, ag,
                erro=f"Estoque insuficiente de {produto.nome} "
                     f"(disponível: {produto.estoque_atual}).",
                data_default=data.strip(), status_code=400,
            )
        bruto = round((produto.preco_venda or 0.0) * qtd, 2)
        tipo, desc, net = _calc_desconto(bruto, t_raw, v_raw)
        vendas.append((produto, qtd, bruto, tipo, desc, net))

    if not serv_linhas and not vendas:
        return _render_pagamento(
            request, session, ag,
            erro="Informe ao menos um serviço com preço ou um produto vendido.",
            data_default=data.strip(), status_code=400,
        )

    cliente = _calcula_cliente(session, ag)
    cli_nome = cliente.nome if cliente is not None else "Sem cliente"

    # 1) Uma receita de Serviços POR serviço (guarda bruto/desconto/líquido).
    if serv_linhas:
        cat_serv = _categoria_receita(session, "Serviços")
        for bruto, tipo, desc, net, nome, pct in serv_linhas:
            session.add(
                LancamentoFinanceiro(
                    tipo="receita",
                    valor=net,
                    valor_bruto=bruto,
                    desconto_valor=desc,
                    desconto_tipo=tipo if desc > 0 else None,
                    data=data_val,
                    categoria_id=cat_serv.id,
                    descricao=nome[:200],
                    comissao_pct=pct,
                    agendamento_id=ag.id,
                    usuario_id=usuario.id,
                    usuario_nome=usuario_nome,
                )
            )

    # 2) Cada produto vendido: baixa de estoque + receita de Produtos.
    if vendas:
        cat_prod = _categoria_receita(session, "Produtos")
        for produto, qtd, bruto, tipo, desc, net in vendas:
            produto.estoque_atual -= qtd
            session.add(produto)
            session.add(
                MovimentacaoEstoque(
                    produto_id=produto.id,
                    tipo="saida_venda",
                    quantidade=qtd,
                    agendamento_id=ag.id,
                    observacoes=f"Venda no atendimento de {cli_nome}",
                )
            )
            session.add(
                LancamentoFinanceiro(
                    tipo="receita",
                    valor=net,
                    valor_bruto=bruto,
                    desconto_valor=desc,
                    desconto_tipo=tipo if desc > 0 else None,
                    data=data_val,
                    categoria_id=cat_prod.id,
                    descricao=f"{produto.nome} (x{qtd})"[:200],
                    agendamento_id=ag.id,
                    usuario_id=usuario.id,
                    usuario_nome=usuario_nome,
                )
            )

    session.commit()
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.post("/{agendamento_id}/pagamento/estornar")
def pagamento_estornar(
    agendamento_id: int,
    session: Session = Depends(get_session),
):
    ag = session.get(Agendamento, agendamento_id)
    if ag is None:
        return RedirectResponse(url="/agendamentos/", status_code=303)
    _estornar_pagamento(session, ag.id)
    session.commit()
    return Response(status_code=204, headers={"HX-Refresh": "true"})
