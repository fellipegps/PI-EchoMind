"""Eventos JSON locais e seguros para diagnostico do pipeline RAG."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Iterator, Mapping, Sequence


SCHEMA_VERSION = 1

_EVENTS = frozenset(
    {
        "chat.completed",
        "chat.failed",
        "ingestion.completed",
        "ingestion.failed",
        "rag.generation.completed",
        "rag.generation.failed",
        "rag.parent_expansion.failed",
        "rag.reranker.completed",
        "rag.reranker.failed",
        "rag.retrieval.completed",
        "rag.retrieval.failed",
        "rag.unanswered.completed",
        "rag.unanswered.failed",
    }
)
_STAGES = frozenset(
    {
        "cache",
        "chunking",
        "cleanup",
        "extraction",
        "finalization",
        "generation",
        "indexing",
        "initialization",
        "lookup",
        "parent_expansion",
        "persistence",
        "reranking",
        "retrieval",
        "state",
        "unanswered",
    }
)
_STATUSES = frozenset({"error", "fallback", "success"})
_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}
_COUNT_FIELDS = frozenset(
    {
        "answered",
        "cache_hits",
        "chunks",
        "grouped",
        "lexical_candidates",
        "parents",
        "previous_chunks",
        "rerank_candidates",
        "retrieved_documents",
        "vector_candidates",
    }
)
_SOURCE_TYPES = frozenset({"document_chunk", "event", "faq"})
_SAFE_ERROR_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

_correlation_id: ContextVar[str | None] = ContextVar(
    "echomind_correlation_id",
    default=None,
)
logger = logging.getLogger("echomind.observability")


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def current_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def bind_correlation_id(correlation_id: str | None = None) -> Iterator[str]:
    """Isola o correlation ID no contexto atual e sempre restaura o anterior."""
    value = correlation_id or new_correlation_id()
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)


def pseudonymize_tenant(tenant_id: str) -> str:
    material = f"echomind-tenant-v1:{tenant_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _safe_duration(duration_ms: float) -> float:
    try:
        value = float(duration_ms)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value) or value < 0:
        return 0.0
    return round(value, 3)


def _safe_counts(counts: Mapping[str, int] | None) -> dict[str, int]:
    safe: dict[str, int] = {}
    for key, value in (counts or {}).items():
        if key not in _COUNT_FIELDS or isinstance(value, bool):
            continue
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        safe[key] = max(0, numeric)
    return dict(sorted(safe.items()))


def _safe_source_types(source_types: Sequence[str] | None) -> list[str]:
    return sorted({value for value in (source_types or ()) if value in _SOURCE_TYPES})


def _safe_error_type(error: BaseException | None) -> str | None:
    if error is None:
        return None
    name = type(error).__name__
    return name if _SAFE_ERROR_TYPE.fullmatch(name) else "Exception"


def build_observability_event(
    event: str,
    *,
    status: str,
    stage: str,
    tenant_id: str,
    duration_ms: float,
    level: str = "info",
    correlation_id: str | None = None,
    counts: Mapping[str, int] | None = None,
    source_types: Sequence[str] | None = None,
    error: BaseException | None = None,
) -> dict[str, object]:
    """Constroi somente o schema permitido, sem campos textuais livres."""
    if event not in _EVENTS:
        raise ValueError("Evento de observabilidade nao permitido.")
    if status not in _STATUSES:
        raise ValueError("Status de observabilidade nao permitido.")
    if stage not in _STAGES:
        raise ValueError("Etapa de observabilidade nao permitida.")
    if level not in _LEVELS:
        raise ValueError("Nivel de observabilidade nao permitido.")

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "level": level,
        "status": status,
        "stage": stage,
        "correlation_id": correlation_id or current_correlation_id() or new_correlation_id(),
        "tenant_ref": pseudonymize_tenant(tenant_id),
        "duration_ms": _safe_duration(duration_ms),
        "counts": _safe_counts(counts),
        "source_types": _safe_source_types(source_types),
    }
    error_type = _safe_error_type(error)
    if error_type is not None:
        payload["error_type"] = error_type
    return payload


def emit_observability_event(event: str, **fields: object) -> dict[str, object] | None:
    """Emite JSON ordenado; qualquer falha de logging e isolada do fluxo principal."""
    try:
        payload = build_observability_event(event, **fields)  # type: ignore[arg-type]
        level_name = str(payload["level"])
        logger.log(
            _LEVELS[level_name],
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        )
        return payload
    except Exception:
        return None
