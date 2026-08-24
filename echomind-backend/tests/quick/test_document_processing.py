"""Testes unitarios do servico interno de processamento documental."""

from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def processing_modules(quick_test_context):
    from app import document_ingestion, document_processing, document_repository

    return SimpleNamespace(
        ingestion=document_ingestion,
        processing=document_processing,
        repository=document_repository,
    )


class TrackingSessionFactory:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.close_spies: list[MagicMock] = []

    def __call__(self):
        session = self.session_factory()
        close_spy = MagicMock(wraps=session.close)
        session.close = close_spy
        self.close_spies.append(close_spy)
        return session


@pytest.fixture()
def processing_context(quick_test_context, processing_modules, monkeypatch):
    """Fornece banco isolado para exercitar commits e rollbacks internos."""
    from app.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    sessions = TrackingSessionFactory(session_factory)
    monkeypatch.setattr(processing_modules.processing, "SessionLocal", sessions)
    try:
        yield SimpleNamespace(session_factory=session_factory, sessions=sessions)
    finally:
        engine.dispose()


class FakeRagIndexer:
    def __init__(self, *, fail_index: bool = False, fail_delete_once: bool = False):
        self.fail_index = fail_index
        self.fail_delete_once = fail_delete_once
        self.reindexed: list[tuple] = []
        self.deleted: list[tuple] = []

    def reindex_document_chunks(self, document, chunks, *, previous_chunks):
        self.reindexed.append((document, tuple(chunks), tuple(previous_chunks)))
        if self.fail_index:
            raise RuntimeError("vector stack trace secreto")

    def delete_document_chunks(self, document, chunks):
        self.deleted.append((document, tuple(chunks)))
        if self.fail_delete_once:
            self.fail_delete_once = False
            raise RuntimeError("pgvector temporariamente indisponivel")


def _create_pending_document(
    processing_context,
    repository,
    *,
    tenant_id: str = "tenant-a",
    mime_type: str = "text/plain",
) -> str:
    filename = {
        "text/plain": "norma.txt",
        "application/pdf": "norma.pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "norma.docx",
    }[mime_type]
    digest = sha256(f"{tenant_id}:{mime_type}:{uuid4()}".encode()).hexdigest()
    session = processing_context.session_factory()
    try:
        document = repository.create_document(
            session,
            tenant_id=tenant_id,
            data=repository.DocumentCreateData(
                filename=filename,
                mime_type=mime_type,
                size_bytes=32,
                sha256=digest,
            ),
        )
        document_id = document.id
        session.commit()
        return document_id
    finally:
        session.close()


