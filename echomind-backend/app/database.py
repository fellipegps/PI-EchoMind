"""
database.py – Conexão SQLAlchemy + pgvector
Modelos ORM para todas as entidades do EchoMind.
"""

import os
import uuid
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Boolean, Text,
    DateTime, Integer, Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

# ─── Conexão ─────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://echomind:echomind@localhost:5432/echomind",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))  # 768 = paraphrase-multilingual-mpnet-base-v2


# ─── Dependency ──────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  MODELOS ORM
# ══════════════════════════════════════════════════════════════════════════════

def new_uuid() -> str:
    return str(uuid.uuid4())


class Faq(Base):
    """Perguntas frequentes com resposta oficial."""
    __tablename__ = "faqs"

    id           = Column(String, primary_key=True, default=new_uuid)
    question     = Column(Text, nullable=False)
    answer       = Column(Text, nullable=False)
    show_on_totem = Column(Boolean, default=False, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanyEvent(Base):
    """Eventos e datas institucionais."""
    __tablename__ = "events"

    id          = Column(String, primary_key=True, default=new_uuid)
    title       = Column(Text, nullable=False)
    event_date  = Column(String, nullable=False)   # formato: YYYY-MM-DD
    event_type  = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Config(Base):
    """Configurações da instituição (singleton – um registro por instalação)."""
    __tablename__ = "config"

    id              = Column(String, primary_key=True, default=new_uuid)
    company_name    = Column(String, nullable=False, default="EchoMind Institution")
    description     = Column(Text, nullable=True)
    tone_of_voice   = Column(String, default="profissional e cordial")
    totem_voice_gender = Column(String, default="feminina")
    website         = Column(String, nullable=True)
    phone           = Column(String, nullable=True)
    address         = Column(Text, nullable=True)
    business_hours  = Column(String, nullable=True)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Interaction(Base):
    """
    Histórico completo de interações – base para o Dashboard e
    para detectar perguntas não respondidas.
    """
    __tablename__ = "interactions"

    id          = Column(String, primary_key=True, default=new_uuid)
    question    = Column(Text, nullable=False)
    answer      = Column(Text, nullable=True)
    was_answered = Column(Boolean, default=True, nullable=False)
    asked_at    = Column(DateTime, default=datetime.utcnow, nullable=False)


class UnansweredQuestion(Base):
    """
    Agregação de perguntas que a IA não conseguiu responder
    com base suficiente (baixo score de similaridade no retriever).
    """
    __tablename__ = "unanswered_questions"

    id                  = Column(String, primary_key=True, default=new_uuid)
    canonical_question  = Column(Text, nullable=False)   # versão "representativa"
    count               = Column(Integer, default=1, nullable=False)
    first_asked         = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_asked          = Column(DateTime, default=datetime.utcnow, nullable=False)
    # variações detectadas (JSON list serializado como texto)
    similar_questions   = Column(Text, default="[]")     # JSON array de strings
    converted           = Column(Boolean, default=False) # True após virar FAQ


class KnowledgeDocument(Base):
    """
    Vetor de embedding para cada chunk de conhecimento indexado.
    Fonte pode ser: 'faq' | 'event' | 'config'
    """
    __tablename__ = "knowledge_documents"

    id          = Column(String, primary_key=True, default=new_uuid)
    source_id   = Column(String, nullable=False, index=True)   # ID do registro original
    source_type = Column(String, nullable=False)               # faq | event | config
    content     = Column(Text, nullable=False)                 # texto indexado
    embedding   = Column(Vector(EMBEDDING_DIM), nullable=True) # vetor pgvector
    created_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "ix_knowledge_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
