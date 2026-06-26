from datetime import datetime

from sqlmodel import Field, SQLModel


class Produto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    preco_venda: float = Field(default=0.0)
    custo: float = Field(default=0.0)
    estoque_atual: int = Field(default=0)
    estoque_minimo: int = Field(default=0)
    unidade: str = Field(default="un")
    ativo: bool = Field(default=True)
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
