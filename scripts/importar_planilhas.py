"""Importa as planilhas exportadas do sistema antigo (Clientes, Profissionais,
Serviços, Produtos .xlsx) para o banco do app.

Por padrão só SIMULA (mostra o que faria). Para gravar, passe --aplicar.
Re-executável: registros cujo nome já existe no banco são pulados.

Banco de destino: o mesmo do app — SQLite local (salao.db) ou, se definido,
DATABASE_URL (variável de ambiente ou arquivo .env na raiz, fora do git).

Regras de limpeza:
- pula as linhas "... Exemplo" das planilhas e o serviço "FECHADO";
- duplicados idênticos entram uma vez; produtos com mesmo nome e preço
  diferente entram como "NOME (2)";
- clientes: nomes em MAIÚSCULAS viram "Nome Sobrenome"; nomes repetidos
  (sem diferenciar maiúsculas) viram um só, mantendo o telefone;
- telefones: só dígitos, sem o 55 do país; "-" = sem telefone;
- categoria do produto vai para as observações (o app não tem esse campo);
  produtos entram com estoque 0.

Requer openpyxl (só para este script):  pip install openpyxl

Uso:
    python scripts/importar_planilhas.py [PASTA]            # simula
    python scripts/importar_planilhas.py [PASTA] --aplicar  # grava
PASTA padrão: ~/Downloads
"""
import os
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _carregar_env() -> None:
    """Lê KEY=VALUE de .env (se existir) antes de importar o app."""
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_env()

import openpyxl  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.database import DATABASE_URL, engine, init_db  # noqa: E402
from app.models.cliente import Cliente  # noqa: E402
from app.models.produto import Produto  # noqa: E402
from app.models.profissional import Profissional  # noqa: E402
from app.models.servico import Servico  # noqa: E402

_MINUSCULAS = {"da", "de", "do", "das", "dos", "e"}


def _linhas(pasta: pathlib.Path, nome: str) -> list[tuple]:
    """Linhas de dados da 1ª aba (pula título e cabeçalho, ignora vazias)."""
    ws = openpyxl.load_workbook(pasta / f"{nome}.xlsx", data_only=True).worksheets[0]
    linhas = [
        tuple(r[:4])
        for r in ws.iter_rows(values_only=True)
        if any(c not in (None, "") for c in r)
    ]
    return [r for r in linhas[2:] if "exemplo" not in str(r[0]).lower()]


def _texto(valor) -> str:
    return re.sub(r"\s+", " ", str(valor if valor is not None else "")).strip()


def _nome_pessoa(valor) -> str:
    nome = _texto(valor)
    if not nome.isupper():
        return nome
    palavras = nome.lower().split(" ")
    return " ".join(
        p if (i > 0 and p in _MINUSCULAS) else p[:1].upper() + p[1:]
        for i, p in enumerate(palavras)
    )


def _capitalizadas(nome: str) -> int:
    return sum(1 for p in nome.split(" ") if p[:1].isupper())


def _telefone(valor) -> str | None:
    digitos = re.sub(r"\D", "", _texto(valor))
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    return digitos if 8 <= len(digitos) <= 15 else None


def _numero(valor) -> float:
    try:
        return float(str(valor).replace("%", "").replace(",", ".").strip())
    except ValueError:
        return 0.0


def _existentes(session: Session, modelo) -> set[str]:
    return {(x.nome or "").strip().lower() for x in session.exec(select(modelo)).all()}


def clientes(pasta, session) -> tuple[list, int]:
    por_nome: dict[str, dict] = {}
    for nome_raw, tel_raw, *_ in _linhas(pasta, "Clientes"):
        nome = _nome_pessoa(nome_raw)
        if not nome:
            continue
        tel = _telefone(tel_raw)
        atual = por_nome.get(nome.lower())
        if atual is None:
            por_nome[nome.lower()] = {"nome": nome, "telefone": tel}
            continue
        if atual["telefone"] is None and tel:
            atual["telefone"] = tel
        # Entre grafias do mesmo nome, fica a com mais palavras capitalizadas.
        if _capitalizadas(nome) > _capitalizadas(atual["nome"]):
            atual["nome"] = nome
    ja = _existentes(session, Cliente)
    novos = [Cliente(**d) for k, d in por_nome.items() if k not in ja]
    return novos, len(por_nome) - len(novos)


def profissionais(pasta, session) -> tuple[list, int]:
    ja = _existentes(session, Profissional)
    novos, vistos = [], set()
    for nome_raw, tel_raw, *_ in _linhas(pasta, "Profissionais"):
        nome = _nome_pessoa(nome_raw)
        if not nome or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        if nome.lower() not in ja:
            novos.append(Profissional(nome=nome, telefone=_telefone(tel_raw)))
    return novos, len(vistos) - len(novos)


def servicos(pasta, session) -> tuple[list, int]:
    ja = _existentes(session, Servico)
    novos, vistos = [], set()
    for nome_raw, preco, duracao, comissao in _linhas(pasta, "Serviços"):
        nome = _texto(nome_raw)
        if not nome or nome.upper() == "FECHADO" or nome.lower() in vistos:
            continue
        vistos.add(nome.lower())
        if nome.lower() not in ja:
            novos.append(
                Servico(
                    nome=nome,
                    preco=round(_numero(preco), 2),
                    duracao_minutos=int(_numero(duracao)) or 30,
                    comissao_pct=_numero(comissao),
                )
            )
    return novos, len(vistos) - len(novos)


def produtos(pasta, session) -> tuple[list, int]:
    ja = _existentes(session, Produto)
    novos, vistos, pulados = [], {}, 0
    for nome_raw, categoria, preco, *_ in _linhas(pasta, "Produtos"):
        nome = _texto(nome_raw)
        if not nome:
            continue
        preco = round(_numero(preco), 2)
        chave = nome.lower()
        if chave in vistos:
            if preco in vistos[chave]:
                continue  # duplicado idêntico
            vistos[chave].append(preco)
            nome = f"{nome} ({len(vistos[chave])})"
        else:
            vistos[chave] = [preco]
        if nome.lower() in ja:
            pulados += 1
            continue
        cat = _texto(categoria)
        novos.append(
            Produto(
                nome=nome,
                preco_venda=preco,
                observacoes=f"Categoria: {cat}" if cat and cat != "-" else None,
            )
        )
    return novos, pulados


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    aplicar = "--aplicar" in sys.argv
    pasta = pathlib.Path(args[0]) if args else pathlib.Path.home() / "Downloads"

    destino = "SQLite local" if DATABASE_URL.startswith("sqlite") else "Postgres (DATABASE_URL)"
    print(f"Planilhas: {pasta}\nBanco:     {destino}\n")

    init_db()
    with Session(engine) as session:
        total = 0
        for rotulo, func in (
            ("Clientes", clientes),
            ("Profissionais", profissionais),
            ("Serviços", servicos),
            ("Produtos", produtos),
        ):
            novos, pulados = func(pasta, session)
            total += len(novos)
            extra = f" ({pulados} já existiam)" if pulados else ""
            print(f"{rotulo:<14} {len(novos):>4} novos{extra}")
            session.add_all(novos)

        if aplicar:
            session.commit()
            print(f"\nGravado: {total} registros.")
        else:
            session.rollback()
            print("\nSimulação: nada foi gravado. Rode com --aplicar para gravar.")


if __name__ == "__main__":
    main()
