import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text)
    response_time = Column(Float) # Em segundos (ex: 1.2)
    created_at = Column(DateTime, default=datetime.utcnow)