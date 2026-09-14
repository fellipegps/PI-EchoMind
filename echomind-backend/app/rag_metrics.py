"""Persistencia e leitura tenant-scoped de agregados operacionais do RAG."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable, Mapping, Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .database import RagMetricDaily, SessionLocal


RAG_METRIC_RETENTION_DAYS = 90
RAG_METRIC_DEFAULT_PERIOD_DAYS = 30
RAG_METRIC_MAX_PERIOD_DAYS = 90
RAG_METRIC_QUEUE_MAXSIZE = 2048
RAG_METRIC_BATCH_SIZE = 64
RAG_METRIC_FLUSH_INTERVAL_SECONDS = 0.25

_logger = logging.getLogger("echomind.rag_metrics")

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


@dataclass(frozen=True, slots=True)
class MetricEvent:
    tenant_id: str
    payload: Mapping[str, object]


MetricBatchSink = Callable[[Sequence[MetricEvent]], None]


class MetricEventWriter:
    """Fila local limitada que retira persistencia do caminho critico da API."""

    def __init__(
        self,
        persist_batch: MetricBatchSink,
        *,
        max_queue_size: int = RAG_METRIC_QUEUE_MAXSIZE,
        batch_size: int = RAG_METRIC_BATCH_SIZE,
        flush_interval_seconds: float = RAG_METRIC_FLUSH_INTERVAL_SECONDS,
    ) -> None:
        if max_queue_size < 1 or batch_size < 1 or flush_interval_seconds <= 0:
            raise ValueError("Configuracao invalida do gravador de metricas.")
        self._persist_batch = persist_batch
        self._batch_size = batch_size
        self._flush_interval_seconds = flush_interval_seconds
        self._queue: Queue[MetricEvent] = Queue(maxsize=max_queue_size)
        self._stop = Event()
        self._lifecycle_lock = Lock()
        self._thread: Thread | None = None
        self._dropped_events = 0

    @property
    def dropped_events(self) -> int:
        with self._lifecycle_lock:
            return self._dropped_events

    def start(self) -> None:
        """Inicia um unico worker daemon; pode ser chamado novamente apos stop."""
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                name="echomind-rag-metrics",
                daemon=True,
            )
            self._thread.start()

    def enqueue(self, tenant_id: str, payload: Mapping[str, object]) -> bool:
        """Aceita apenas eventos agregaveis e nunca bloqueia o chamador."""
        normalized_tenant = tenant_id.strip()
        if not normalized_tenant or metric_deltas(payload) is None:
            return False
        self.start()
        try:
            self._queue.put_nowait(
                MetricEvent(
                    tenant_id=normalized_tenant,
                    payload=dict(payload),
                )
            )
        except Full:
            with self._lifecycle_lock:
                self._dropped_events += 1
            return False
        return True

    def stop(self, *, timeout_seconds: float = 5.0) -> bool:
        """Solicita encerramento, drenando a fila dentro do limite informado."""
        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop.set()
        thread.join(timeout=max(0.0, timeout_seconds))
        stopped = not thread.is_alive()
        if stopped:
            with self._lifecycle_lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def _next_batch(self) -> list[MetricEvent]:
        try:
            first = self._queue.get(timeout=self._flush_interval_seconds)
        except Empty:
            return []

        batch = [first]
        deadline = monotonic() + self._flush_interval_seconds
        while len(batch) < self._batch_size:
            if self._stop.is_set():
                timeout = 0.0
            else:
                timeout = max(0.0, deadline - monotonic())
            if timeout == 0.0 and not self._stop.is_set():
                break
            try:
                batch.append(self._queue.get(timeout=timeout))
            except Empty:
                break
        return batch

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            batch = self._next_batch()
            if not batch:
                continue
            try:
                self._persist_batch(batch)
            except Exception:
                # Perder uma amostra operacional e preferivel a afetar chat/ingestao.
                _logger.warning("rag_metric_batch_failed", exc_info=False)
            finally:
                for _event in batch:
                    self._queue.task_done()


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
    """Persiste um evento diretamente; util para manutencao e compatibilidade."""
    persist_metric_batch([MetricEvent(tenant_id=tenant_id, payload=payload)])


def persist_metric_batch(events: Sequence[MetricEvent]) -> None:
    """Persiste um lote em uma transacao e aplica retencao uma vez por tenant."""
    if not events:
        return
    with SessionLocal() as db:
        affected_tenants: set[str] = set()
        for event in events:
            if record_metric_event(
                db,
                tenant_id=event.tenant_id,
                payload=event.payload,
            ):
                affected_tenants.add(event.tenant_id)
        for tenant_id in sorted(affected_tenants):
            purge_expired_metrics(db, tenant_id=tenant_id)
        db.commit()


metric_event_writer = MetricEventWriter(persist_metric_batch)


def start_metric_writer() -> None:
    metric_event_writer.start()


def enqueue_metric_event(tenant_id: str, payload: Mapping[str, object]) -> bool:
    return metric_event_writer.enqueue(tenant_id, payload)


def stop_metric_writer(*, timeout_seconds: float = 5.0) -> bool:
    return metric_event_writer.stop(timeout_seconds=timeout_seconds)


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
