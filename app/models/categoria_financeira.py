from datetime import datetime

from sqlmodel import Field, SQLModel


class CategoriaFinanceira(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    tipo: str = Field(index=True)  # "receita" | "despesa"
    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.now)
