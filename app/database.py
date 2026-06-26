from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "salao.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # Importa todos os módulos de models para registrar tabelas em SQLModel.metadata.
    from app.models import agendamento  # noqa: F401
    from app.models import categoria_financeira  # noqa: F401
    from app.models import cliente  # noqa: F401
    from app.models import lancamento_financeiro  # noqa: F401
    from app.models import movimentacao_estoque  # noqa: F401
    from app.models import produto  # noqa: F401
    from app.models import profissional  # noqa: F401
    from app.models import servico  # noqa: F401
    from app.models import usuario  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrar_schema()
    _seed_categorias_financeiras()


def _migrar_schema() -> None:
    """Migrações idempotentes manuais via ALTER TABLE.

    Padrão: consultar PRAGMA table_info(<tabela>); se a coluna faltar, ALTER TABLE.
    Tolerante a tabelas que ainda não existem (modules não importados/criados).
    """
    with engine.connect() as conn:
        # Exemplo: cliente.ativo BOOLEAN NOT NULL DEFAULT 1
        try:
            cols = _colunas(conn, "cliente")
            if cols and "ativo" not in cols:
                conn.execute(
                    text("ALTER TABLE cliente ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT 1")
                )
                conn.commit()
        except Exception:
            # tabela ainda não existe ou outro erro benigno — ignora
            pass

        # agendamentoprofissional.nome_snapshot TEXT (preenchido em hard-delete de profissional)
        try:
            cols = _colunas(conn, "agendamentoprofissional")
            if cols and "nome_snapshot" not in cols:
                conn.execute(
                    text("ALTER TABLE agendamentoprofissional ADD COLUMN nome_snapshot TEXT")
                )
                conn.commit()
        except Exception:
            pass

        # usuario: multiusuário (nome_usuario, papel, ativo).
        # O usuário mais antigo (menor id) é promovido a admin com nome 'admin'.
        try:
            cols = _colunas(conn, "usuario")
            if cols:
                if "nome_usuario" not in cols:
                    conn.execute(text("ALTER TABLE usuario ADD COLUMN nome_usuario TEXT"))
                    conn.commit()
                if "papel" not in cols:
                    conn.execute(
                        text("ALTER TABLE usuario ADD COLUMN papel TEXT NOT NULL DEFAULT 'comum'")
                    )
                    conn.commit()
                if "ativo" not in cols:
                    conn.execute(
                        text("ALTER TABLE usuario ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT 1")
                    )
                    conn.commit()
                if "nome_exibicao" not in cols:
                    conn.execute(text("ALTER TABLE usuario ADD COLUMN nome_exibicao TEXT"))
                    conn.commit()

                # Backfill: a conta pré-existente vira o admin principal.
                primeiro = conn.execute(
                    text("SELECT id FROM usuario ORDER BY id LIMIT 1")
                ).first()
                if primeiro is not None:
                    conn.execute(
                        text(
                            "UPDATE usuario SET nome_usuario = 'admin', papel = 'admin' "
                            "WHERE id = :id AND (nome_usuario IS NULL OR nome_usuario = '')"
                        ),
                        {"id": primeiro[0]},
                    )
                    conn.commit()
        except Exception:
            pass

        # movimentacaoestoque.agendamento_id INTEGER (vendas geradas no pagamento
        # de um agendamento; permite estornar a venda ao excluir o pagamento).
        try:
            cols = _colunas(conn, "movimentacaoestoque")
            if cols and "agendamento_id" not in cols:
                conn.execute(
                    text("ALTER TABLE movimentacaoestoque ADD COLUMN agendamento_id INTEGER")
                )
                conn.commit()
        except Exception:
            pass

        # lancamentofinanceiro.categoria_nome TEXT (snapshot preenchido ao remover
        # a categoria, para o histórico não perder a classificação).
        try:
            cols = _colunas(conn, "lancamentofinanceiro")
            if cols and "categoria_nome" not in cols:
                conn.execute(
                    text("ALTER TABLE lancamentofinanceiro ADD COLUMN categoria_nome TEXT")
                )
                conn.commit()
        except Exception:
            pass

        # lancamentofinanceiro: desconto por item (receitas de agendamento).
        # valor_bruto (preço cheio antes do desconto), desconto_valor (R$ abatido)
        # e desconto_tipo ("brl"|"pct"). Mantém o desconto rastreável na comanda.
        try:
            cols = _colunas(conn, "lancamentofinanceiro")
            if cols:
                if "valor_bruto" not in cols:
                    conn.execute(
                        text("ALTER TABLE lancamentofinanceiro ADD COLUMN valor_bruto REAL")
                    )
                    conn.commit()
                if "desconto_valor" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE lancamentofinanceiro ADD COLUMN "
                            "desconto_valor REAL NOT NULL DEFAULT 0"
                        )
                    )
                    conn.commit()
                if "desconto_tipo" not in cols:
                    conn.execute(
                        text("ALTER TABLE lancamentofinanceiro ADD COLUMN desconto_tipo TEXT")
                    )
                    conn.commit()
        except Exception:
            pass

        # lancamentofinanceiro: autoria (quem fechou a comanda / lançou avulso).
        # usuario_id (FK usuario) + usuario_nome (snapshot do nome). Linhas
        # antigas ficam NULL → exibidas como "—".
        try:
            cols = _colunas(conn, "lancamentofinanceiro")
            if cols:
                if "usuario_id" not in cols:
                    conn.execute(
                        text("ALTER TABLE lancamentofinanceiro ADD COLUMN usuario_id INTEGER")
                    )
                    conn.commit()
                if "usuario_nome" not in cols:
                    conn.execute(
                        text("ALTER TABLE lancamentofinanceiro ADD COLUMN usuario_nome TEXT")
                    )
                    conn.commit()
        except Exception:
            pass


