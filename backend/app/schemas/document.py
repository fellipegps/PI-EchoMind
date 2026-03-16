from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    model_config = ConfigDict(from_attributes=True)

class DocumentChunkResponse(BaseModel):
    id: UUID
    content: str
    document_id: UUID
    model_config = ConfigDict(from_attributes=True)
    