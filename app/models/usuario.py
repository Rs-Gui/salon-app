from datetime import datetime

from sqlmodel import Field, SQLModel


class Usuario(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nome_usuario: str = Field(index=True, unique=True)
    nome_exibicao: str | None = Field(default=None)
    senha_hash: str
    papel: str = Field(default="comum")  # "superadmin" | "admin" | "comum"
    ativo: bool = Field(default=True)
    criado_em: datetime = Field(default_factory=datetime.now)
    atualizado_em: datetime = Field(default_factory=datetime.now)