# Categorias padrão criadas no primeiro boot. Idempotente: só insere o que faltar
# (por nome+tipo), preservando o que o usuário tiver criado/renomeado depois.
_CATEGORIAS_PADRAO = {
    "receita": ("Serviços", "Produtos", "Outros"),
    "despesa": ("Aluguel", "Salários", "Insumos", "Marketing", "Outros"),
}


def _seed_categorias_financeiras() -> None:
    from app.models.categoria_financeira import CategoriaFinanceira

    try:
        with Session(engine) as session:
            existentes = {
                (c.tipo, (c.nome or "").strip().lower())
                for c in session.exec(_select_categorias()).all()
            }
            novas = []
            for tipo, nomes in _CATEGORIAS_PADRAO.items():
                for nome in nomes:
                    if (tipo, nome.lower()) not in existentes:
                        novas.append(
                            CategoriaFinanceira(nome=nome, tipo=tipo, ativo=True)
                        )
            if novas:
                session.add_all(novas)
                session.commit()
    except Exception:
        # tabela ainda não criada ou erro benigno — ignora (próximo boot tenta de novo)
        pass


def _select_categorias():
    from sqlmodel import select

    from app.models.categoria_financeira import CategoriaFinanceira

    return select(CategoriaFinanceira)


_TABELAS_PERMITIDAS = {
    "cliente",
    "profissional",
    "servico",
    "agendamento",
    "usuario",
    "agendamentoservico",
    "agendamentoprofissional",
    "produto",
    "movimentacaoestoque",
    "categoriafinanceira",
    "lancamentofinanceiro",
}


def _colunas(conn, tabela: str) -> set[str]:
    if tabela not in _TABELAS_PERMITIDAS:
        return set()
    try:
        result = conn.execute(text(f"PRAGMA table_info({tabela})"))
        return {row[1] for row in result}
    except Exception:
        return set()


def get_session():
    with Session(engine) as session:
        yield session
