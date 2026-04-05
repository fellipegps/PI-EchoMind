import uuid
from datetime import datetime
from sqlalchemy import Column, Text, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class faq(Base):
    __tablename__ = "faqs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    # Mudamos para nullable=True para que perguntas sem resposta apareçam no painel
    answer = Column(Text, nullable=True) 
    category = Column(String, default="Geral")
    # Contador para o gráfico de "FAQs Mais Consultadas" do seu print
    total_consults = Column(Integer, default=0)
    embedding = Column(Vector(768))
    created_at = Column(DateTime, default=datetime.utcnow)

FAQ = faq