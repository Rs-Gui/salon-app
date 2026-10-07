from datetime import date, datetime

from sqlmodel import Field, SQLModel


class LancamentoFinanceiro(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tipo: str = Field(index=True)  # "receita" | "despesa"
    valor: float = Field(default=0.0)  # valor LÍQUIDO (já com desconto aplicado)
    # Desconto por item (receitas de agendamento). valor_bruto None = lançamento
    # antigo/avulso sem desconto → tratar bruto = valor, desconto = 0.
    valor_bruto: float | None = None
    desconto_valor: float = Field(default=0.0)
    desconto_tipo: str | None = None  # "brl" | "pct" | None (quando sem desconto)
    data: date = Field(index=True)
    categoria_id: int | None = Field(
        default=None, foreign_key="categoriafinanceira.id", index=True
    )
    # Snapshot do nome da categoria, preenchido quando a categoria é removida.
    # Mantém a classificação visível no histórico mesmo sem o vínculo vivo.
    categoria_nome: str | None = None
    descricao: str | None = None
    # Quando a receita nasce do pagamento de um agendamento, guarda o vínculo.
    # "Pago" = existe um lançamento de receita com este agendamento_id.
    agendamento_id: int | None = Field(
        default=None, foreign_key="agendamento.id", index=True
    )
    # Autoria: quem fechou a comanda / lançou a despesa/receita avulsa.
    # usuario_nome é snapshot (sobrevive a rename/exclusão do usuário, como
    # categoria_nome). Registra o CRIADOR; edição não sobrescreve.
    usuario_id: int | None = Field(
        default=None, foreign_key="usuario.id", index=True
    )
    usuario_nome: str | None = None
    # % de comissão do serviço no momento do pagamento (snapshot). None em
    # lançamentos antigos/produtos/avulsos.
    comissao_pct: float | None = None
    observacoes: str | None = None
    criado_em: datetime = Field(default_factory=datetime.now)
