from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

class _Templates(Jinja2Templates):
    """Aceita a assinatura antiga TemplateResponse(name, {"request": ...}),
    removida no Starlette 1.x, usada em todos os routers."""

    def TemplateResponse(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name, *resto = args
            context = resto[0] if resto else kwargs.pop("context", {})
            return super().TemplateResponse(
                context["request"], name, context, *resto[1:], **kwargs
            )
        return super().TemplateResponse(*args, **kwargs)


templates = _Templates(directory=str(TEMPLATES_DIR))


def asset_version(nome: str) -> str:
    """Versão do arquivo estático (mtime) p/ cache-busting do <link>/<script>.

    Recalculado a cada render, então editar o CSS já invalida o cache do
    navegador sem precisar reiniciar/limpar cache manualmente.
    """
    try:
        return str(int((STATIC_DIR / nome).stat().st_mtime))
    except OSError:
        return "1"


# Disponível em todos os templates: href="/static/bruma.css?v={{ asset_version('bruma.css') }}"
templates.env.globals["asset_version"] = asset_version


def brl(valor) -> str:
    """Formata um número como moeda BR: 1234.5 → '1.234,50' (sem o 'R$')."""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


templates.env.filters["brl"] = brl
