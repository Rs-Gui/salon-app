from datetime import datetime

from sqlmodel import Field, SQLModel


class Cliente(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    telefone: str | None = None
    email: str | None = None
    observacoes: str | None = None
    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.now)
