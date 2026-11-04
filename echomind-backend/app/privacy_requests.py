"""Acesso e eliminação de interações selecionadas por operador autorizado."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .database import Interaction

MAX_SELECTED_INTERACTIONS = 100


def _selection(tenant_id: str, interaction_ids: list[str]) -> tuple[str, list[str]]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("Informe uma instituição.")
    if (not isinstance(interaction_ids, list) or not 1 <= len(interaction_ids) <= MAX_SELECTED_INTERACTIONS
            or any(not isinstance(value, str) or not value.strip() or len(value) > 128 for value in interaction_ids)):
        raise ValueError("Selecione de 1 a 100 identificadores de interação válidos.")
    ids = [value.strip() for value in interaction_ids]
    if len(set(ids)) != len(ids):
        raise ValueError("A seleção não pode conter identificadores repetidos.")
    return tenant_id.strip(), ids


def _selected_records(db: Session, tenant_id: str, interaction_ids: list[str], *, lock: bool = False):
    tenant, ids = _selection(tenant_id, interaction_ids)
    query = db.query(Interaction).filter(Interaction.tenant_id == tenant, Interaction.id.in_(ids))
    if lock:
        query = query.with_for_update()
    rows = query.order_by(Interaction.asked_at, Interaction.id).all()
    if len(rows) != len(ids):
        # Não distingue registro inexistente de registro pertencente a outra instituição.
        raise ValueError("A seleção contém registros indisponíveis para esta instituição.")
    return rows


def export_chat_records(db: Session, *, tenant_id: str, interaction_ids: list[str]) -> dict:
    """Arquivo para revisão interna; IDs e semelhança de texto não provam identidade."""
    rows = _selected_records(db, tenant_id, interaction_ids)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "selected_interactions_only",
        "requires_review": True,
        "interactions": [
            {"id": row.id, "question": row.question, "answer": row.answer,
             "asked_at": row.asked_at.isoformat() if row.asked_at else None,
             "feedback_helpful": row.feedback_helpful, "was_answered": row.was_answered}
            for row in rows
        ],
    }


def delete_chat_records(db: Session, *, tenant_id: str, interaction_ids: list[str], apply: bool = False) -> int:
    """Prévia por padrão. Não realiza commit nem deduz registros relacionados."""
    rows = _selected_records(db, tenant_id, interaction_ids, lock=apply)
    if not apply:
        return len(rows)
    deleted = db.query(Interaction).filter(
        Interaction.tenant_id == tenant_id.strip(), Interaction.id.in_([row.id for row in rows]),
    ).delete(synchronize_session=False)
    if deleted != len(rows):
        raise RuntimeError("Os registros selecionados mudaram durante a operação.")
    return deleted
