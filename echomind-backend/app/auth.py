"""
auth.py – Autenticação JWT para o painel administrativo do EchoMind.

Fluxo:
  1. POST /auth/login recebe {username (email), password} via OAuth2PasswordRequestForm.
  2. Valida o hash bcrypt contra o banco (tabela admin_users).
  3. Retorna um JWT assinado com HS256 (válido por JWT_EXPIRE_HOURS horas).
  4. O frontend armazena o token e o envia como Bearer em cada requisição protegida.
  5. get_current_user é um Depends() que valida o token e retorna o usuário — usado
     nas rotas do dashboard para garantir acesso somente autenticado.
"""

import os
import logging
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import AdminUser, get_db

logger = logging.getLogger("echomind.auth")

# ─── Configuração ─────────────────────────────────────────────────────────────

JWT_SECRET       = os.getenv("JWT_SECRET", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32")
JWT_ALGORITHM    = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ══════════════════════════════════════════════════════════════════════════════
#  HASHING
#  Usa bcrypt diretamente (sem passlib) para evitar incompatibilidade com
#  bcrypt >= 4.x, que removeu o atributo __about__ que o passlib esperava.
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(plain: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compara senha em texto puro com o hash bcrypt armazenado."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  JWT
# ══════════════════════════════════════════════════════════════════════════════

def create_access_token(subject: str) -> str:
    """
    Cria um JWT assinado com HS256.
    `subject` é o email do usuário — identifica quem é o titular do token.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": subject,           # subject: email do usuário
        "exp": expire,            # expiration time
        "iat": datetime.now(timezone.utc),  # issued at
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> Optional[str]:
    """
    Decodifica e valida o JWT.
    Retorna o email (sub) se válido, None se expirado ou adulterado.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  CRUD de usuário
# ══════════════════════════════════════════════════════════════════════════════

def get_user_by_email(db: Session, email: str) -> Optional[AdminUser]:
    return db.query(AdminUser).filter(AdminUser.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[AdminUser]:
    """
    Valida credenciais:
      1. Busca o usuário pelo email.
      2. Verifica o hash bcrypt da senha.
      3. Verifica se a conta está ativa.
    Retorna o usuário em caso de sucesso, None caso contrário.
    """
    user = get_user_by_email(db, email)
    if not user:
        # Executa verify_password mesmo assim para evitar timing attacks
        verify_password("dummy", hash_password("dummy"))
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY — protege rotas do dashboard
# ══════════════════════════════════════════════════════════════════════════════

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    Dependência FastAPI para rotas protegidas.
    Extrai o Bearer token do header Authorization, valida o JWT e
    retorna o AdminUser correspondente.

    Uso nas rotas:
        @router_unanswered.delete("/{id}")
        def delete_unanswered(id: str, _: AdminUser = Depends(get_current_user)):
            ...
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou sessão expirada. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = _decode_token(token)
    if not email:
        raise credentials_exception

    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        raise credentials_exception

    return user
