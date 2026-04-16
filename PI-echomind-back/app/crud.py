"""
crud.py – Operações de banco de dados para todas as entidades.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .database import Faq, CompanyEvent, Config, Interaction, UnansweredQuestion
from .schemas import (
    FaqCreate, FaqUpdate,
    EventCreate, EventUpdate,
    ConfigUpdate,
    DashboardResponse, DailyInteraction, TopFaq,
)


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
    return faq


def update_faq(db: Session, faq_id: str, payload: FaqUpdate) -> Optional[Faq]:
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    faq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(faq)
    return faq


def toggle_faq_totem(db: Session, faq_id: str):
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
    faq.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(faq)
    return faq


def delete_faq(db: Session, faq_id: str) -> bool:
    faq = db.query(Faq).filter(Faq.id == faq_id).first()
    if not faq:
        return False
    db.delete(faq)
    db.commit()
    return True


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
    event.updated_at = datetime.utcnow()
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
    cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def save_interaction(db: Session, question: str, answer: str) -> Interaction:
    """Persiste uma interação completa para uso no Dashboard."""
    was_answered = bool(answer) and "Não tenho informações" not in answer
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


def convert_unanswered_to_faq(db: Session, question_id: str, answer: str) -> Optional[Faq]:
    uq = db.query(UnansweredQuestion).filter(UnansweredQuestion.id == question_id).first()
    if not uq:
        return None

    # Cria FAQ
    faq = Faq(
        question=uq.canonical_question,
        answer=answer,
        show_on_totem=False,
    )
    db.add(faq)

    # Marca como convertida
    uq.converted = True
    db.commit()
    db.refresh(faq)
    return faq


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
    today = datetime.utcnow().date()
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

    # Top FAQs (por frequência nas interações – match simples por substring)
    faqs = db.query(Faq).order_by(desc(Faq.created_at)).limit(5).all()
    top_faqs = []
    for faq in faqs:
        hits = (
            db.query(Interaction)
            .filter(func.lower(Interaction.question).contains(
                faq.question[:30].lower()
            ))
            .count()
        )
        top_faqs.append({"question": faq.question[:50], "count": hits or 0})

    top_faqs.sort(key=lambda x: x["count"], reverse=True)

    return {
        "total_questions": total,
        "unanswered_questions": unanswered_count,
        "avg_response_time": "~1.2s",  # Em produção: medir real com middleware
        "daily_interactions": daily,
        "top_faqs": top_faqs[:5],
    }
