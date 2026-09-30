"""
crud.py - Operacoes de banco com isolamento por tenant.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .database import (
    CampusLocation,
    CompanyEvent,
    Config,
    Faq,
    Interaction,
    UnansweredQuestion,
    utc_now,
)
from .middleware import latency_store
from .schemas import (
    CampusLocationCreate,
    CampusLocationUpdate,
    ConfigUpdate,
    EventCreate,
    EventUpdate,
    FaqCreate,
    FaqUpdate,
)


DEFAULT_TONE = "profissional e cordial"
DEFAULT_VOICE = "feminina"
FAQ_CACHE_MATCH_THRESHOLD = 1.0
PUBLIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def build_public_slug(company_name: str, tenant_id: str) -> str:
    """Cria um slug legivel, estavel e sem expor o identificador interno."""
    normalized = unicodedata.normalize("NFKD", company_name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    base = (base or "instituicao")[:83].rstrip("-")
    tenant_hash = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:16]
    return f"{base}-{tenant_hash}"


def is_valid_public_slug(public_slug: str) -> bool:
    return (
        3 <= len(public_slug) <= 100
        and PUBLIC_SLUG_PATTERN.fullmatch(public_slug) is not None
    )


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
    vazios para nao exibir conteudo ficticio no chatbot publico de uma empresa nova.
    """
    existing = get_config(db, tenant_id)
    if existing:
        if not existing.public_slug:
            existing.public_slug = build_public_slug(existing.company_name, tenant_id)
            existing.updated_at = utc_now()
            db.commit()
            db.refresh(existing)
        return existing

    display_name = (company_name or "").strip()
    if not display_name:
        display_name = email.split("@", 1)[0] if email else "Minha instituicao"

    cfg = Config(
        tenant_id=tenant_id,
        public_slug=build_public_slug(display_name, tenant_id),
        company_name=display_name,
        description=(
            f"Configure aqui as informacoes oficiais de {display_name} "
            "para orientar as respostas do agente."
        ),
        tone_of_voice=DEFAULT_TONE,
        chat_voice_gender=DEFAULT_VOICE,
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


def get_chatbot_faqs(db: Session, tenant_id: str) -> list[Faq]:
    return (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id, Faq.show_in_chatbot == True)
        .order_by(desc(Faq.created_at))
        .limit(4)
        .all()
    )


