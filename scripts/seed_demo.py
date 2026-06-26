"""Popula o banco com um dataset de demonstração para testes manuais.

Mantém os usuários (logins) e as categorias financeiras padrão; LIMPA e recria
todas as tabelas de negócio (clientes, profissionais, serviços, produtos,
agendamentos + vínculos, lançamentos e movimentações de estoque).

Replica fielmente a lógica de pagamento do app (`agendamentos.pagamento`):
cada serviço vira 1 receita "Serviços"; cada produto vendido baixa estoque
(movimentação `saida_venda` vinculada) e vira 1 receita "Produtos"; descontos
por item recalculados via `_calc_desconto`.

Uso:  python3 scripts/seed_demo.py
(Re-executável: limpa e repopula a cada run.)
"""
import pathlib
import sys
from datetime import datetime, time, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.models.agendamento import (  # noqa: E402
    Agendamento,
    AgendamentoProfissional,
    AgendamentoServico,
)
from app.models.cliente import Cliente  # noqa: E402
from app.models.lancamento_financeiro import LancamentoFinanceiro  # noqa: E402
from app.models.movimentacao_estoque import MovimentacaoEstoque  # noqa: E402
from app.models.produto import Produto  # noqa: E402
from app.models.profissional import Profissional  # noqa: E402
from app.models.servico import Servico  # noqa: E402
from app.routers.agendamentos import (  # noqa: E402
    _calc_desconto,
    _calcula_servicos,
    _categoria_receita,
)

AGORA = datetime.now()
HOJE = AGORA.date()


def _del_all(session, modelo):
    for row in session.exec(select(modelo)).all():
        session.delete(row)


def limpar(session):
    """Apaga dados de negócio em ordem segura de FK. Mantém usuário e categorias."""
    for modelo in (
        LancamentoFinanceiro,
        MovimentacaoEstoque,
        AgendamentoServico,
        AgendamentoProfissional,
        Agendamento,
        Produto,
        Servico,
        Profissional,
        Cliente,
    ):
        _del_all(session, modelo)
    session.commit()


def snap30(dt):
    """Arredonda para :00 ou :30 (visual mais realista na agenda)."""
    return dt.replace(minute=(0 if dt.minute < 30 else 30), second=0, microsecond=0)


def dia(offset, h, m=0):
    return datetime.combine(HOJE + timedelta(days=offset), time(h, m))


def add_agendamento(session, quando, cliente, servicos, profissionais, obs=None):
    ag = Agendamento(data_hora=quando, cliente_id=cliente.id if cliente else None,
                     observacoes=obs, criado_em=quando - timedelta(days=1))
    session.add(ag)
    session.flush()
    for s in servicos:
        session.add(AgendamentoServico(agendamento_id=ag.id, servico_id=s.id))
    for p in profissionais:
        session.add(AgendamentoProfissional(agendamento_id=ag.id, profissional_id=p.id))
    session.flush()
    return ag


