"""
Baixa as bibliotecas frontend usadas pelo SalaoApp (Tailwind, HTMX, Alpine,
SortableJS) e salva em `app/static/vendor/`. Após rodar este script uma vez,
o app funciona offline (sem CDN).

Uso:
    python scripts/baixar_vendors.py

Pode ser rodado quantas vezes quiser — apenas re-baixa e sobrescreve.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

# Raiz do projeto: dois níveis acima deste arquivo (scripts/ -> raiz).
RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "app" / "static" / "vendor"

# Pares (URL, nome do arquivo local). As URLs apontam para versões fixas para
# garantir reprodutibilidade entre builds.
VENDORS = [
    ("https://cdn.tailwindcss.com", "tailwind.js"),
    ("https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js", "htmx.min.js"),
    ("https://unpkg.com/alpinejs@3.13.10/dist/cdn.min.js", "alpine.min.js"),
    ("https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js", "sortable.min.js"),
]


def baixar(url: str, destino: Path) -> None:
    """Baixa `url` e grava em `destino` (modo binário)."""
    print(f"Baixando {url} -> {destino.name} ...", flush=True)
    # User-Agent custom evita 403 em alguns CDNs que bloqueiam clients padrão do urllib.
    req = urllib.request.Request(url, headers={"User-Agent": "salao-app-vendor-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        conteudo = resp.read()
    destino.write_bytes(conteudo)
    print(f"  OK ({len(conteudo):,} bytes)", flush=True)


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    erros = 0
    for url, nome in VENDORS:
        destino = DESTINO / nome
        try:
            baixar(url, destino)
        except Exception as e:  # noqa: BLE001 - script utilitário, logamos tudo
            print(f"  ERRO ao baixar {url}: {e}", file=sys.stderr)
            erros += 1
    if erros:
        print(f"\nConcluído com {erros} erro(s).", file=sys.stderr)
        return 1
    print("\nTodos os vendors baixados com sucesso em:", DESTINO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
