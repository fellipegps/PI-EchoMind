from pydantic import BaseModel, ConfigDict
from uuid import UUID

class UnansweredResponse(BaseModel):
    id: UUID
    question: str
    resolved: bool
    model_config = ConfigDict(from_attributes=True)
    