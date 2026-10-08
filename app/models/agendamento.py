from datetime import datetime

from sqlmodel import Field, SQLModel


class Agendamento(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    data_hora: datetime = Field(index=True)
    cliente_id: int | None = Field(default=None, foreign_key="cliente.id", index=True)
    duracao_override: int | None = None
    # Encaixe: sobrepõe outro horário do mesmo profissional de propósito
    # (não bloqueia nem é bloqueado pela checagem de conflito).
    encaixe: bool = Field(default=False)
    # Agendamentos criados juntos por "Repetir" compartilham o mesmo serie_id.
    serie_id: str | None = Field(default=None, index=True)
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)


class AgendamentoServico(SQLModel, table=True):
    agendamento_id: int = Field(foreign_key="agendamento.id", primary_key=True)
    servico_id: int = Field(foreign_key="servico.id", primary_key=True)


class AgendamentoProfissional(SQLModel, table=True):
    agendamento_id: int = Field(foreign_key="agendamento.id", primary_key=True)
    profissional_id: int = Field(foreign_key="profissional.id", primary_key=True)
    nome_snapshot: str | None = None
