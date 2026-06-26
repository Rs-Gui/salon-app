from datetime import datetime

from sqlmodel import Field, SQLModel


class Servico(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    preco: float = Field(default=0.0)
    duracao_minutos: int = Field(default=30)
    ativo: bool = Field(default=True)
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