def pagar(session, ag, data_lanc, serv_desc=None, vendas=None):
    """Replica agendamentos.pagamento(): receitas de serviço/produto + estoque."""
    serv_desc = serv_desc or {}        # {servico_id: (tipo, valor_raw)}
    vendas = vendas or []              # [(produto, qtd, tipo, valor_raw)]
    quando = datetime.combine(data_lanc, time(12, 0))

    servs = _calcula_servicos(session, ag.id)
    cat_serv = _categoria_receita(session, "Serviços")
    for s in servs:
        bruto = round(s.preco or 0.0, 2)
        if bruto <= 0:
            continue
        t_raw, v_raw = serv_desc.get(s.id, ("brl", ""))
        tipo, desc, net = _calc_desconto(bruto, t_raw, v_raw)
        session.add(LancamentoFinanceiro(
            tipo="receita", valor=net, valor_bruto=bruto, desconto_valor=desc,
            desconto_tipo=tipo if desc > 0 else None, data=data_lanc,
            categoria_id=cat_serv.id, descricao=s.nome[:200],
            agendamento_id=ag.id, criado_em=quando,
        ))

    if vendas:
        cat_prod = _categoria_receita(session, "Produtos")
        for produto, qtd, t_raw, v_raw in vendas:
            if qtd <= 0 or qtd > produto.estoque_atual:
                print(f"  ! venda ignorada (estoque insuf.): {produto.nome} x{qtd} "
                      f"(disp. {produto.estoque_atual})")
                continue
            bruto = round((produto.preco_venda or 0.0) * qtd, 2)
            tipo, desc, net = _calc_desconto(bruto, t_raw, v_raw)
            produto.estoque_atual -= qtd
            session.add(produto)
            session.add(MovimentacaoEstoque(
                produto_id=produto.id, tipo="saida_venda", quantidade=qtd,
                agendamento_id=ag.id, observacoes="Venda no atendimento", criado_em=quando,
            ))
            session.add(LancamentoFinanceiro(
                tipo="receita", valor=net, valor_bruto=bruto, desconto_valor=desc,
                desconto_tipo=tipo if desc > 0 else None, data=data_lanc,
                categoria_id=cat_prod.id, descricao=f"{produto.nome} (x{qtd})"[:200],
                agendamento_id=ag.id, criado_em=quando,
            ))
    session.flush()


def despesa(session, nome_cat, valor, data_lanc, descricao):
    from app.models.categoria_financeira import CategoriaFinanceira
    cat = session.exec(
        select(CategoriaFinanceira)
        .where(CategoriaFinanceira.tipo == "despesa")
        .where(CategoriaFinanceira.nome == nome_cat)
    ).first()
    session.add(LancamentoFinanceiro(
        tipo="despesa", valor=round(valor, 2), data=data_lanc,
        categoria_id=cat.id if cat else None, descricao=descricao,
        criado_em=datetime.combine(data_lanc, time(9, 0)),
    ))


