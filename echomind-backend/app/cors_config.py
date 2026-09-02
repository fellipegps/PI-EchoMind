"""Configuracao segura e explicita de CORS para a API."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
CORS_ALLOW_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
CORS_ALLOW_HEADERS = ("Authorization", "Content-Type")


class InvalidCORSConfigurationError(ValueError):
    """Indica que ALLOWED_ORIGINS nao representa origens web exatas."""


def _validate_origin(origin: str) -> None:
    if "*" in origin:
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS nao permite wildcard quando credenciais estao ativas."
        )
    if any(character.isspace() for character in origin):
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS contem uma origem invalida."
        )

    try:
        parsed = urlsplit(origin)
        parsed.port
    except ValueError as exc:
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS contem uma origem invalida."
        ) from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS aceita apenas origens HTTP/HTTPS completas."
        )
    if parsed.username is not None or parsed.password is not None:
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS nao permite credenciais embutidas na URL."
        )
    if parsed.path or parsed.query or parsed.fragment:
        raise InvalidCORSConfigurationError(
            "ALLOWED_ORIGINS deve conter somente esquema, host e porta opcional."
        )


def parse_allowed_origins(raw_value: str | None = None) -> tuple[str, ...]:
    """Le e valida uma allowlist separada por virgulas, preservando a ordem."""
    configured_value = (
        os.getenv("ALLOWED_ORIGINS") if raw_value is None else raw_value
    )
    if configured_value is None:
        return DEFAULT_ALLOWED_ORIGINS

    entries = configured_value.split(",")
    origins: list[str] = []
    for entry in entries:
        origin = entry.strip()
        if not origin:
            raise InvalidCORSConfigurationError(
                "ALLOWED_ORIGINS deve conter ao menos uma origem e nao ter itens vazios."
            )
        _validate_origin(origin)
        if origin not in origins:
            origins.append(origin)

    return tuple(origins)


def configure_cors(
    application: FastAPI,
    raw_allowed_origins: str | None = None,
) -> tuple[str, ...]:
    """Registra o middleware com a allowlist validada e privilegios minimos."""
    allowed_origins = parse_allowed_origins(raw_allowed_origins)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=True,
        allow_methods=list(CORS_ALLOW_METHODS),
        allow_headers=list(CORS_ALLOW_HEADERS),
    )
    return allowed_origins
