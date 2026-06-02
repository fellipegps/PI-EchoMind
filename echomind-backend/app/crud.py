"""
crud.py – Operações de banco de dados para todas as entidades.
"""

from __future__ import annotations

import json
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .database import Faq, CompanyEvent, Config, Interaction, UnansweredQuestion, utc_now
from .schemas import (
    FaqCreate, FaqUpdate,
    EventCreate, EventUpdate,
    ConfigUpdate,
)
from .middleware import latency_store


# ══════════════════════════════════════════════════════════════════════════════
#  FAQs
# ══════════════════════════════════════════════════════════════════════════════

def get_faqs(db: Session) -> list[Faq]:
    return db.query(Faq).order_by(desc(Faq.created_at)).all()


def get_totem_faqs(db: Session) -> list[Faq]:
    return db.query(Faq).filter(Faq.show_on_totem == True).limit(4).all()


def create_faq(db: Session, payload: FaqCreate) -> Faq:
    faq = Faq(
        question=payload.question,
        answer=payload.answer,
        show_on_totem=payload.show_on_totem,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def update_faq(db: Session, faq_id: str, payload: FaqUpdate) -> Optional[Faq]:
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    faq.updated_at = utc_now()
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def toggle_faq_totem(db: Session, faq_id: str) -> Faq | str | None:
    """
    Ativa/desativa show_on_totem.
    Retorna 'limit_exceeded' se já há 4 ativas e a tentativa é de ativar.
    """
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return None

    if not faq.show_on_totem:
        active_count = db.query(Faq).filter(Faq.show_on_totem == True).count()
        if active_count >= 4:
            return "limit_exceeded"

    faq.show_on_totem = not faq.show_on_totem
    faq.updated_at = utc_now()
    db.commit()
    db.refresh(faq)
    return faq


def delete_faq(db: Session, faq_id: str) -> bool:
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return False
    db.delete(faq)
    db.commit()
    get_cached_faq_answers.cache_clear()
    return True


@lru_cache(maxsize=1)
def get_cached_faq_answers() -> tuple[tuple[str, str, str], ...]:
    """Cache simples das FAQs mais consultadas para respostas instantâneas no totem."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        rows = (
            db.query(Faq)
            .order_by(desc(Faq.total_consults), desc(Faq.created_at))
            .limit(10)
            .all()
        )
        return tuple((row.id, row.question, row.answer) for row in rows)
    finally:
        db.close()


def find_cached_faq_answer(question: str) -> Optional[tuple[str, str]]:
    """Retorna (faq_id, answer) quando a pergunta bate com uma FAQ frequente."""
    normalized = question.strip().lower()
    if len(normalized) < 4:
        return None
    for faq_id, faq_question, faq_answer in get_cached_faq_answers():
        fq = faq_question.strip().lower()
        if normalized == fq or normalized in fq or fq in normalized:
            return faq_id, faq_answer
    return None


def increment_faq_consult(db: Session, faq_id: str) -> None:
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return
    faq.total_consults = (faq.total_consults or 0) + 1
    db.commit()
    get_cached_faq_answers.cache_clear()


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════════════

def get_events(db: Session) -> list[CompanyEvent]:
    return db.query(CompanyEvent).order_by(desc(CompanyEvent.event_date)).all()


def create_event(db: Session, payload: EventCreate) -> CompanyEvent:
    event = CompanyEvent(
        title=payload.title,
        event_date=payload.event_date,
        event_type=payload.event_type,
        description=payload.description,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, event_id: str, payload: EventUpdate) -> Optional[CompanyEvent]:
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    event.updated_at = utc_now()
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: str) -> bool:
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        return False
    db.delete(event)
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def get_config(db: Session) -> Optional[Config]:
    return db.query(Config).first()


def upsert_config(db: Session, payload: ConfigUpdate) -> Config:
    cfg = db.query(Config).first()
    if not cfg:
        cfg = Config()
        db.add(cfg)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    cfg.updated_at = utc_now()
    db.commit()
    db.refresh(cfg)
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def save_interaction(db: Session, question: str, answer: str) -> Interaction:
    """Persiste uma interação completa para uso no Dashboard."""
    # Detecta as duas formas de resposta negativa:
    # 1. Fallback direto do RAG (sem docs): "Não tenho informações suficientes..."
    # 2. Resposta do LLM quando não encontra contexto: "Não tenho essa informação..."
    _not_answered_markers = (
        "Não tenho informações",   # cobre ambos os fallbacks
        "não tenho informações",
    )
    was_answered = bool(answer) and not any(m in answer for m in _not_answered_markers)
    interaction = Interaction(
        question=question,
        answer=answer,
        was_answered=was_answered,
    )
    db.add(interaction)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return interaction


# ══════════════════════════════════════════════════════════════════════════════
#  UNANSWERED QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_unanswered_questions(db: Session) -> list[dict]:
    rows = (
        db.query(UnansweredQuestion)
        .filter(UnansweredQuestion.converted == False)
        .order_by(desc(UnansweredQuestion.count))
        .all()
    )
    result = []
    for row in rows:
        result.append({
            "id": row.id,
            "canonical_question": row.canonical_question,
            "count": row.count,
            "first_asked": row.first_asked,
            "last_asked": row.last_asked,
            "similar_questions": json.loads(row.similar_questions or "[]"),
        })
    return result


def get_unanswered_by_id(db: Session, question_id: str) -> Optional[dict]:
    """Retorna um único registro de pergunta não respondida como dict."""
    uq = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == question_id).first()
    if not uq:
        return None
    return {
        "id": uq.id,
        "canonical_question": uq.canonical_question,
        "count": uq.count,
        "first_asked": uq.first_asked,
        "last_asked": uq.last_asked,
        "similar_questions": json.loads(uq.similar_questions or "[]"),
    }


def delete_unanswered_question(db: Session, question_id: str) -> bool:
    """Remove permanentemente uma pergunta pendente pelo ID."""
    uq = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == question_id).first()
    if not uq:
        return False
    db.delete(uq)
    db.commit()
    return True


def convert_unanswered_to_faq(db: Session, question_id: str, answer: str, question: Optional[str] = None) -> Optional[Faq]:
    uq = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == question_id).first()
    if not uq:
        return None

    # Cria FAQ
    faq = Faq(
        question=(question or uq.canonical_question).strip(),
        answer=answer,
        show_on_totem=False,
    )
    db.add(faq)

    # Marca como convertida
    uq.converted = True
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def save_feedback(db: Session, question: str, answer: str, helpful: bool) -> Interaction:
    interaction = Interaction(
        question=question,
        answer=answer,
        was_answered=True,
        feedback_helpful=helpful,
    )
    db.add(interaction)
    db.commit()
    return interaction


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats(db: Session) -> dict:
    total = db.query(Interaction).count()
    unanswered_count = (
        db.query(UnansweredQuestion)
        .filter(UnansweredQuestion.converted == False)
        .count()
    )

    # Interações dos últimos 7 dias
    today = utc_now().date()
    daily = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        count = (
            db.query(Interaction)
            .filter(Interaction.asked_at.between(day_start, day_end))
            .count()
        )
        daily.append({"date": day.strftime("%d/%m"), "count": count})

    # Top FAQs por consultas diretas no cache/FAQ. Caso ainda não existam
    # consultas registradas, mantém fallback por correspondência textual.
    faqs = db.query(Faq).order_by(desc(Faq.total_consults), desc(Faq.created_at)).limit(5).all()
    top_faqs = []
    for faq in faqs:
        hits = faq.total_consults or 0
        if hits == 0:
            hits = (
                db.query(Interaction)
                .filter(func.lower(Interaction.question).contains(
                    faq.question[:30].lower()
                ))
                .count()
            )
        top_faqs.append({"question": faq.question[:50], "count": hits or 0})

    top_faqs.sort(key=lambda x: x["count"], reverse=True)

    feedback_total = db.query(Interaction).filter(Interaction.feedback_helpful.isnot(None)).count()
    feedback_positive = db.query(Interaction).filter(Interaction.feedback_helpful == True).count()
    satisfaction_rate = round((feedback_positive / feedback_total) * 100, 1) if feedback_total else 0.0

    return {
        "total_questions": total,
        "unanswered_questions": unanswered_count,
        "avg_response_time": latency_store.summary()["avg_response_time"],
        "satisfaction_rate": satisfaction_rate,
        "daily_interactions": daily,
        "top_faqs": top_faqs[:5],
    }