def create_faq(db: Session, payload: FaqCreate, tenant_id: str) -> Faq:
    faq = Faq(
        tenant_id=tenant_id,
        question=payload.question,
        answer=payload.answer,
        show_in_chatbot=payload.show_in_chatbot,
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


def toggle_faq_chatbot(db: Session, faq_id: str, tenant_id: str) -> Faq | str | None:
    faq = db.query(Faq).filter(Faq.id == faq_id, Faq.tenant_id == tenant_id).first()
    if not faq:
        return None

    if not faq.show_in_chatbot:
        active_count = (
            db.query(Faq)
            .filter(Faq.tenant_id == tenant_id, Faq.show_in_chatbot == True)
            .count()
        )
        if active_count >= 4:
            return "limit_exceeded"

    faq.show_in_chatbot = not faq.show_in_chatbot
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


def normalize_faq_cache_question(question: str) -> str:
    """Normaliza apenas variacoes ortograficas seguras para o cache de FAQ."""
    decomposed = unicodedata.normalize("NFKD", question.casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    alphanumeric_words = "".join(
        char if char.isalnum() else " " for char in without_accents
    )
    return " ".join(alphanumeric_words.split())


def faq_cache_match_score(question: str, faq_question: str) -> float:
    """Retorna confianca binaria; cache exige igualdade normalizada completa."""
    normalized_question = normalize_faq_cache_question(question)
    normalized_faq = normalize_faq_cache_question(faq_question)
    if not normalized_question or normalized_question != normalized_faq:
        return 0.0
    return 1.0


def find_cached_faq_answer(question: str, tenant_id: str) -> Optional[tuple[str, str]]:
    matched: Optional[tuple[str, str]] = None
    for faq_id, faq_question, faq_answer in get_cached_faq_answers(tenant_id):
        if faq_cache_match_score(question, faq_question) >= FAQ_CACHE_MATCH_THRESHOLD:
            if matched is not None:
                return None
            matched = (faq_id, faq_answer)
    return matched


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


def get_public_events(
    db: Session,
    tenant_id: str,
    *,
    today: date | None = None,
) -> list[CompanyEvent]:
    """Lista somente eventos publicáveis do tenant, sem datas já encerradas."""
    current_date = (today or date.today()).isoformat()
    return (
        db.query(CompanyEvent)
        .filter(
            CompanyEvent.tenant_id == tenant_id,
            CompanyEvent.published.is_(True),
            CompanyEvent.event_date >= current_date,
        )
        .order_by(CompanyEvent.event_date.asc(), CompanyEvent.id.asc())
        .all()
    )


def create_event(db: Session, payload: EventCreate, tenant_id: str) -> CompanyEvent:
    event = CompanyEvent(
        tenant_id=tenant_id,
        title=payload.title,
        event_date=payload.event_date,
        event_type=payload.event_type,
        description=payload.description,
        location=payload.location,
        published=payload.published,
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


# Locais do campus

class CampusLocationNameConflictError(ValueError):
    pass


def get_campus_locations(db: Session, tenant_id: str) -> list[CampusLocation]:
    return (
        db.query(CampusLocation)
        .filter(CampusLocation.tenant_id == tenant_id)
        .order_by(CampusLocation.name.asc(), CampusLocation.id.asc())
        .all()
    )


def get_public_campus_locations(
    db: Session,
    tenant_id: str,
) -> list[CampusLocation]:
    return (
        db.query(CampusLocation)
        .filter(
            CampusLocation.tenant_id == tenant_id,
            CampusLocation.active.is_(True),
        )
        .order_by(CampusLocation.name.asc(), CampusLocation.id.asc())
        .all()
    )


def _campus_location_name_exists(
    db: Session,
    *,
    tenant_id: str,
    name: str,
    exclude_id: str | None = None,
) -> bool:
    query = db.query(CampusLocation.id).filter(
        CampusLocation.tenant_id == tenant_id,
        func.lower(CampusLocation.name) == name.strip().lower(),
    )
    if exclude_id is not None:
        query = query.filter(CampusLocation.id != exclude_id)
    return query.first() is not None


def create_campus_location(
    db: Session,
    payload: CampusLocationCreate,
    tenant_id: str,
) -> CampusLocation:
    if _campus_location_name_exists(
        db,
        tenant_id=tenant_id,
        name=payload.name,
    ):
        raise CampusLocationNameConflictError
    location = CampusLocation(
        tenant_id=tenant_id,
        **payload.model_dump(),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def update_campus_location(
    db: Session,
    location_id: str,
    payload: CampusLocationUpdate,
    tenant_id: str,
) -> Optional[CampusLocation]:
    location = (
        db.query(CampusLocation)
        .filter(
            CampusLocation.id == location_id,
            CampusLocation.tenant_id == tenant_id,
        )
        .first()
    )
    if location is None:
        return None
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and _campus_location_name_exists(
        db,
        tenant_id=tenant_id,
        name=changes["name"],
        exclude_id=location.id,
    ):
        raise CampusLocationNameConflictError
    for field, value in changes.items():
        setattr(location, field, value)
    location.updated_at = utc_now()
    db.commit()
    db.refresh(location)
    return location


def delete_campus_location(
    db: Session,
    location_id: str,
    tenant_id: str,
) -> bool:
    location = (
        db.query(CampusLocation)
        .filter(
            CampusLocation.id == location_id,
            CampusLocation.tenant_id == tenant_id,
        )
        .first()
    )
    if location is None:
        return False
    db.delete(location)
    db.commit()
    return True


# Config

def get_config(db: Session, tenant_id: str) -> Optional[Config]:
    return db.query(Config).filter(Config.tenant_id == tenant_id).first()


def get_config_by_public_slug(db: Session, public_slug: str) -> Optional[Config]:
    if not is_valid_public_slug(public_slug):
        return None
    return db.query(Config).filter(Config.public_slug == public_slug).first()


def upsert_config(db: Session, payload: ConfigUpdate, tenant_id: str) -> Config:
    cfg = get_config(db, tenant_id)
    if not cfg:
        company_name = payload.company_name or "EchoMind Institution"
        cfg = Config(
            tenant_id=tenant_id,
            public_slug=build_public_slug(company_name, tenant_id),
        )
        db.add(cfg)
    elif not cfg.public_slug:
        cfg.public_slug = build_public_slug(cfg.company_name, tenant_id)

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
        show_in_chatbot=False,
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
