from datetime import datetime

from sqlmodel import Field, SQLModel


class MovimentacaoEstoque(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produto.id", index=True)
    tipo: str = Field(index=True)  # "entrada" | "saida_uso" | "saida_venda"
    quantidade: int
    # Vínculo opcional: vendas (saida_venda) geradas no pagamento de um agendamento.
    agendamento_id: int | None = Field(
        default=None, foreign_key="agendamento.id", index=True
    )
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
