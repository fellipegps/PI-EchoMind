"""Production checks with diagnostics restricted to variable names, never values."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit


class ProductionConfigurationError(RuntimeError):
    pass


def _https_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https" and parsed.hostname and parsed.port != 0
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            and not parsed.username and not parsed.password
            and not parsed.path and not parsed.query and not parsed.fragment
            and not any(char in value for char in "*\\?#")
            and not any(char.isspace() for char in value)
        )
    except ValueError:
        return False


def validate_production(environment: Mapping[str, str]) -> None:
    """Check structure only; does not connect to services or authenticate keys."""
    invalid: set[str] = set()
    required = ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "GROQ_API_KEY", "ALLOWED_ORIGINS")
    for name in required:
        value = environment.get(name, "")
        if (not value.strip() or any(marker in value.upper() for marker in
                ("CHANGE_ME", "SUBSTITUA", "PLACEHOLDER", "{{RESOLVE:", "...", "[SUA_", "[SEU_"))
                or any(char in value for char in "\r\n\0")):
            invalid.add(name)

    try:
        url = urlsplit(environment.get("DATABASE_URL", ""))
        ssl_modes = parse_qs(url.query).get("sslmode", [])
        if not (
            url.scheme in {"postgresql", "postgresql+psycopg2"}
            and url.hostname and url.username and url.password and url.path.strip("/")
            and url.port != 0 and not url.fragment
            and len(ssl_modes) == 1 and ssl_modes[0] in {"require", "verify-ca", "verify-full"}
            and not any(char.isspace() for char in environment.get("DATABASE_URL", ""))
        ):
            invalid.add("DATABASE_URL")
    except ValueError:
        invalid.add("DATABASE_URL")

    if not _https_origin(environment.get("SUPABASE_URL", "")):
        invalid.add("SUPABASE_URL")
    origins = environment.get("ALLOWED_ORIGINS", "").split(",")
    if not all(_https_origin(origin.strip()) for origin in origins):
        invalid.add("ALLOWED_ORIGINS")
    for name, prefix in (("SUPABASE_SECRET_KEY", "sb_secret_"), ("GROQ_API_KEY", "gsk_")):
        value = environment.get(name, "")
        if not value.startswith(prefix) or len(value) <= len(prefix) or any(c.isspace() for c in value):
            invalid.add(name)

    for name in ("RATE_LIMIT_INSTANCE_COUNT", "UVICORN_WORKERS", "WEB_CONCURRENCY"):
        if environment.get(name, "1") != "1":
            invalid.add(name)
    if environment.get("EMBEDDING_DIM", "384") != "384":
        invalid.add("EMBEDDING_DIM")
    for name in ("RERANKER_ENABLED", "RAG_WARMUP_ENABLED", "DOCUMENT_RECOVERY_ENABLED"):
        if environment.get(name, "false" if name == "RERANKER_ENABLED" else "true").lower() not in {
            "true", "false", "1", "0", "yes", "no",
        }:
            invalid.add(name)
    for name in ("RATE_LIMIT_MAX_BUCKETS", "CHAT_RATE_LIMIT_REQUESTS", "CHAT_RATE_LIMIT_WINDOW_SECONDS",
                 "UPLOAD_RATE_LIMIT_REQUESTS", "UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "TOP_K_DOCS",
                 "RERANKER_CANDIDATE_LIMIT", "RERANKER_MAX_CHARS", "MAX_DOCUMENT_SIZE_MB"):
        if name in environment:
            try:
                if int(environment[name]) <= 0:
                    invalid.add(name)
            except ValueError:
                invalid.add(name)
    for name in ("SIMILARITY_THRESHOLD", "UNCERTAIN_DISTANCE_THRESHOLD", "RERANKER_TIMEOUT_SECONDS", "RAG_WARMUP_TIMEOUT_SECONDS"):
        if name in environment:
            try:
                number = float(environment[name])
                if not math.isfinite(number) or number <= 0:
                    invalid.add(name)
            except ValueError:
                invalid.add(name)
    if invalid:
        raise ProductionConfigurationError(
            "Configuração de produção inválida. Revise: " + ", ".join(sorted(invalid)) + "."
        ) from None


def load_runtime_environment() -> None:
    # Development retains dotenv support. Production receives only runtime env.
    mode = os.environ.get("ECHOMIND_ENV", "development")
    if mode not in {"development", "testing", "production"}:
        raise ProductionConfigurationError("ECHOMIND_ENV inválido.")
    if mode == "development":
        from dotenv import load_dotenv
        load_dotenv()
    if os.environ.get("ECHOMIND_ENV") == "production":
        validate_production(os.environ)
