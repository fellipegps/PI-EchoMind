"""
database.py – Conexão SQLAlchemy + pgvector
Modelos ORM para todas as entidades do EchoMind.
"""

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Boolean, Text,
    CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv

# ─── Conexão ─────────────────────────────────────────────────────────────────

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. Defina no .env com a connection string do Supabase."
    )

if DATABASE_URL.startswith("postgresql") and "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require" if "?" not in DATABASE_URL else "&sslmode=require"

engine_options = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    engine_options.update(pool_size=10, max_overflow=20)

engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    tenant_id    = Column(String, nullable=False, index=True)
    question     = Column(Text, nullable=False)
    answer       = Column(Text, nullable=False)
    show_on_totem = Column(Boolean, default=False, nullable=False)
    total_consults = Column(Integer, default=0, nullable=False)
    positive_feedback = Column(Integer, default=0, nullable=False)
    negative_feedback = Column(Integer, default=0, nullable=False)
    created_at   = Column(DateTime, default=utc_now, nullable=False)
    updated_at   = Column(DateTime, default=utc_now, onupdate=utc_now)


class CompanyEvent(Base):
    """Eventos e datas institucionais."""
    __tablename__ = "events"

    id          = Column(String, primary_key=True, default=new_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    title       = Column(Text, nullable=False)
    event_date  = Column(String, nullable=False)   # formato: YYYY-MM-DD
    event_type  = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=utc_now, nullable=False)
    updated_at  = Column(DateTime, default=utc_now, onupdate=utc_now)


class Config(Base):
    """Configurações da instituição (singleton – um registro por instalação)."""
    __tablename__ = "config"

    id              = Column(String, primary_key=True, default=new_uuid)
    tenant_id       = Column(String, nullable=False, index=True)
    company_name    = Column(String, nullable=False, default="EchoMind Institution")
    description     = Column(Text, nullable=True)
    tone_of_voice   = Column(String, default="profissional e cordial")
    totem_voice_gender = Column(String, default="feminina")
    website         = Column(String, nullable=True)
    phone           = Column(String, nullable=True)
    address         = Column(Text, nullable=True)
    business_hours  = Column(String, nullable=True)
    updated_at      = Column(DateTime, default=utc_now, onupdate=utc_now)


class Interaction(Base):
    """
    Histórico completo de interações – base para o Dashboard e
    para detectar perguntas não respondidas.
    """
    __tablename__ = "interactions"

    id          = Column(String, primary_key=True, default=new_uuid)
    tenant_id   = Column(String, nullable=False, index=True)
    question    = Column(Text, nullable=False)
    answer      = Column(Text, nullable=True)
    was_answered = Column(Boolean, default=True, nullable=False)
    feedback_helpful = Column(Boolean, nullable=True)
    asked_at    = Column(DateTime, default=utc_now, nullable=False)


class UnansweredQuestion(Base):
    """
    Agregação de perguntas que a IA não conseguiu responder
    com base suficiente (baixo score de similaridade no retriever).
    """
    __tablename__ = "unanswered_questions"

    id                  = Column(String, primary_key=True, default=new_uuid)
    tenant_id           = Column(String, nullable=False, index=True)
    canonical_question  = Column(Text, nullable=False)   # versão "representativa"
    count               = Column(Integer, default=1, nullable=False)
    first_asked         = Column(DateTime, default=utc_now, nullable=False)
    last_asked          = Column(DateTime, default=utc_now, nullable=False)
    # variações detectadas (JSON list serializado como texto)
    similar_questions   = Column(Text, default="[]")     # JSON array de strings
    converted           = Column(Boolean, default=False) # True após virar FAQ


class Document(Base):
    """Estado e metadados auditaveis de um documento por tenant."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'error')",
            name="ck_documents_status",
        ),
        CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
        CheckConstraint("length(sha256) = 64", name="ck_documents_sha256_length"),
        CheckConstraint("chunk_count >= 0", name="ck_documents_chunk_count_nonnegative"),
        Index("ix_documents_tenant_status", "tenant_id", "status"),
        Index("ix_documents_tenant_sha256", "tenant_id", "sha256"),
        Index("ix_documents_tenant_created_at", "tenant_id", "created_at"),
    )

    id              = Column(String, primary_key=True, default=new_uuid)
    tenant_id       = Column(String, nullable=False, index=True)
    filename        = Column(String, nullable=False)
    mime_type       = Column(String, nullable=False)
    size_bytes      = Column(Integer, nullable=False)
    sha256          = Column(String, nullable=False)
    status          = Column(String, default="pending", nullable=False)
    chunk_count     = Column(Integer, default=0, nullable=False)
    document_type   = Column(String, nullable=True)
    document_number = Column(String, nullable=True)
    department      = Column(String, nullable=True)
    published_at    = Column(Date, nullable=True)
    valid_until     = Column(Date, nullable=True)
    error_message   = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=utc_now, nullable=False)
    updated_at      = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    processed_at    = Column(DateTime, nullable=True)

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )
    chunk_parents = relationship(
        "DocumentChunkParent",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunkParent.parent_index",
    )


class DocumentChunkParent(Base):
    """Contexto maior persistido; seus children continuam sendo os vetores."""

    __tablename__ = "document_chunk_parents"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "parent_index",
            name="uq_document_chunk_parents_document_id_parent_index",
        ),
        CheckConstraint(
            "parent_index >= 0",
            name="ck_document_chunk_parents_parent_index_nonnegative",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_start > 0",
            name="ck_document_chunk_parents_page_start_positive",
        ),
        CheckConstraint(
            "page_end IS NULL OR page_end > 0",
            name="ck_document_chunk_parents_page_end_positive",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_end >= page_start",
            name="ck_document_chunk_parents_page_range",
        ),
        Index("ix_document_chunk_parents_tenant_document", "tenant_id", "document_id"),
    )

    id            = Column(String, primary_key=True)
    tenant_id     = Column(String, nullable=False, index=True)
    document_id   = Column(
        String,
        ForeignKey(
            "documents.id",
            name="fk_document_chunk_parents_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    parent_index  = Column(Integer, nullable=False)
    content       = Column(Text, nullable=False)
    page_start    = Column(Integer, nullable=True)
    page_end      = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    created_at    = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="chunk_parents")
    children = relationship("DocumentChunk", back_populates="parent")


class DocumentChunk(Base):
    """Trecho textual ordenado e rastreavel de um documento."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_id_chunk_index",
        ),
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_document_chunks_chunk_index_nonnegative",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_start > 0",
            name="ck_document_chunks_page_start_positive",
        ),
        CheckConstraint(
            "page_end IS NULL OR page_end > 0",
            name="ck_document_chunks_page_end_positive",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_end >= page_start",
            name="ck_document_chunks_page_range",
        ),
    )

    id            = Column(String, primary_key=True, default=new_uuid)
    tenant_id     = Column(String, nullable=False, index=True)
    document_id   = Column(
        String,
        ForeignKey(
            "documents.id",
            name="fk_document_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    parent_id     = Column(
        String,
        ForeignKey(
            "document_chunk_parents.id",
            name="fk_document_chunks_parent_id_document_chunk_parents",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    chunk_index   = Column(Integer, nullable=False)
    content       = Column(Text, nullable=False)
    page_start    = Column(Integer, nullable=True)
    page_end      = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    created_at    = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="chunks")
    parent = relationship("DocumentChunkParent", back_populates="children")

