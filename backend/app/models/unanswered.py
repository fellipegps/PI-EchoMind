import uuid
from sqlalchemy import Column, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class UnansweredQuestion(Base):
    __tablename__ = "unanswered_questions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    embedding = Column(Vector(768))
    resolved = Column(Boolean, default=False)
    