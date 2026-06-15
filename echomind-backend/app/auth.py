"""
auth.py - Autenticacao do painel administrativo via Supabase Auth.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .supabase_client import supabase

bearer_scheme = HTTPBearer()


@dataclass
class CurrentUser:
    id: str
    email: str
    is_active: bool
    created_at: datetime | str
    full_name: str | None = None
    company_name: str | None = None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
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
        response = supabase.auth.get_user(credentials.credentials)
        user = response.user
    except Exception:
        raise credentials_exception

    if not user or not user.email:
        raise credentials_exception

    metadata = (
        getattr(user, "user_metadata", None)
        or getattr(user, "raw_user_meta_data", None)
        or {}
    )
    created_at = getattr(user, "created_at", None) or datetime.now(timezone.utc)
    return CurrentUser(
        id=str(getattr(user, "id", "")),
        email=user.email,
        is_active=True,
        created_at=created_at,
        full_name=metadata.get("full_name") if isinstance(metadata, dict) else None,
        company_name=metadata.get("company_name") if isinstance(metadata, dict) else None,
    )
