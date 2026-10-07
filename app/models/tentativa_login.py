from datetime import datetime

from sqlmodel import Field, SQLModel


class TentativaLogin(SQLModel, table=True):
    """Login que falhou. Usado para limitar tentativas (força bruta)."""

    id: int | None = Field(default=None, primary_key=True)
    nome_usuario: str = Field(index=True)
    ip: str = Field(index=True)
    criado_em: datetime = Field(default_factory=datetime.now, index=True)
