"""Descarte de conversas pela política do servidor e operações por instituição."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from .database import ChatMetricDaily, Interaction, SessionLocal, UnansweredQuestion, UnansweredSuppression
from .runtime_config import chat_history_retention_days
from .structured_logging import emit_event, safe_error_code


CHAT_METRIC_RETENTION_DAYS = 90


def purge_chat_data(
    db: Session, *, tenant_id: str, cutoff: datetime, apply: bool = False,
) -> dict[str, int]:
    """Conta ou exclui registros anteriores ao corte; o chamador controla o commit."""
    if not tenant_id.strip():
        raise ValueError("Informe uma instituição.")
    return _purge_expired_history(db, cutoff=cutoff, apply=apply, tenant_id=tenant_id)


def _purge_expired_history(
    db: Session, *, cutoff: datetime, apply: bool, tenant_id: str | None = None,
) -> dict[str, int]:
    questions = db.query(UnansweredQuestion).filter(UnansweredQuestion.first_asked < cutoff)
    suppressions = db.query(UnansweredSuppression)
    interactions = db.query(Interaction).filter(Interaction.asked_at < cutoff)
    if tenant_id is not None:
        questions = questions.filter(UnansweredQuestion.tenant_id == tenant_id)
        suppressions = suppressions.filter(UnansweredSuppression.tenant_id == tenant_id)
        interactions = interactions.filter(Interaction.tenant_id == tenant_id)

    expired_suppressed_question = questions.filter(
        UnansweredQuestion.tenant_id == UnansweredSuppression.tenant_id,
        UnansweredQuestion.id == UnansweredSuppression.question_id,
    ).exists()
    targets = {
        "suppressions": suppressions.filter(
            or_(
                UnansweredSuppression.created_at < cutoff,
                expired_suppressed_question,
            ),
        ),
        "unanswered": questions,
        "interactions": interactions,
    }
    counts = {}
    for name, query in targets.items():
        counts[name] = query.delete(synchronize_session=False) if apply else query.count()
    return counts


def run_configured_retention(*, session_factory=None, now: datetime | None = None) -> dict[str, int]:
    """Aplica o prazo do servidor a todo o histórico, inclusive registros legados."""
    factory = session_factory or SessionLocal
    timestamp = now or datetime.now(timezone.utc)
    counts: dict[str, int] = {}
    try:
        cutoff = timestamp - timedelta(days=chat_history_retention_days())
        with factory() as db:
            if db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL statement_timeout = '20s'"))
                db.execute(text("SET LOCAL lock_timeout = '3s'"))
            deleted = _purge_expired_history(db, cutoff=cutoff, apply=True)
            db.commit()
            counts = deleted
        emit_event(
            event="privacy.retention", status="success", stage="cleanup",
            counts={f"deleted_{kind}": count for kind, count in counts.items()},
        )
    except Exception as exc:
        emit_event(event="privacy.retention", status="error", stage="cleanup", error_code=safe_error_code(exc))
    try:
        with factory() as db:
            first_metric_day = timestamp.date() - timedelta(days=CHAT_METRIC_RETENTION_DAYS - 1)
            db.query(ChatMetricDaily).filter(ChatMetricDaily.metric_date < first_metric_day).delete(
                synchronize_session=False,
            )
            db.commit()
    except Exception as exc:
        emit_event(event="privacy.chat-metrics-retention", status="error", stage="cleanup", error_code=safe_error_code(exc))
    return counts


async def retention_worker(stop: asyncio.Event, *, interval_seconds: float = 3600) -> None:
    """Primeira execução em até uma hora; aguarda a operação antes de encerrar."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            try:
                await asyncio.to_thread(run_configured_retention)
            except Exception as exc:
                emit_event(event="privacy.retention", status="error", stage="schedule", error_code=safe_error_code(exc))
