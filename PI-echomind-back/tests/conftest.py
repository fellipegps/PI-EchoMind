"""
tests/conftest.py – Fixtures compartilhadas para todos os testes.

Estratégia de isolamento:
  • Banco: SQLite em memória (sem precisar de Postgres nem pgvector)
  • Ollama (LLM + Embeddings): mocados com unittest.mock
  • RAGEngine: substituído por um FakeRAGEngine controlável nos testes de chat
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

# ─── Patch pgvector ANTES de qualquer import do app ──────────────────────────
# SQLite não tem Vector — substituímos por Text para os testes
import sqlalchemy.types as types


class FakeVector(types.TypeDecorator):
    """Substituto do pgvector.sqlalchemy.Vector para testes com SQLite."""
    impl = types.Text
    cache_ok = True

    def __init__(self, dim=768):
        super().__init__()
        self.dim = dim

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


# Injeta o fake antes do import dos modelos
import pgvector.sqlalchemy as pgvec_module
pgvec_module.Vector = FakeVector

# Agora importa o app (já com o patch aplicado)
from app.database import Base, get_db
from app.main import app

# ─── Engine SQLite em memória ─────────────────────────────────────────────────

SQLITE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)

# SQLite não suporta HNSW — remove o índice antes de criar as tabelas
@event.listens_for(Base.metadata, "before_create")
def remove_hnsw_index(target, connection, **kwargs):
    for table in target.tables.values():
        indexes_to_remove = [
            idx for idx in table.indexes
            if "hnsw" in idx.name.lower()
        ]
        for idx in indexes_to_remove:
            table.indexes.discard(idx)


Base.metadata.create_all(bind=test_engine)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Sessão de banco isolada por teste (rollback ao final)."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP do FastAPI com injeção da sessão de teste
    e RAGEngine mocado (sem Ollama real).
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock do RAGEngine para não precisar do Ollama
    with patch("app.main.get_rag_engine") as mock_engine_factory:
        fake_engine = FakeRAGEngine()
        mock_engine_factory.return_value = fake_engine
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


# ─── Fake RAGEngine ───────────────────────────────────────────────────────────

class FakeRAGEngine:
    """
    Substituto controlável do RAGEngine para testes unitários.
    Permite testar cenários de:
      - resposta normal
      - sem contexto (pergunta não respondida)
      - erro de conexão
    """

    def __init__(self, has_context: bool = True, error: bool = False):
        self.has_context = has_context
        self.error = error
        self.indexed_faqs: list = []
        self.indexed_events: list = []
        self.deleted: list = []

    async def astream_chat(self, question: str) -> AsyncGenerator[str, None]:
        if self.error:
            raise ConnectionError("Ollama unavailable")

        if not self.has_context:
            response = (
                "Não tenho informações suficientes para responder a isso. "
                "Por favor, consulte nossa instituição diretamente."
            )
        else:
            response = f"Resposta simulada para: {question}"

        for token in response.split():
            yield token + " "

    def index_faq(self, faq):
        self.indexed_faqs.append(faq.id)

    def reindex_faq(self, faq):
        self.index_faq(faq)

    def index_event(self, event):
        self.indexed_events.append(event.id)

    def reindex_event(self, event):
        self.index_event(event)

    def delete_document(self, source_id: str, source: str):
        self.deleted.append((source_id, source))


# ─── Helpers para criar fixtures de dados ─────────────────────────────────────

@pytest.fixture()
def sample_faq_data() -> dict:
    return {
        "question": "Como faço minha matrícula?",
        "answer": "Compareça à secretaria com seus documentos.",
        "show_on_totem": False,
    }


@pytest.fixture()
def sample_event_data() -> dict:
    return {
        "title": "Semana Acadêmica",
        "event_date": "2025-08-20",
        "event_type": "palestra",
        "description": "Palestras e workshops para alunos.",
    }


@pytest.fixture()
def sample_config_data() -> dict:
    return {
        "company_name": "UniEVANGÉLICA",
        "description": "Instituição de ensino superior.",
        "tone_of_voice": "profissional e cordial",
        "totem_voice_gender": "feminina",
        "website": "https://www.unievangelica.edu.br",
        "phone": "(62) 3310-6600",
        "address": "Av. Universitária Km 3,5 - Anápolis, GO",
        "business_hours": "Seg-Sex 7h30-22h",
    }
