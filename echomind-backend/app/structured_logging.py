"""Eventos estruturados e seguros para observabilidade local do RAG."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Mapping


SCHEMA_VERSION = 1
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_KNOWN_SOURCE_TYPES = {"faq", "event", "document_chunk", "document_parent"}
_KNOWN_COUNT_FIELDS = {
    "approved_candidates",
    "child_candidates",
    "current_candidates",
    "excluded_results",
    "input_candidates",
    "lexical_candidates",
    "matched_existing",
    "persisted_chunks",
    "persisted_parents",
    "retrieved_results",
    "returned_results",
    "vector_candidates",
}
_logger = logging.getLogger("echomind.observability")


@dataclass(frozen=True, slots=True)
class LogContext:
    correlation_id: str
    tenant_ref: str


_current_context: ContextVar[LogContext | None] = ContextVar(
    "echomind_log_context",
    default=None,
)


def new_correlation_id() -> str:
    """Gera identificador opaco controlado pelo servidor."""
    return uuid.uuid4().hex


def pseudonymize_tenant(tenant_id: str | None) -> str:
    """Evita gravar o tenant bruto mantendo correlação operacional estável."""
    if not tenant_id:
        return "system"
    digest = hashlib.sha256(
        b"echomind-log-tenant-v1\x00" + tenant_id.encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _context_for(
    tenant_id: str | None,
    correlation_id: str | None = None,
) -> LogContext:
    tenant_ref = pseudonymize_tenant(tenant_id)
    current = _current_context.get()
    if current is not None and current.tenant_ref == tenant_ref and correlation_id is None:
        return current
    return LogContext(
        correlation_id=correlation_id or new_correlation_id(),
        tenant_ref=tenant_ref,
    )


def create_log_context(
    tenant_id: str | None,
    *,
    correlation_id: str | None = None,
) -> LogContext:
    """Cria contexto explícito para operações síncronas ou em background."""
    return _context_for(tenant_id, correlation_id)


@contextmanager
def bind_log_context(
    tenant_id: str | None,
    *,
    correlation_id: str | None = None,
) -> Iterator[LogContext]:
    """Isola correlation/tenant por operação e restaura o contexto anterior."""
    context = _context_for(tenant_id, correlation_id)
    token = _current_context.set(context)
    try:
        yield context
    finally:
        _current_context.reset(token)


def safe_error_code(error: BaseException | str) -> str:
    """Retorna somente um código técnico; mensagens de exceção nunca entram no log."""
    candidate = error if isinstance(error, str) else type(error).__name__
    normalized = candidate.strip().lower().replace("_", "-")
    if normalized == "timeout-error":
        return normalized
    if (
        not _IDENTIFIER_PATTERN.fullmatch(normalized)
        or not normalized.endswith(("error", "exception"))
    ):
        return "internal-error"
    return normalized


def _safe_identifier(value: str, fallback: str) -> str:
    normalized = value.strip().lower()
    return normalized if _IDENTIFIER_PATTERN.fullmatch(normalized) else fallback


def _safe_counts(values: Mapping[str, int] | None) -> dict[str, int]:
    safe: dict[str, int] = {}
    for name, value in (values or {}).items():
        key = str(name) if name in _KNOWN_COUNT_FIELDS else "other"
        if isinstance(value, int) and not isinstance(value, bool):
            safe[key] = safe.get(key, 0) + max(0, value)
    return safe


def _safe_source_types(values: Mapping[str, int] | None) -> dict[str, int]:
    safe: dict[str, int] = {}
    for source_type, count in (values or {}).items():
        key = source_type if source_type in _KNOWN_SOURCE_TYPES else "other"
        if isinstance(count, int) and not isinstance(count, bool):
            safe[key] = safe.get(key, 0) + max(0, count)
    return safe


def emit_event(
    *,
    event: str,
    status: str,
    stage: str,
    tenant_id: str | None = None,
    context: LogContext | None = None,
    duration_ms: float | None = None,
    counts: Mapping[str, int] | None = None,
    source_types: Mapping[str, int] | None = None,
    error_code: str | None = None,
    level: int | None = None,
) -> dict[str, object]:
    """Emite uma linha JSON allowlisted; qualquer falha do sink é ignorada."""
    log_context = context or _context_for(tenant_id)
    safe_status = status if status in {"started", "success", "error"} else "error"
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "event": _safe_identifier(event, "observability.invalid-event"),
        "status": safe_status,
        "stage": _safe_identifier(stage, "unknown"),
        "correlation_id": log_context.correlation_id,
        "tenant_ref": log_context.tenant_ref,
    }
    if duration_ms is not None:
        payload["duration_ms"] = round(max(0.0, float(duration_ms)), 3)
    safe_counts = _safe_counts(counts)
    if safe_counts:
        payload["counts"] = safe_counts
    safe_sources = _safe_source_types(source_types)
    if safe_sources:
        payload["source_types"] = safe_sources
    if error_code is not None:
        payload["error_code"] = safe_error_code(error_code)

    log_level = level if level is not None else (
        logging.ERROR if safe_status == "error" else logging.INFO
    )
    try:
        _logger.log(
            log_level,
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        )
    except Exception:
        # Observabilidade nunca pode alterar a resposta ou o processamento principal.
        pass
    return payload
