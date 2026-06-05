"""
auth.py - Autenticacao do painel administrativo via Supabase Auth.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .supabase_client import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class CurrentUser:
    id: str
    email: str
    is_active: bool
    created_at: datetime | str


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Valida o Bearer token emitido pelo Supabase Auth e retorna dados publicos
    suficientes para manter compatibilidade com as rotas protegidas existentes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais invalidas ou sessao expirada. Faca login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        response = supabase.auth.get_user(token)
        user = response.user
    except Exception:
        raise credentials_exception

    if not user or not user.email:
        raise credentials_exception

    created_at = getattr(user, "created_at", None) or datetime.now(timezone.utc)
    return CurrentUser(
        id=str(getattr(user, "id", "")),
        email=user.email,
        is_active=True,
        created_at=created_at,
    )
