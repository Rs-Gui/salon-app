import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from passlib.context import CryptContext
from sqlmodel import Session, func, select

from app.database import get_session
from app.models.tentativa_login import TentativaLogin
from app.models.usuario import Usuario

ROOT_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY_FILE = ROOT_DIR / ".secret_key"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _carregar_secret_key() -> str:
    env_key = os.environ.get("SALAO_SECRET_KEY")
    if env_key:
        return env_key
    # Na Vercel não há disco gravável: deriva a chave da URL do banco (segredo
    # injetado pela integração do Neon, fora do repositório).
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if db_url:
        return hashlib.sha256(b"salao-session-key:" + db_url.encode()).hexdigest()
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
    chave = secrets.token_urlsafe(64)
    try:
        SECRET_KEY_FILE.write_text(chave, encoding="utf-8")
        try:
            os.chmod(SECRET_KEY_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return chave


SECRET_KEY = _carregar_secret_key()

# Em produção (Vercel) o cookie de sessão só trafega por HTTPS.
EM_PRODUCAO = bool(os.environ.get("VERCEL"))

SESSAO_HORAS = 24

# Limite de logins errados por janela (por nome de usuário e por IP).
LOGIN_JANELA_MIN = 15
LOGIN_MAX_FALHAS_USUARIO = 5
LOGIN_MAX_FALHAS_IP = 20

# Quando definido, /setup só abre com ?token=<valor>. Evita que um estranho crie
# o admin antes da dona num deploy público.
SETUP_TOKEN = os.environ.get("SALAO_SETUP_TOKEN") or None


def impressao_senha(senha_hash: str) -> str:
    """Guardada na sessão no login: trocar a senha derruba as sessões abertas."""
    return hashlib.sha256(("salao-senha:" + senha_hash).encode()).hexdigest()[:16]


def setup_token_valido(token: str | None) -> bool:
    if SETUP_TOKEN is None:
        # Local: setup livre. Em produção sem token configurado: fechado.
        return not EM_PRODUCAO
    return secrets.compare_digest((token or "").encode(), SETUP_TOKEN.encode())


def ip_do_cliente(request: Request) -> str:
    # Na Vercel o IP real vem no x-forwarded-for (definido pela própria plataforma).
    encaminhado = request.headers.get("x-forwarded-for", "")
    if EM_PRODUCAO and encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "?"


def login_bloqueado(session: Session, nome_usuario: str, ip: str) -> bool:
    desde = datetime.now() - timedelta(minutes=LOGIN_JANELA_MIN)
    falhas_usuario = session.exec(
        select(func.count()).select_from(TentativaLogin)
        .where(TentativaLogin.nome_usuario == nome_usuario)
        .where(TentativaLogin.criado_em >= desde)
    ).one()
    if falhas_usuario >= LOGIN_MAX_FALHAS_USUARIO:
        return True
    falhas_ip = session.exec(
        select(func.count()).select_from(TentativaLogin)
        .where(TentativaLogin.ip == ip)
        .where(TentativaLogin.criado_em >= desde)
    ).one()
    return falhas_ip >= LOGIN_MAX_FALHAS_IP


def registrar_falha_login(session: Session, nome_usuario: str, ip: str) -> None:
    # Limpa registros antigos para a tabela não crescer.
    antigos = datetime.now() - timedelta(days=1)
    for t in session.exec(select(TentativaLogin).where(TentativaLogin.criado_em < antigos)).all():
        session.delete(t)
    session.add(TentativaLogin(nome_usuario=nome_usuario[:60], ip=ip[:60]))
    session.commit()


def hash_senha(senha: str) -> str:
    return _pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return _pwd_context.verify(senha, senha_hash)
    except Exception:
        return False


def normalizar_nome_usuario(nome: str) -> str:
    return (nome or "").strip().lower()


def existe_algum_usuario(session: Session) -> bool:
    return session.exec(select(Usuario.id).limit(1)).first() is not None


def obter_usuario_por_id(session: Session, usuario_id: int) -> Usuario | None:
    return session.get(Usuario, usuario_id)


def obter_usuario_por_nome(session: Session, nome: str) -> Usuario | None:
    nome = normalizar_nome_usuario(nome)
    if not nome:
        return None
    return session.exec(
        select(Usuario).where(Usuario.nome_usuario == nome)
    ).first()


# ---------- Papéis e regras de permissão ----------

SUPERADMIN = "superadmin"
ADMIN = "admin"
COMUM = "comum"

# Papéis que podem ser atribuídos pela interface. "superadmin" NUNCA é atribuível:
# existe apenas na conta criada na origem e jamais pode ser concedido a ninguém.
PAPEIS_ATRIBUIVEIS = (COMUM, ADMIN)


def pode_gerenciar_usuarios(ator: Usuario) -> bool:
    """Quem pode abrir a tela de Usuários: admin ou superadmin."""
    return ator.papel in (ADMIN, SUPERADMIN)


def pode_alterar_papel(ator: Usuario) -> bool:
    """Somente o superadmin promove/rebaixa (concede ou retira 'admin')."""
    return ator.papel == SUPERADMIN


def pode_criar_com_papel(ator: Usuario, papel: str) -> bool:
    if papel not in PAPEIS_ATRIBUIVEIS:
        return False
    if papel == ADMIN:
        return ator.papel == SUPERADMIN
    return pode_gerenciar_usuarios(ator)


def pode_gerenciar_alvo(ator: Usuario, alvo: Usuario) -> tuple[bool, str | None]:
    """Regra para ações de acesso (ativar/desativar) sobre uma conta-alvo."""
    if alvo.papel == SUPERADMIN:
        return False, "O super admin não pode ser desativado."
    if ator.id == alvo.id:
        return False, "Você não pode desativar a própria conta."
    if alvo.papel == ADMIN and ator.papel != SUPERADMIN:
        return False, "Apenas o super admin pode desativar administradores."
    if alvo.papel == COMUM and not pode_gerenciar_usuarios(ator):
        return False, "Sem permissão."
    return True, None


def pode_redefinir_senha(ator: Usuario, alvo: Usuario) -> tuple[bool, str | None]:
    if ator.id == alvo.id:
        return True, None  # qualquer um redefine a própria senha
    return pode_gerenciar_alvo(ator, alvo)


def _eh_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


class RedirectRequired(HTTPException):
    """Exceção usada por dependencies para forçar redirect/HX-Redirect."""

    def __init__(self, url: str, *, htmx: bool):
        self.url = url
        self.htmx = htmx
        if htmx:
            super().__init__(status_code=401, headers={"HX-Redirect": url})
        else:
            super().__init__(status_code=303, headers={"Location": url})


def montar_resposta_redirect(exc: RedirectRequired) -> Response:
    if exc.htmx:
        return Response(status_code=401, headers={"HX-Redirect": exc.url})
    return RedirectResponse(url=exc.url, status_code=303)


def usuario_atual(
    request: Request,
    session: Session = Depends(get_session),
) -> Usuario:
    """Resolve o usuário logado a partir da sessão, validando que ainda existe
    e está ativo. Redireciona para /setup (sem usuários) ou /login caso contrário."""
    htmx = _eh_htmx(request)
    if not existe_algum_usuario(session):
        raise RedirectRequired("/setup", htmx=htmx)

    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        raise RedirectRequired("/login", htmx=htmx)

    # O cookie assinado não expira sozinho; o login vale SESSAO_HORAS.
    login_em = request.session.get("login_em")
    if not isinstance(login_em, (int, float)) or time.time() - login_em > SESSAO_HORAS * 3600:
        request.session.clear()
        raise RedirectRequired("/login", htmx=htmx)

    usuario = obter_usuario_por_id(session, usuario_id)
    if (
        usuario is None
        or not usuario.ativo
        or request.session.get("senha_fp") != impressao_senha(usuario.senha_hash)
    ):
        request.session.clear()
        raise RedirectRequired("/login", htmx=htmx)
    return usuario


def requer_login(
    usuario: Usuario = Depends(usuario_atual),
) -> Usuario:
    return usuario


def requer_admin(
    request: Request,
    usuario: Usuario = Depends(usuario_atual),
) -> Usuario:
    if not pode_gerenciar_usuarios(usuario):
        htmx = _eh_htmx(request)
        # Sem permissão: manda de volta para a home em vez de expor a tela.
        raise RedirectRequired("/", htmx=htmx)
    return usuario
