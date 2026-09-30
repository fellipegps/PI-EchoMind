"""
schemas.py – Contratos de entrada/saída da API (Pydantic v2)
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["Onde fica a secretaria?"])
    tenant_id: str = Field(..., min_length=1)


class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["Onde fica a secretaria?"])

    model_config = {"extra": "forbid"}



# ══════════════════════════════════════════════════════════════════════════════
#  FAQ
# ══════════════════════════════════════════════════════════════════════════════

class FaqCreate(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    answer: str   = Field(..., min_length=5, max_length=4000)
    show_in_chatbot: bool = False


class FaqUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=5, max_length=500)
    answer: Optional[str]   = Field(None, min_length=5, max_length=4000)
    show_in_chatbot: Optional[bool] = None


class FaqResponse(BaseModel):
    id: str
    question: str
    answer: str
    show_in_chatbot: bool
    total_consults: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicFaqResponse(BaseModel):
    id: str
    question: str
    answer: str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════════════

class EventCreate(BaseModel):
    title: str         = Field(..., min_length=3, max_length=300)
    event_date: str    = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2025-12-31"])
    event_type: str    = Field(..., examples=["palestra"])
    description: Optional[str] = Field(None, max_length=2000)
    location: str = Field(default="Local a definir", min_length=2, max_length=300)
    published: bool = False

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
    location: Optional[str] = Field(None, min_length=2, max_length=300)
    published: Optional[bool] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"palestra", "feriado", "promocao", "workshop", "reuniao", "evento_social", "outro"}
        if v not in allowed:
            raise ValueError(f"Tipo inválido. Permitidos: {allowed}")
        return v


class EventResponse(BaseModel):
    id: str
    title: str
    event_date: str
    event_type: str
    description: Optional[str]
    location: str
    published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  LOCAIS DO CAMPUS
# ══════════════════════════════════════════════════════════════════════════════

class CampusLocationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: str = Field(default="outro", min_length=2, max_length=100)
    floor: Optional[str] = Field(None, max_length=50)
    building: Optional[str] = Field(None, max_length=100)
    x: float = Field(..., ge=0, le=100)
    y: float = Field(..., ge=0, le=100)
    active: bool = True

    @field_validator("name", "category")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("O campo deve ter pelo menos 2 caracteres.")
        return normalized

    @field_validator("description", "floor", "building")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None

    model_config = {"extra": "forbid"}


class CampusLocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    floor: Optional[str] = Field(None, max_length=50)
    building: Optional[str] = Field(None, max_length=100)
    x: Optional[float] = Field(None, ge=0, le=100)
    y: Optional[float] = Field(None, ge=0, le=100)
    active: Optional[bool] = None

    @field_validator("name", "category")
    @classmethod
    def normalize_required_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("O campo deve ter pelo menos 2 caracteres.")
        return normalized

    @field_validator("description", "floor", "building")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None

    model_config = {"extra": "forbid"}


class CampusLocationResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    floor: Optional[str]
    building: Optional[str]
    x: float
    y: float
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublicCampusLocationResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    floor: Optional[str]
    building: Optional[str]
    x: float
    y: float

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

class ConfigUpdate(BaseModel):
    company_name: Optional[str]       = Field(None, min_length=2, max_length=200)
    description: Optional[str]        = Field(None, max_length=5000)
    tone_of_voice: Optional[str]      = None
    chat_voice_gender: Optional[str] = None
    website: Optional[str]            = Field(None, max_length=500)
    phone: Optional[str]              = Field(None, max_length=30)
    address: Optional[str]            = Field(None, max_length=500)
    business_hours: Optional[str]     = Field(None, max_length=200)


class ConfigResponse(BaseModel):
    id: str
    public_slug: str
    company_name: str
    description: Optional[str]
    tone_of_voice: str
    chat_voice_gender: str
    website: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    business_hours: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PublicEventResponse(BaseModel):
    id: str
    title: str
    event_date: str
    event_type: str
    description: Optional[str]
    location: str

    model_config = {"from_attributes": True}


class PublicInstitutionResponse(BaseModel):
    public_slug: str
    company_name: str
    description: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    business_hours: Optional[str]

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
    similar_questions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConvertToFaqRequest(BaseModel):
    answer: str = Field(..., min_length=5, max_length=4000)
    question: Optional[str] = Field(None, min_length=5, max_length=500)


class FeedbackRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=8000)
    helpful: bool
    tenant_id: str = Field(..., min_length=1)


class FeedbackResponse(BaseModel):
    saved: bool
    helpful: bool


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
    satisfaction_rate: float
    daily_interactions: list[DailyInteraction]
    top_faqs: list[TopFaq]


class RagOperationMetrics(BaseModel):
    total: int
    success: int
    error: int
    average_latency_ms: float


class RagSourceTypeMetrics(BaseModel):
    faq: int
    event: int
    document_chunk: int
    document_parent: int
    other: int


class RagDailyMetrics(BaseModel):
    date: date
    queries: int
    failures: int
    unanswered: int


class RagMetricsResponse(BaseModel):
    period_days: int
    start_date: date
    end_date: date
    has_data: bool
    query_count: int
    query_error_count: int
    failure_count: int
    average_retrieved_results: float
    unanswered_rate: float
    retrieval: RagOperationMetrics
    ingestion: RagOperationMetrics
    source_types: RagSourceTypeMetrics
    daily: list[RagDailyMetrics]


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

class CurrentUserResponse(BaseModel):
    """Dados publicos do usuario autenticado pelo Supabase Auth."""
    id: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENTOS
# ══════════════════════════════════════════════════════════════════════════════

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class DocumentResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    chunk_count: int
    document_type: Optional[str]
    document_number: Optional[str]
    department: Optional[str]
    published_at: Optional[date]
    valid_until: Optional[date]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
