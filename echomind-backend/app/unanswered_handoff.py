"""Short-lived bearer confirmation bound to an already minimized interaction.

Only the hash is stored. No public lookup by interaction ID or arbitrary text.
The row lock serializes retries and the receipt commits with queue registration.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import Interaction, utc_now

HANDOFF_TTL = timedelta(hours=1)


class InvalidHandoff(ValueError):
    pass


def new_handoff() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, sha256(token.encode("ascii")).hexdigest()


def submit_unanswered(db: Session, *, tenant_id: str, token: str, now: datetime | None = None) -> None:
    from .rag_engine import register_unanswered_question

    digest = sha256(token.encode("ascii")).hexdigest()
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        db.execute(text("SET LOCAL statement_timeout = '5s'"))
    row = (
        db.query(Interaction)
        .filter(Interaction.tenant_id == tenant_id, Interaction.unanswered_token_hash == digest)
        .with_for_update()
        .first()
    )
    current = now or utc_now()
    current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
    asked_at = row.asked_at.replace(tzinfo=timezone.utc) if row is not None else current
    if row is None or row.was_answered or not (asked_at <= current <= asked_at + HANDOFF_TTL):
        raise InvalidHandoff("Esta confirmação não está disponível. Faça a pergunta novamente para encaminhá-la.")
    if row.unanswered_submitted_at is not None:
        return
    register_unanswered_question(row.question, tenant_id, db)
    row.unanswered_submitted_at = current
    # The caller commits the queue write and receipt atomically.
    db.flush()
