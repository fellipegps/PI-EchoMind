"""
schemas.py – Contratos de entrada/saída da API (Pydantic v2)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["Onde fica a secretaria?"])
    session_id: Optional[str] = Field(None, description="Identificador de sessão (para histórico futuro)")


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


# ══════════════════════════════════════════════════════════════════════════════
#  FAQ
# ══════════════════════════════════════════════════════════════════════════════

class FaqCreate(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    answer: str   = Field(..., min_length=5, max_length=4000)
    show_on_totem: bool = False


class FaqUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=5, max_length=500)
    answer: Optional[str]   = Field(None, min_length=5, max_length=4000)
    show_on_totem: Optional[bool] = None


class FaqResponse(BaseModel):
    id: str
    question: str
    answer: str
    show_on_totem: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════════════

class EventCreate(BaseModel):
    title: str         = Field(..., min_length=3, max_length=300)
    event_date: str    = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2025-12-31"])
    event_type: str    = Field(..., examples=["palestra"])
    description: Optional[str] = Field(None, max_length=2000)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        allowed = {"palestra", "feriado", "promocao", "workshop", "reuniao", "evento_social", "outro"}
        if v not in allowed:
            raise ValueError(f"Tipo inválido. Permitidos: {allowed}")
        return v


class EventUpdate(BaseModel):
    title: Optional[str]       = Field(None, min_length=3, max_length=300)
    event_date: Optional[str]  = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    event_type: Optional[str]  = None
    description: Optional[str] = Field(None, max_length=2000)


class EventResponse(BaseModel):
    id: str
    title: str
    event_date: str
    event_type: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

class ConfigUpdate(BaseModel):
    company_name: Optional[str]       = Field(None, min_length=2, max_length=200)
    description: Optional[str]        = Field(None, max_length=5000)
    tone_of_voice: Optional[str]      = None
    totem_voice_gender: Optional[str] = None
    website: Optional[str]            = Field(None, max_length=500)
    phone: Optional[str]              = Field(None, max_length=30)
    address: Optional[str]            = Field(None, max_length=500)
    business_hours: Optional[str]     = Field(None, max_length=200)


class ConfigResponse(BaseModel):
    id: str
    company_name: str
    description: Optional[str]
    tone_of_voice: str
    totem_voice_gender: str
    website: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    business_hours: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  PERGUNTAS NÃO RESPONDIDAS
# ══════════════════════════════════════════════════════════════════════════════

class UnansweredQuestionResponse(BaseModel):
    id: str
    canonical_question: str
    count: int
    first_asked: datetime
    last_asked: datetime
    similar_questions: list[str] = []

    model_config = {"from_attributes": True}


class ConvertToFaqRequest(BaseModel):
    answer: str = Field(..., min_length=5, max_length=4000)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class DailyInteraction(BaseModel):
    date: str
    count: int


class TopFaq(BaseModel):
    question: str
    count: int


class DashboardResponse(BaseModel):
    total_questions: int
    unanswered_questions: int
    avg_response_time: str
    daily_interactions: list[DailyInteraction]
    top_faqs: list[TopFaq]