def _stored_state(processing_context, repository, tenant_id: str, document_id: str):
    session = processing_context.session_factory()
    try:
        document = repository.get_document(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        chunks = repository.list_document_chunks(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        return SimpleNamespace(
            status=document.status,
            chunk_count=document.chunk_count,
            processed_at=document.processed_at,
            error_message=document.error_message,
            chunks=[
                SimpleNamespace(
                    id=chunk.id,
                    tenant_id=chunk.tenant_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                )
                for chunk in chunks
            ],
        )
    finally:
        session.close()


def _successful_boundaries(monkeypatch, modules, mime_type: str, fake_rag):
    extracted = modules.ingestion.ExtractedDocument(
        blocks=(modules.ingestion.ExtractedTextBlock(text="Texto institucional."),)
    )
    extractor = MagicMock(return_value=extracted)
    monkeypatch.setitem(modules.processing._EXTRACTORS, mime_type, extractor)
    monkeypatch.setattr(
        modules.processing,
        "chunk_document",
        MagicMock(
            return_value=(
                modules.ingestion.ChunkedTextBlock(
                    chunk_index=0,
                    content="Primeiro chunk.",
                    page_start=1,
                    page_end=1,
                ),
                modules.ingestion.ChunkedTextBlock(
                    chunk_index=1,
                    content="Segundo chunk.",
                    section_title="Secao sintetica",
                ),
            )
        ),
    )
    monkeypatch.setattr(
        modules.processing,
        "get_rag_indexer",
        lambda db, tenant_id: fake_rag,
    )
    return extractor


@pytest.mark.parametrize(
    "mime_type",
    [
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
    ],
    ids=["txt", "docx", "pdf"],
)
def test_process_document_success_for_each_format_and_closes_session(
    processing_context,
    monkeypatch,
    processing_modules,
    mime_type,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(
        processing_context,
        repository,
        mime_type=mime_type,
    )
    sessions = processing_context.sessions
    fake_rag = FakeRagIndexer()
    extractor = _successful_boundaries(monkeypatch, processing_modules, mime_type, fake_rag)
    transitions: list[str] = []
    real_transition = processing.transition_document_status

    def tracked_transition(*args, **kwargs):
        target = kwargs["target_status"]
        transitions.append(target.value if hasattr(target, "value") else target)
        return real_transition(*args, **kwargs)

    monkeypatch.setattr(processing, "transition_document_status", tracked_transition)

    result = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"bytes duraveis",
    )

    stored = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert result.status == "ready"
    assert result.chunk_count == 2
    assert transitions == ["processing", "ready"]
    assert stored.status == "ready"
    assert stored.chunk_count == 2
    assert stored.processed_at is not None
    assert stored.error_message is None
    assert [chunk.content for chunk in stored.chunks] == ["Primeiro chunk.", "Segundo chunk."]
    assert len(fake_rag.reindexed) == 1
    extractor.assert_called_once_with(b"bytes duraveis")
    assert all(spy.call_count == 1 for spy in sessions.close_spies)


def test_parser_failure_persists_short_error_without_traceback(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    sessions = processing_context.sessions
    monkeypatch.setitem(
        processing._EXTRACTORS,
        "text/plain",
        MagicMock(side_effect=RuntimeError("Traceback: segredo interno")),
    )
    fake_rag = FakeRagIndexer()
    monkeypatch.setattr(processing, "get_rag_indexer", lambda db, tenant_id: fake_rag)

    result = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo",
    )

    stored = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert result.status == "error"
    assert stored.error_message == "Falha ao extrair o documento."
    assert "Traceback" not in stored.error_message
    assert stored.chunks == []
    assert all(spy.call_count == 1 for spy in sessions.close_spies)


def test_persistence_failure_rolls_back_partial_chunks_and_marks_error(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    fake_rag = FakeRagIndexer()
    _successful_boundaries(monkeypatch, processing_modules, "text/plain", fake_rag)
    real_replace = processing.replace_document_chunks
    failed_once = False

    def fail_after_flush(*args, **kwargs):
        nonlocal failed_once
        persisted = real_replace(*args, **kwargs)
        if kwargs["chunks"] and not failed_once:
            failed_once = True
            raise RuntimeError("falha sintetica de persistencia")
        return persisted

    monkeypatch.setattr(processing, "replace_document_chunks", fail_after_flush)

    result = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo",
    )

    stored = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert result.status == "error"
    assert stored.error_message == "Falha ao persistir os chunks."
    assert stored.chunk_count == 0
    assert stored.chunks == []
    assert fake_rag.reindexed == []


def test_index_failure_cleans_persisted_chunks_and_partial_vectors(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    fake_rag = FakeRagIndexer(fail_index=True)
    _successful_boundaries(monkeypatch, processing_modules, "text/plain", fake_rag)

    result = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo",
    )

    stored = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert result.status == "error"
    assert stored.error_message == "Falha ao indexar os chunks."
    assert stored.chunk_count == 0
    assert stored.chunks == []
    assert len(fake_rag.deleted) == 1
    assert all(chunk.tenant_id == "tenant-a" for chunk in fake_rag.deleted[0][1])
    assert all(chunk.document_id == document_id for chunk in fake_rag.deleted[0][1])


def test_failed_vector_cleanup_is_retried_idempotently_on_error_record(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    fake_rag = FakeRagIndexer(fail_index=True, fail_delete_once=True)
    _successful_boundaries(monkeypatch, processing_modules, "text/plain", fake_rag)

    first = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo",
    )
    partial = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert first.status == "error"
    assert partial.chunk_count == 2

    second = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo ignorado no retry de cleanup",
    )
    cleaned = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert second.status == "error"
    assert cleaned.chunk_count == 0
    assert cleaned.chunks == []
    assert len(fake_rag.deleted) == 2


def test_wrong_tenant_is_rejected_and_session_is_closed(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    sessions = processing_context.sessions

    with pytest.raises(repository.DocumentNotFoundError):
        processing.process_document(
            document_id=document_id,
            tenant_id="tenant-b",
            content=b"conteudo",
        )

    assert len(sessions.close_spies) == 1
    sessions.close_spies[0].assert_called_once_with()
    stored = _stored_state(processing_context, repository, "tenant-a", document_id)
    assert stored.status == "pending"


def test_ready_document_reexecution_is_a_noop(
    processing_context,
    monkeypatch,
    processing_modules,
) -> None:
    processing = processing_modules.processing
    repository = processing_modules.repository
    document_id = _create_pending_document(processing_context, repository)
    setup_session = processing_context.session_factory()
    try:
        repository.transition_document_status(
            setup_session,
            tenant_id="tenant-a",
            document_id=document_id,
            target_status="processing",
        )
        repository.transition_document_status(
            setup_session,
            tenant_id="tenant-a",
            document_id=document_id,
            target_status="ready",
        )
        setup_session.commit()
    finally:
        setup_session.close()

    sessions = processing_context.sessions
    extractor = MagicMock(side_effect=AssertionError("extrator nao deve ser chamado"))
    monkeypatch.setitem(processing._EXTRACTORS, "text/plain", extractor)
    rag_factory = MagicMock(side_effect=AssertionError("RAG nao deve ser criado"))
    monkeypatch.setattr(processing, "get_rag_indexer", rag_factory)

    result = processing.process_document(
        document_id=document_id,
        tenant_id="tenant-a",
        content=b"conteudo ignorado",
    )

    assert result.status == "ready"
    extractor.assert_not_called()
    rag_factory.assert_not_called()
    sessions.close_spies[0].assert_called_once_with()
