from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class FAQBase(BaseModel):
    question: str
    answer: str
    category: str = "Geral"


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None


class FAQResponse(FAQBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FAQAskRequest(BaseModel):
    question: str


class FAQAskResponse(BaseModel):
    answer: str
    source: str  # "faq" ou "unanswered"
