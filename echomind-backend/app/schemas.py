"""
schemas.py – Contratos de entrada/saída da API (Pydantic v2)
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator


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

EVENT_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
EVENT_TYPES = {"palestra", "feriado", "promocao", "workshop", "reuniao", "evento_social", "outro"}


def sao_paulo_today() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def validate_event_date(value: str, field_name: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} deve ser uma data real no formato YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} deve estar no formato YYYY-MM-DD.")
    return value


def validate_event_period(
    event_date: str,
    event_end_date: str,
    *,
    today: date | None = None,
) -> None:
    start = date.fromisoformat(validate_event_date(event_date, "event_date"))
    end = date.fromisoformat(validate_event_date(event_end_date, "event_end_date"))
    if end < start:
        raise ValueError("event_end_date deve ser igual ou posterior a event_date.")
    if end < (today or sao_paulo_today()):
        raise ValueError("event_end_date não pode estar no passado.")


def validate_external_url(
    value: Optional[str],
    *,
    field_name: str,
    allowed_schemes: set[str],
) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} deve ser uma URL válida.")
    if not value.strip():
        return None
    if len(value) > 2000:
        raise ValueError(f"{field_name} deve ter no máximo 2000 caracteres.")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{field_name} não pode conter espaços ou caracteres de controle.")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ValueError(f"{field_name} deve ser uma URL válida.") from exc
    if parsed.scheme.lower() not in allowed_schemes or not hostname:
        schemes = " ou ".join(sorted(allowed_schemes))
        raise ValueError(f"{field_name} deve usar {schemes} e possuir um host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} não pode conter credenciais.")
    return value


def normalize_event_course(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 2:
        raise ValueError("course deve ter pelo menos 2 caracteres.")
    if len(normalized) > 200:
        raise ValueError("course deve ter no máximo 200 caracteres.")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ValueError("course não pode conter caracteres de controle.")
    return normalized


class EventCourseCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_event_course(value)


class EventCourseResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}

class EventCreate(BaseModel):
    title: str         = Field(..., min_length=3, max_length=300)
    event_date: str    = Field(..., pattern=EVENT_DATE_PATTERN, examples=["2026-12-31"])
    event_end_date: Optional[str] = Field(None, pattern=EVENT_DATE_PATTERN)
    event_type: str    = Field(..., examples=["palestra"])
    course: str = Field(default="Geral", min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    location: str = Field(default="Local a definir", min_length=2, max_length=300)
    image_url: Optional[str] = Field(None, max_length=2000)
    link_url: Optional[str] = Field(None, max_length=2000)

    @field_validator("event_date", "event_end_date")
    @classmethod
    def validate_dates(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        return validate_event_date(value, info.field_name)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"Tipo inválido. Permitidos: {EVENT_TYPES}")
        return v

    @field_validator("course")
    @classmethod
    def validate_course(cls, value: str) -> str:
        return normalize_event_course(value)

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_external_url(value, field_name="image_url", allowed_schemes={"https"})

    @field_validator("link_url", mode="before")
    @classmethod
    def validate_link_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_external_url(value, field_name="link_url", allowed_schemes={"http", "https"})

    @model_validator(mode="after")
    def validate_period(self) -> "EventCreate":
        self.event_end_date = self.event_end_date or self.event_date
        validate_event_period(self.event_date, self.event_end_date)
        return self


class EventUpdate(BaseModel):
    title: Optional[str]       = Field(None, min_length=3, max_length=300)
    event_date: Optional[str]  = Field(None, pattern=EVENT_DATE_PATTERN)
    event_end_date: Optional[str] = Field(None, pattern=EVENT_DATE_PATTERN)
    event_type: Optional[str]  = None
    course: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, min_length=2, max_length=300)
    image_url: Optional[str] = Field(None, max_length=2000)
    link_url: Optional[str] = Field(None, max_length=2000)

    @field_validator("event_date", "event_end_date")
    @classmethod
    def validate_dates(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return None
        return validate_event_date(value, info.field_name)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in EVENT_TYPES:
            raise ValueError(f"Tipo inválido. Permitidos: {EVENT_TYPES}")
        return v

    @field_validator("course")
    @classmethod
    def validate_course(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_event_course(value)

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_external_url(value, field_name="image_url", allowed_schemes={"https"})

    @field_validator("link_url", mode="before")
    @classmethod
    def validate_link_url(cls, value: Optional[str]) -> Optional[str]:
        return validate_external_url(value, field_name="link_url", allowed_schemes={"http", "https"})


class EventResponse(BaseModel):
    id: str
    title: str
    event_date: str
    event_end_date: str
    event_type: str
    course: str
    description: Optional[str]
    location: str
    image_url: Optional[str]
    link_url: Optional[str]
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
    event_end_date: str
    event_type: str
    course: str
    description: Optional[str]
    location: str
    image_url: Optional[str]
    link_url: Optional[str]

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
    triage_status: Literal["pending", "review", "ignored"]
    triage_reason: Optional[str] = None

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


class DocumentUploadLimitsResponse(BaseModel):
    max_document_size_bytes: int = Field(gt=0)
