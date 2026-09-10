"""Persistencia e leitura tenant-scoped de agregados operacionais do RAG."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Mapping

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .database import RagMetricDaily, SessionLocal


RAG_METRIC_RETENTION_DAYS = 90
RAG_METRIC_DEFAULT_PERIOD_DAYS = 30
RAG_METRIC_MAX_PERIOD_DAYS = 90

_AGGREGATE_FIELDS = (
    "chat_success",
    "chat_error",
    "retrieval_success",
    "retrieval_error",
    "retrieval_duration_ms",
    "retrieved_results",
    "unanswered",
    "ingestion_success",
    "ingestion_error",
    "ingestion_duration_ms",
    "source_faq",
    "source_event",
    "source_document_chunk",
    "source_document_parent",
    "source_other",
)
_SOURCE_COLUMNS = {
    "faq": "source_faq",
    "event": "source_event",
    "document_chunk": "source_document_chunk",
    "document_parent": "source_document_parent",
    "other": "source_other",
}


def _nonnegative_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def _nonnegative_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def metric_deltas(payload: Mapping[str, object]) -> dict[str, int | float] | None:
    """Converte somente dimensoes aprovadas do schema v1 em incrementos fixos."""
    event = payload.get("event")
    status = payload.get("status")
    stage = payload.get("stage")
    if status not in {"success", "error"}:
        return None

    counts_value = payload.get("counts")
    counts = counts_value if isinstance(counts_value, Mapping) else {}
    sources_value = payload.get("source_types")
    sources = sources_value if isinstance(sources_value, Mapping) else {}
    duration_ms = _nonnegative_number(payload.get("duration_ms"))

    deltas: dict[str, int | float] = {field: 0 for field in _AGGREGATE_FIELDS}
    if event == "rag.chat":
        deltas[f"chat_{status}"] = 1
        deltas["retrieved_results"] = _nonnegative_integer(
            counts.get("retrieved_results")
        )
    elif event == "rag.retrieval":
        deltas[f"retrieval_{status}"] = 1
        deltas["retrieval_duration_ms"] = duration_ms
    elif event == "rag.unanswered" and status == "success":
        deltas["unanswered"] = 1
    elif event == "rag.ingestion":
        deltas[f"ingestion_{status}"] = 1
        deltas["ingestion_duration_ms"] = duration_ms
    else:
        return None

    # Sources aparecem no retrieval normal e no caminho exclusivo de FAQ cache.
    if event == "rag.retrieval" or (event == "rag.chat" and stage == "faq-cache"):
        for source_type, count in sources.items():
            column = _SOURCE_COLUMNS.get(str(source_type), "source_other")
            deltas[column] += _nonnegative_integer(count)
    return deltas


def record_metric_event(
    db: Session,
    *,
    tenant_id: str,
    payload: Mapping[str, object],
    metric_date: date | None = None,
) -> bool:
    """Acumula um evento sanitizado de forma atomica para um tenant e dia."""
    normalized_tenant = tenant_id.strip()
    deltas = metric_deltas(payload)
    if not normalized_tenant or deltas is None:
        return False

    day = metric_date or datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "tenant_id": normalized_tenant,
        "metric_date": day,
        "created_at": now,
        "updated_at": now,
        **deltas,
    }
    table = RagMetricDaily.__table__
    dialect_name = db.get_bind().dialect.name

    if dialect_name == "postgresql":
        statement = postgresql_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.tenant_id, table.c.metric_date],
            set_={
                **{
                    field: table.c[field] + deltas[field]
                    for field in _AGGREGATE_FIELDS
                },
                "updated_at": now,
            },
        )
        db.execute(statement)
        return True

    if dialect_name == "sqlite":
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.tenant_id, table.c.metric_date],
            set_={
                **{
                    field: table.c[field] + deltas[field]
                    for field in _AGGREGATE_FIELDS
                },
                "updated_at": now,
            },
        )
        db.execute(statement)
        return True

    existing = db.get(
        RagMetricDaily,
        {"tenant_id": normalized_tenant, "metric_date": day},
    )
    if existing is None:
        db.add(RagMetricDaily(**values))
    else:
        for field in _AGGREGATE_FIELDS:
            setattr(existing, field, getattr(existing, field) + deltas[field])
        existing.updated_at = now
    return True


def purge_expired_metrics(
    db: Session,
    *,
    tenant_id: str,
    today: date | None = None,
) -> int:
    """Mantem somente o dia atual e os 89 anteriores para um tenant."""
    reference_date = today or datetime.now(timezone.utc).date()
    cutoff = reference_date - timedelta(days=RAG_METRIC_RETENTION_DAYS - 1)
    result = db.execute(
        delete(RagMetricDaily).where(
            RagMetricDaily.tenant_id == tenant_id,
            RagMetricDaily.metric_date < cutoff,
        )
    )
    return int(result.rowcount or 0)


def persist_metric_event(tenant_id: str, payload: Mapping[str, object]) -> None:
    """Sink local: falhas sao isoladas pelo emissor de logs estruturados."""
    with SessionLocal() as db:
        record_metric_event(db, tenant_id=tenant_id, payload=payload)
        purge_expired_metrics(db, tenant_id=tenant_id)
        db.commit()


def _average(total: int | float, count: int) -> float:
    return round(float(total) / count, 2) if count else 0.0


def get_rag_metrics(
    db: Session,
    *,
    tenant_id: str,
    days: int = RAG_METRIC_DEFAULT_PERIOD_DAYS,
    today: date | None = None,
) -> dict[str, object]:
    """Retorna apenas agregados do tenant autenticado em uma janela limitada."""
    if not 1 <= days <= RAG_METRIC_MAX_PERIOD_DAYS:
        raise ValueError("Periodo de metricas fora do limite permitido.")

    end_date = today or datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    rows = db.execute(
        select(RagMetricDaily)
        .where(
            RagMetricDaily.tenant_id == tenant_id,
            RagMetricDaily.metric_date.between(start_date, end_date),
        )
        .order_by(RagMetricDaily.metric_date)
    ).scalars().all()

    totals = {
        field: sum(getattr(row, field) for row in rows)
        for field in _AGGREGATE_FIELDS
    }
    query_count = int(totals["chat_success"] + totals["chat_error"])
    retrieval_count = int(
        totals["retrieval_success"] + totals["retrieval_error"]
    )
    ingestion_count = int(totals["ingestion_success"] + totals["ingestion_error"])
    failure_count = int(
        totals["chat_error"]
        + totals["retrieval_error"]
        + totals["ingestion_error"]
    )

    return {
        "period_days": days,
        "start_date": start_date,
        "end_date": end_date,
        "has_data": bool(rows),
        "query_count": query_count,
        "query_error_count": int(totals["chat_error"]),
        "failure_count": failure_count,
        "average_retrieved_results": _average(
            totals["retrieved_results"], query_count
        ),
        "unanswered_rate": min(
            100.0,
            _average(totals["unanswered"] * 100, query_count),
        ),
        "retrieval": {
            "total": retrieval_count,
            "success": int(totals["retrieval_success"]),
            "error": int(totals["retrieval_error"]),
            "average_latency_ms": _average(
                totals["retrieval_duration_ms"], retrieval_count
            ),
        },
        "ingestion": {
            "total": ingestion_count,
            "success": int(totals["ingestion_success"]),
            "error": int(totals["ingestion_error"]),
            "average_latency_ms": _average(
                totals["ingestion_duration_ms"], ingestion_count
            ),
        },
        "source_types": {
            "faq": int(totals["source_faq"]),
            "event": int(totals["source_event"]),
            "document_chunk": int(totals["source_document_chunk"]),
            "document_parent": int(totals["source_document_parent"]),
            "other": int(totals["source_other"]),
        },
        "daily": [
            {
                "date": row.metric_date,
                "queries": row.chat_success + row.chat_error,
                "failures": (
                    row.chat_error + row.retrieval_error + row.ingestion_error
                ),
                "unanswered": row.unanswered,
            }
            for row in rows
        ],
    }
