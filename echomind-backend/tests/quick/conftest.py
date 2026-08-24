"""
tests/quick/conftest.py – Fixtures exclusivas dos testes rapidos.

Estratégia de isolamento:
  • Banco: SQLite em memória (sem precisar de Postgres nem pgvector)
  • Ollama (LLM + Embeddings): mocados com unittest.mock
  • RAGEngine: substituído por um FakeRAGEngine controlável nos testes de chat
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

# SQLite não tem Vector — substituímos por Text somente ao executar a suite rapida.
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


SQLITE_URL = "sqlite:///:memory:"


@dataclass
class QuickTestContext:
    app: Any
    current_user_type: Any
    get_current_user: Any
    get_db: Any
    engine: Engine
    session_factory: Any


@pytest.fixture(scope="session")
def quick_test_context() -> Generator[QuickTestContext, None, None]:
    """Inicializa SQLite/FakeVector apenas quando um teste rapido e selecionado."""
    os.environ.setdefault("DATABASE_URL", SQLITE_URL)
    os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
    os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")

    import pgvector.sqlalchemy as pgvec_module

    original_vector = pgvec_module.Vector
    pgvec_module.Vector = FakeVector

    from app.auth import CurrentUser, get_current_user
    from app.database import Base, get_db
    from app.main import app

    test_engine = create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    def remove_hnsw_index(target, connection, **kwargs):
        for table in target.tables.values():
            indexes_to_remove = [
                idx for idx in table.indexes
                if "hnsw" in idx.name.lower()
            ]
            for idx in indexes_to_remove:
                table.indexes.discard(idx)

    event.listen(Base.metadata, "before_create", remove_hnsw_index)
    Base.metadata.create_all(bind=test_engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    try:
        yield QuickTestContext(
            app=app,
            current_user_type=CurrentUser,
            get_current_user=get_current_user,
            get_db=get_db,
            engine=test_engine,
            session_factory=testing_session_local,
        )
    finally:
        event.remove(Base.metadata, "before_create", remove_hnsw_index)
        test_engine.dispose()
        pgvec_module.Vector = original_vector


@pytest.fixture()
def db(quick_test_context: QuickTestContext) -> Generator[Session, None, None]:
    """Sessão de banco isolada por teste (rollback ao final)."""
    connection = quick_test_context.engine.connect()
    transaction = connection.begin()
    session = quick_test_context.session_factory(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(
    db: Session,
    quick_test_context: QuickTestContext,
) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP do FastAPI com injeção da sessão de teste
    e RAGEngine mocado (sem Ollama real).
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app = quick_test_context.app
    app.dependency_overrides[quick_test_context.get_db] = override_get_db
    app.dependency_overrides[quick_test_context.get_current_user] = lambda: (
        quick_test_context.current_user_type(
            id="test-admin",
            email="admin@test.local",
            is_active=True,
            created_at=datetime.utcnow(),
            company_name="Empresa Teste",
        )
    )

    # Mock do RAGEngine para não precisar do Ollama
    with (
        patch("app.main.get_rag_engine") as mock_engine_factory,
        patch("app.crud.find_cached_faq_answer", return_value=None),
    ):
        fake_engine = FakeRAGEngine()
        mock_engine_factory.return_value = fake_engine
        with TestClient(app) as c:
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
        self.last_had_docs = has_context
        self.error = error
        self.indexed_faqs: list = []
        self.indexed_events: list = []
        self.deleted: list = []

    async def astream_chat(self, question: str) -> AsyncGenerator[str, None]:
        self.last_had_docs = self.has_context
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