def main():
    init_db()
    with Session(engine) as s:
        print("Limpando dados de negócio (mantendo logins + categorias)...")
        limpar(s)

        # ---------------- CLIENTES ----------------
        clientes_def = [
            ("Marina Costa", "(11) 98877-1234", "marina.costa@gmail.com", True),
            ("Fernanda Dias", "(11) 99654-8820", "fernanda.dias@hotmail.com", True),
            ("Patrícia Lemos", "(11) 98123-9001", "patricia.lemos@outlook.com", True),
            ("Bianca Reis", "(11) 98456-2210", None, True),
            ("Camila Rocha", "(11) 99988-7766", "camila.rocha@gmail.com", True),
            ("Letícia Alves", "(11) 97766-5544", "leticia.alves@gmail.com", True),
            ("Helena Martins", "(11) 97712-3344", None, True),
            ("Juliana Pereira", "(11) 96655-1122", "ju.pereira@gmail.com", True),
            ("Beatriz Nunes", "(11) 98090-7766", "bia.nunes@yahoo.com.br", True),
            ("Carolina Mendes", "(11) 99321-8800", "carol.mendes@gmail.com", True),
            ("Rafael Torres", "(11) 98233-1190", "rafael.torres@gmail.com", True),
            ("Tatiane Lima", "(11) 97001-4567", None, True),
            ("Sofia Andrade", "(11) 99001-0000", "sofia.andrade@gmail.com", False),
            ("Gustavo Lima", "(11) 98330-1199", None, False),
        ]
        clientes = {}
        for nome, tel, email, ativo in clientes_def:
            c = Cliente(nome=nome, telefone=tel, email=email, ativo=ativo)
            s.add(c)
            clientes[nome] = c
        s.flush()

        # ------------- PROFISSIONAIS (4) -------------
        profs_def = [
            ("Carla Bianchi", "(11) 98111-0001", "carla@salao.com"),
            ("Renata Souza", "(11) 98111-0002", "renata@salao.com"),
            ("Aline Ferreira", "(11) 98111-0003", None),
            ("Patrícia Gomes", "(11) 98111-0004", "patricia.g@salao.com"),
        ]
        profs = {}
        for nome, tel, email in profs_def:
            p = Profissional(nome=nome, telefone=tel, email=email, ativo=True)
            s.add(p)
            profs[nome] = p
        s.flush()

        # --------------- SERVIÇOS ---------------
        servs_def = [
            ("Corte Feminino", 70.0, 45, True),
            ("Corte Masculino", 45.0, 30, True),
            ("Escova", 50.0, 40, True),
            ("Coloração", 180.0, 120, True),
            ("Luzes / Mechas", 280.0, 150, True),
            ("Hidratação", 90.0, 60, True),
            ("Progressiva", 220.0, 120, True),
            ("Manicure", 35.0, 40, True),
            ("Pedicure", 45.0, 45, True),
            ("Design de Sobrancelha", 40.0, 30, True),
            ("Maquiagem", 150.0, 60, True),
            ("Depilação (cera)", 60.0, 30, True),
            ("Penteado de Festa", 130.0, 60, False),  # inativo (testar filtro)
        ]
        servs = {}
        for nome, preco, dur, ativo in servs_def:
            sv = Servico(nome=nome, preco=preco, duracao_minutos=dur, ativo=ativo)
            s.add(sv)
            servs[nome] = sv
        s.flush()

        # --------------- PRODUTOS ---------------
        # (nome, preco_venda, custo, estoque, minimo, ativo)
        prods_def = [
            ("Shampoo Hidratante 300ml", 45.0, 22.0, 20, 5, True),
            ("Condicionador 300ml", 45.0, 22.0, 18, 5, True),
            ("Máscara Capilar 250g", 60.0, 30.0, 12, 4, True),
            ("Óleo de Argan 60ml", 80.0, 40.0, 8, 3, True),
            ("Leave-in 200ml", 38.0, 18.0, 15, 5, True),
            ("Protetor Térmico 150ml", 55.0, 28.0, 10, 3, True),
            ("Esmalte", 12.0, 5.0, 40, 10, True),
            ("Tintura Profissional", 35.0, 18.0, 6, 8, True),     # abaixo do mínimo (alerta)
            ("Água Oxigenada 900ml", 25.0, 10.0, 3, 5, True),     # abaixo do mínimo (alerta)
            ("Removedor de Esmalte", 15.0, 6.0, 0, 4, True),      # sem estoque (testar venda)
            ("Pomada Modeladora 100g", 40.0, 19.0, 9, 3, False),  # inativo (testar filtro)
        ]
        prods = {}
        for nome, pv, custo, est, mini, ativo in prods_def:
            pr = Produto(nome=nome, preco_venda=pv, custo=custo, estoque_atual=est,
                         estoque_minimo=mini, unidade="un", ativo=ativo)
            s.add(pr)
            prods[nome] = pr
        s.flush()

        # ----------- MOVIMENTAÇÕES DE ESTOQUE (histórico entrada/uso) -----------
        movs = [
            ("Shampoo Hidratante 300ml", "entrada", 10, 12, "Reposição fornecedor"),
            ("Condicionador 300ml", "entrada", 10, 12, "Reposição fornecedor"),
            ("Esmalte", "entrada", 20, 9, "Compra lote esmaltes"),
            ("Máscara Capilar 250g", "saida_uso", 2, 6, "Uso interno em atendimento"),
            ("Óleo de Argan 60ml", "saida_uso", 1, 4, "Amostra cliente"),
            ("Tintura Profissional", "saida_uso", 3, 3, "Uso em coloração"),
        ]
        for nome, tipo, qtd, dias_atras, obs in movs:
            pr = prods[nome]
            quando = AGORA - timedelta(days=dias_atras)
            s.add(MovimentacaoEstoque(produto_id=pr.id, tipo=tipo, quantidade=qtd,
                                      observacoes=obs, criado_em=quando))
            # ajusta estoque conforme o tipo (entrada soma, saida_uso subtrai)
            pr.estoque_atual += qtd if tipo == "entrada" else -qtd
            s.add(pr)
        s.flush()

        # --------------- AGENDAMENTOS ---------------
        def C(n): return clientes[n]
        def P(n): return profs[n]
        def S(n): return servs[n]

        ags = {}  # rotulo -> (ag, data_pagamento|None, serv_desc, vendas)

        # ---- HOJE: passados (serão pagos) ----
        ags["h_p1"] = (add_agendamento(s, snap30(AGORA - timedelta(hours=3)),
                       C("Marina Costa"), [S("Corte Feminino"), S("Escova")],
                       [P("Carla Bianchi")]), HOJE,
                       {}, [(prods["Óleo de Argan 60ml"], 1, "brl", "")])
        ags["h_p2"] = (add_agendamento(s, snap30(AGORA - timedelta(hours=1, minutes=30)),
                       C("Helena Martins"), [S("Manicure"), S("Pedicure")],
                       [P("Aline Ferreira")]), HOJE, {}, [])

        # ---- HOJE: futuros (NÃO pagos → aparecem na Home "próximos") ----
        add_agendamento(s, snap30(AGORA + timedelta(hours=1)),
                        C("Bianca Reis"), [S("Design de Sobrancelha")], [P("Patrícia Gomes")])
        add_agendamento(s, snap30(AGORA + timedelta(hours=2, minutes=30)),
                        C("Fernanda Dias"), [S("Coloração")], [P("Renata Souza")])
        add_agendamento(s, snap30(AGORA + timedelta(hours=4)),
                        C("Camila Rocha"), [S("Escova"), S("Maquiagem")],
                        [P("Carla Bianchi"), P("Patrícia Gomes")])

        # ---- DIAS PASSADOS (pagos, com variações de desconto e venda) ----
        ags["d2"] = (add_agendamento(s, dia(-2, 10, 0), C("Patrícia Lemos"),
                     [S("Luzes / Mechas")], [P("Renata Souza")]), HOJE - timedelta(days=2),
                     {}, [(prods["Máscara Capilar 250g"], 1, "brl", "")])
        ags["d3"] = (add_agendamento(s, dia(-3, 14, 0), C("Juliana Pereira"),
                     [S("Corte Feminino"), S("Hidratação")], [P("Carla Bianchi")]),
                     HOJE - timedelta(days=3),
                     {S("Hidratação").id: ("pct", "50")},  # 50% off na hidratação
                     [(prods["Leave-in 200ml"], 1, "brl", "")])
        ags["d4"] = (add_agendamento(s, dia(-4, 11, 0), C("Beatriz Nunes"),
                     [S("Progressiva")], [P("Renata Souza")]), HOJE - timedelta(days=4),
                     {S("Progressiva").id: ("brl", "20")},  # R$20 off
                     [])
        ags["d6"] = (add_agendamento(s, dia(-6, 9, 30), C("Rafael Torres"),
                     [S("Corte Masculino")], [P("Aline Ferreira")]), HOJE - timedelta(days=6),
                     {}, [(prods["Shampoo Hidratante 300ml"], 1, "brl", "")])
        ags["d8"] = (add_agendamento(s, dia(-8, 16, 0), C("Carolina Mendes"),
                     [S("Maquiagem"), S("Escova")], [P("Patrícia Gomes"), P("Carla Bianchi")]),
                     HOJE - timedelta(days=8), {}, [])
        ags["d10"] = (add_agendamento(s, dia(-10, 13, 30), C("Tatiane Lima"),
                      [S("Manicure"), S("Design de Sobrancelha")], [P("Aline Ferreira")]),
                      HOJE - timedelta(days=10), {}, [(prods["Esmalte"], 2, "brl", "")])
        ags["d14"] = (add_agendamento(s, dia(-14, 15, 0), C("Sofia Andrade"),
                      [S("Coloração"), S("Corte Feminino")], [P("Renata Souza")]),
                      HOJE - timedelta(days=14), {}, [])  # cliente inativa, histórico pago
        ags["d18"] = (add_agendamento(s, dia(-18, 10, 30), C("Marina Costa"),
                      [S("Hidratação")], [P("Carla Bianchi")]), HOJE - timedelta(days=18),
                      {}, [(prods["Protetor Térmico 150ml"], 1, "brl", "")])

        # ---- DIAS PASSADOS NÃO pagos (testar atendimento sem pagamento no histórico) ----
        add_agendamento(s, dia(-1, 17, 0), C("Fernanda Dias"),
                        [S("Escova")], [P("Carla Bianchi")])
        add_agendamento(s, dia(-5, 18, 30), C("Bianca Reis"),
                        [S("Pedicure")], [P("Aline Ferreira")])

        # ---- FUTUROS (agenda dos próximos dias, não pagos) ----
        add_agendamento(s, dia(1, 9, 0), C("Camila Rocha"),
                        [S("Coloração")], [P("Renata Souza")])
        add_agendamento(s, dia(1, 14, 0), C("Juliana Pereira"),
                        [S("Corte Feminino"), S("Escova")], [P("Carla Bianchi")])
        add_agendamento(s, dia(2, 11, 0), C("Beatriz Nunes"),
                        [S("Manicure"), S("Pedicure")], [P("Aline Ferreira")])
        add_agendamento(s, dia(3, 16, 0), C("Patrícia Lemos"),
                        [S("Maquiagem")], [P("Patrícia Gomes")], obs="Casamento à noite")
        add_agendamento(s, dia(5, 10, 0), C("Rafael Torres"),
                        [S("Corte Masculino")], [P("Aline Ferreira")])

        s.flush()

        # --------------- PAGAMENTOS ---------------
        print("Registrando pagamentos (receitas + baixa de estoque)...")
        for rotulo, (ag, data_pag, serv_desc, vendas) in ags.items():
            pagar(s, ag, data_pag, serv_desc=serv_desc, vendas=vendas)

        # --------------- DESPESAS ---------------
        print("Registrando despesas do mês...")
        despesa(s, "Aluguel", 2500.0, HOJE - timedelta(days=23), "Aluguel do salão")
        despesa(s, "Salários", 4800.0, HOJE - timedelta(days=19), "Folha das profissionais")
        despesa(s, "Insumos", 680.0, HOJE - timedelta(days=16), "Compra de produtos químicos")
        despesa(s, "Insumos", 320.0, HOJE - timedelta(days=9), "Reposição de esmaltes")
        despesa(s, "Marketing", 400.0, HOJE - timedelta(days=12), "Impulsionamento Instagram")
        despesa(s, "Outros", 150.0, HOJE - timedelta(days=5), "Material de limpeza")
        despesa(s, "Outros", 90.0, HOJE - timedelta(days=2), "Cafézinho / copos")

        s.commit()

        # --------------- RESUMO ---------------
        from sqlmodel import func
        def cnt(M):
            return s.exec(select(func.count()).select_from(M)).one()
        receitas = s.exec(select(func.coalesce(func.sum(LancamentoFinanceiro.valor), 0.0))
                          .where(LancamentoFinanceiro.tipo == "receita")).one()
        despesas = s.exec(select(func.coalesce(func.sum(LancamentoFinanceiro.valor), 0.0))
                          .where(LancamentoFinanceiro.tipo == "despesa")).one()
        print("\n=== SEED CONCLUÍDO ===")
        print(f"Clientes:       {cnt(Cliente)} (2 inativos)")
        print(f"Profissionais:  {cnt(Profissional)}")
        print(f"Serviços:       {cnt(Servico)} (1 inativo)")
        print(f"Produtos:       {cnt(Produto)} (1 inativo, 1 sem estoque, 2 abaixo do mínimo)")
        print(f"Agendamentos:   {cnt(Agendamento)}")
        print(f"Lançamentos:    {cnt(LancamentoFinanceiro)}  | Movimentações: {cnt(MovimentacaoEstoque)}")
        print(f"Receitas R$ {receitas:,.2f} · Despesas R$ {despesas:,.2f} · Saldo R$ {receitas - despesas:,.2f}")


if __name__ == "__main__":
    main()
