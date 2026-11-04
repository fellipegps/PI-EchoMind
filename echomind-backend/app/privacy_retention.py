"""Descarte de conversas por instituição, sem acessar o provedor de IA."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from .database import Config, Interaction, SessionLocal, UnansweredQuestion, UnansweredSuppression
from .structured_logging import emit_event, safe_error_code


def purge_chat_data(
    db: Session, *, tenant_id: str, cutoff: datetime, apply: bool = False,
) -> dict[str, int]:
    """Conta ou exclui registros anteriores ao corte; o chamador controla o commit."""
    if not tenant_id.strip():
        raise ValueError("Informe uma instituição.")
    questions = db.query(UnansweredQuestion.id).filter(
        UnansweredQuestion.tenant_id == tenant_id,
        UnansweredQuestion.first_asked < cutoff,
    )
    targets = {
        "suppressions": db.query(UnansweredSuppression).filter(
            UnansweredSuppression.tenant_id == tenant_id,
            or_(
                UnansweredSuppression.created_at < cutoff,
                UnansweredSuppression.question_id.in_(questions),
            ),
        ),
        "unanswered": db.query(UnansweredQuestion).filter(
            UnansweredQuestion.tenant_id == tenant_id,
            UnansweredQuestion.first_asked < cutoff,
        ),
        "interactions": db.query(Interaction).filter(
            Interaction.tenant_id == tenant_id,
            Interaction.asked_at < cutoff,
        ),
    }
    counts = {}
    for name, query in targets.items():
        counts[name] = query.delete(synchronize_session=False) if apply else query.count()
    return counts


def run_configured_retention(*, session_factory=None, now: datetime | None = None) -> int:
    """Aplica apenas políticas explicitamente ativadas; falhas não afetam o chat."""
    factory = session_factory or SessionLocal
    timestamp = now or datetime.now(timezone.utc)
    with factory() as db:
        config_ids = [row[0] for row in db.query(Config.id).filter(Config.chat_retention_enabled.is_(True)).all()]
    completed = 0
    for config_id in config_ids:
        try:
            with factory() as db:
                if db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL statement_timeout = '20s'"))
                    db.execute(text("SET LOCAL lock_timeout = '3s'"))
                config = db.query(Config).filter(Config.id == config_id).with_for_update(skip_locked=True).first()
                if config is None or not config.privacy_ready:
                    continue
                counts = purge_chat_data(
                    db, tenant_id=config.tenant_id,
                    cutoff=timestamp - timedelta(days=config.chat_retention_days), apply=True,
                )
                db.commit()
                completed += 1
                emit_event(event="privacy.retention", status="success", stage="cleanup", tenant_id=config.tenant_id,
                           counts={"deleted_interactions": counts["interactions"], "deleted_unanswered": counts["unanswered"], "deleted_suppressions": counts["suppressions"]})
        except Exception as exc:
            emit_event(event="privacy.retention", status="error", stage="cleanup", error_code=safe_error_code(exc))
    return completed


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
