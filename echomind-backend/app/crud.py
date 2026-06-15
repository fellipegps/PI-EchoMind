"""
crud.py - Operacoes de banco com isolamento por tenant.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .database import CompanyEvent, Config, Faq, Interaction, UnansweredQuestion, utc_now
from .middleware import latency_store
from .schemas import ConfigUpdate, EventCreate, EventUpdate, FaqCreate, FaqUpdate


DEFAULT_TONE = "profissional e cordial"
DEFAULT_VOICE = "feminina"


def ensure_tenant_onboarded(
    db: Session,
    tenant_id: str,
    email: str = "",
    company_name: str | None = None,
    full_name: str | None = None,
) -> Config:
    """
    Garante que um usuario autenticado tenha o conjunto inicial de dados.

    Hoje o template cria a configuracao base do tenant. FAQs e eventos ficam
    vazios para nao exibir conteudo ficticio no totem publico de uma empresa nova.
    """
    existing = get_config(db, tenant_id)
    if existing:
        return existing

    display_name = (company_name or "").strip()
    if not display_name:
        display_name = email.split("@", 1)[0] if email else "Minha instituicao"

    cfg = Config(
        tenant_id=tenant_id,
        company_name=display_name,
        description=(
            f"Configure aqui as informacoes oficiais de {display_name} "
            "para orientar as respostas do agente."
        ),
        tone_of_voice=DEFAULT_TONE,
        totem_voice_gender=DEFAULT_VOICE,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


# FAQs

def get_faqs(db: Session, tenant_id: str) -> list[Faq]:
    return (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id)
        .order_by(desc(Faq.created_at))
        .all()
    )


def get_totem_faqs(db: Session, tenant_id: str) -> list[Faq]:
    return (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id, Faq.show_on_totem == True)
        .order_by(desc(Faq.created_at))
        .limit(4)
        .all()
    )


def create_faq(db: Session, payload: FaqCreate, tenant_id: str) -> Faq:
    faq = Faq(
        tenant_id=tenant_id,
        question=payload.question,
        answer=payload.answer,
        show_on_totem=payload.show_on_totem,
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def update_faq(db: Session, faq_id: str, payload: FaqUpdate, tenant_id: str) -> Optional[Faq]:
    faq = db.query(Faq).filter(Faq.id == faq_id, Faq.tenant_id == tenant_id).first()
    if not faq:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    faq.updated_at = utc_now()
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def toggle_faq_totem(db: Session, faq_id: str, tenant_id: str) -> Faq | str | None:
    faq = db.query(Faq).filter(Faq.id == faq_id, Faq.tenant_id == tenant_id).first()
    if not faq:
        return None

    if not faq.show_on_totem:
        active_count = (
            db.query(Faq)
            .filter(Faq.tenant_id == tenant_id, Faq.show_on_totem == True)
            .count()
        )
        if active_count >= 4:
            return "limit_exceeded"

    faq.show_on_totem = not faq.show_on_totem
    faq.updated_at = utc_now()
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def delete_faq(db: Session, faq_id: str, tenant_id: str) -> bool:
    faq = db.query(Faq).filter(Faq.id == faq_id, Faq.tenant_id == tenant_id).first()
    if not faq:
        return False
    db.delete(faq)
    db.commit()
    get_cached_faq_answers.cache_clear()
    return True


@lru_cache(maxsize=128)
def get_cached_faq_answers(tenant_id: str) -> tuple[tuple[str, str, str], ...]:
    from .database import SessionLocal

    db = SessionLocal()
    try:
        rows = (
            db.query(Faq)
            .filter(Faq.tenant_id == tenant_id)
            .order_by(desc(Faq.total_consults), desc(Faq.created_at))
            .limit(10)
            .all()
        )
        return tuple((row.id, row.question, row.answer) for row in rows)
    finally:
        db.close()


def find_cached_faq_answer(question: str, tenant_id: str) -> Optional[tuple[str, str]]:
    normalized = question.strip().lower()
    if len(normalized) < 4:
        return None
    for faq_id, faq_question, faq_answer in get_cached_faq_answers(tenant_id):
        fq = faq_question.strip().lower()
        if normalized == fq or normalized in fq or fq in normalized:
            return faq_id, faq_answer
    return None


def increment_faq_consult(db: Session, faq_id: str, tenant_id: str) -> None:
    faq = db.query(Faq).filter(Faq.id == faq_id, Faq.tenant_id == tenant_id).first()
    if not faq:
        return
    faq.total_consults = (faq.total_consults or 0) + 1
    db.commit()
    get_cached_faq_answers.cache_clear()


# Events

def get_events(db: Session, tenant_id: str) -> list[CompanyEvent]:
    return (
        db.query(CompanyEvent)
        .filter(CompanyEvent.tenant_id == tenant_id)
        .order_by(desc(CompanyEvent.event_date))
        .all()
    )


def create_event(db: Session, payload: EventCreate, tenant_id: str) -> CompanyEvent:
    event = CompanyEvent(
        tenant_id=tenant_id,
        title=payload.title,
        event_date=payload.event_date,
        event_type=payload.event_type,
        description=payload.description,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(
    db: Session,
    event_id: str,
    payload: EventUpdate,
    tenant_id: str,
) -> Optional[CompanyEvent]:
    event = (
        db.query(CompanyEvent)
        .filter(CompanyEvent.id == event_id, CompanyEvent.tenant_id == tenant_id)
        .first()
    )
    if not event:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    event.updated_at = utc_now()
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: str, tenant_id: str) -> bool:
    event = (
        db.query(CompanyEvent)
        .filter(CompanyEvent.id == event_id, CompanyEvent.tenant_id == tenant_id)
        .first()
    )
    if not event:
        return False
    db.delete(event)
    db.commit()
    return True


# Config

def get_config(db: Session, tenant_id: str) -> Optional[Config]:
    return db.query(Config).filter(Config.tenant_id == tenant_id).first()


def upsert_config(db: Session, payload: ConfigUpdate, tenant_id: str) -> Config:
    cfg = get_config(db, tenant_id)
    if not cfg:
        cfg = Config(tenant_id=tenant_id)
        db.add(cfg)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    cfg.updated_at = utc_now()
    db.commit()
    db.refresh(cfg)
    return cfg


# Interactions

def save_interaction(db: Session, question: str, answer: str, tenant_id: str) -> Interaction:
    not_answered_markers = (
        "nao tenho informacoes",
        "nao tenho informações",
        "não tenho informações",
    )
    answer_text = (answer or "").lower()
    was_answered = bool(answer) and not any(m in answer_text for m in not_answered_markers)
    interaction = Interaction(
        tenant_id=tenant_id,
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


# Unanswered questions

def get_unanswered_questions(db: Session, tenant_id: str) -> list[dict]:
    rows = (
        db.query(UnansweredQuestion)
        .filter(
            UnansweredQuestion.tenant_id == tenant_id,
            UnansweredQuestion.converted == False,
        )
        .order_by(desc(UnansweredQuestion.count))
        .all()
    )
    return [
        {
            "id": row.id,
            "canonical_question": row.canonical_question,
            "count": row.count,
            "first_asked": row.first_asked,
            "last_asked": row.last_asked,
            "similar_questions": json.loads(row.similar_questions or "[]"),
        }
        for row in rows
    ]


def delete_unanswered_question(db: Session, question_id: str, tenant_id: str) -> bool:
    uq = (
        db.query(UnansweredQuestion)
        .filter(UnansweredQuestion.id == question_id, UnansweredQuestion.tenant_id == tenant_id)
        .first()
    )
    if not uq:
        return False
    db.delete(uq)
    db.commit()
    return True


def convert_unanswered_to_faq(
    db: Session,
    question_id: str,
    answer: str,
    question: Optional[str],
    tenant_id: str,
) -> Optional[Faq]:
    uq = (
        db.query(UnansweredQuestion)
        .filter(UnansweredQuestion.id == question_id, UnansweredQuestion.tenant_id == tenant_id)
        .first()
    )
    if not uq:
        return None

    faq = Faq(
        tenant_id=tenant_id,
        question=(question or uq.canonical_question).strip(),
        answer=answer,
        show_on_totem=False,
    )
    db.add(faq)
    uq.converted = True
    db.commit()
    db.refresh(faq)
    get_cached_faq_answers.cache_clear()
    return faq


def save_feedback(
    db: Session,
    question: str,
    answer: str,
    helpful: bool,
    tenant_id: str,
) -> Interaction:
    interaction = Interaction(
        tenant_id=tenant_id,
        question=question,
        answer=answer,
        was_answered=True,
        feedback_helpful=helpful,
    )
    db.add(interaction)
    db.commit()
    return interaction


# Dashboard

def get_dashboard_stats(db: Session, tenant_id: str) -> dict:
    total = db.query(Interaction).filter(Interaction.tenant_id == tenant_id).count()
    unanswered_count = (
        db.query(UnansweredQuestion)
        .filter(
            UnansweredQuestion.tenant_id == tenant_id,
            UnansweredQuestion.converted == False,
        )
        .count()
    )

    today = utc_now().date()
    daily = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        count = (
            db.query(Interaction)
            .filter(
                Interaction.tenant_id == tenant_id,
                Interaction.asked_at.between(day_start, day_end),
            )
            .count()
        )
        daily.append({"date": day.strftime("%d/%m"), "count": count})

    faqs = (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id)
        .order_by(desc(Faq.total_consults), desc(Faq.created_at))
        .limit(5)
        .all()
    )
    top_faqs = []
    for faq in faqs:
        hits = faq.total_consults or 0
        if hits == 0:
            hits = (
                db.query(Interaction)
                .filter(
                    Interaction.tenant_id == tenant_id,
                    func.lower(Interaction.question).contains(faq.question[:30].lower()),
                )
                .count()
            )
        top_faqs.append({"question": faq.question[:50], "count": hits or 0})

    top_faqs.sort(key=lambda x: x["count"], reverse=True)

    feedback_total = (
        db.query(Interaction)
        .filter(Interaction.tenant_id == tenant_id, Interaction.feedback_helpful.isnot(None))
        .count()
    )
    feedback_positive = (
        db.query(Interaction)
        .filter(Interaction.tenant_id == tenant_id, Interaction.feedback_helpful == True)
        .count()
    )
    satisfaction_rate = round((feedback_positive / feedback_total) * 100, 1) if feedback_total else 0.0

    return {
        "total_questions": total,
        "unanswered_questions": unanswered_count,
        "avg_response_time": latency_store.summary()["avg_response_time"],
        "satisfaction_rate": satisfaction_rate,
        "daily_interactions": daily,
        "top_faqs": top_faqs[:5],
    }
