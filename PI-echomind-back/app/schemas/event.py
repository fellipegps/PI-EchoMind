from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class EventBase(BaseModel):
    title: str
    description: str | None = None
    event_date: datetime
    event_type: str = "outro"


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    event_date: datetime | None = None
    event_type: str | None = None


class EventResponse(EventBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)