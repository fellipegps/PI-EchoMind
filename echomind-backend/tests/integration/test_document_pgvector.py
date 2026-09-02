"""Ciclo documental no PGVector real com embeddings locais deterministicos."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


def _document(document_id: str, tenant_id: str, filename: str):
    return SimpleNamespace(
        id=document_id,
        tenant_id=tenant_id,
        filename=filename,
        mime_type="application/pdf",
        document_type="regulamento",
        document_number="42/2026",
        department="Secretaria Academica",
        published_at=date(2026, 2, 1),
        valid_until=date(2027, 2, 1),
    )


def _chunk(chunk_id: str, document_id: str, tenant_id: str, index: int, content: str):
    return SimpleNamespace(
        id=chunk_id,
        tenant_id=tenant_id,
        document_id=document_id,
        chunk_index=index,
        content=content,
        page_start=index + 1,
        page_end=index + 1,
        section_title=f"Secao {index + 1}",
    )


@pytest.fixture()
def real_rag_runtime(
    monkeypatch,
    integration_database_url,
    deterministic_fake_embeddings,
):
    from app import rag_engine

    monkeypatch.setattr(rag_engine, "DATABASE_URL", integration_database_url)
    monkeypatch.setattr(
        rag_engine,
        "_get_embeddings",
        lambda: deterministic_fake_embeddings,
    )
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()
    tenant_ids: set[str] = set()

    def make_indexer(tenant_id: str):
        tenant_ids.add(tenant_id)
        indexer = object.__new__(rag_engine.RAGEngine)
        indexer.tenant_id = tenant_id
        return indexer

    yield SimpleNamespace(module=rag_engine, make_indexer=make_indexer)

    for tenant_id in tenant_ids:
        rag_engine._get_vector_store(tenant_id).delete_collection()
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()


def _documents_for(runtime, tenant_id: str):
    store = runtime.module._get_vector_store(tenant_id)
    return store.similarity_search("consulta sintetica", k=20)


def _create_pending_processing_document(tenant_id: str) -> str:
    from app.database import SessionLocal
    from app.document_repository import DocumentCreateData, create_document

    session = SessionLocal()
    try:
        document = create_document(
            session,
            tenant_id=tenant_id,
            data=DocumentCreateData(
                filename="norma.txt",
                mime_type="text/plain",
                size_bytes=128,
                sha256=sha256(f"{tenant_id}:{uuid4()}".encode()).hexdigest(),
            ),
        )
        document_id = document.id
        session.commit()
        return document_id
    finally:
        session.close()


def _processing_state(tenant_id: str, document_id: str):
    from app.database import SessionLocal
    from app.document_repository import get_document, list_document_chunks

    session = SessionLocal()
    try:
        document = get_document(session, tenant_id=tenant_id, document_id=document_id)
        chunks = list_document_chunks(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        return SimpleNamespace(
            status=document.status,
            chunk_count=document.chunk_count,
            processed_at=document.processed_at,
            error_message=document.error_message,
            chunk_contents=[chunk.content for chunk in chunks],
        )
    finally:
        session.close()


def _remove_processing_document(tenant_id: str, document_id: str) -> None:
    from app.database import SessionLocal
    from app.document_repository import delete_document

    session = SessionLocal()
    try:
        delete_document(session, tenant_id=tenant_id, document_id=document_id)
        session.commit()
    finally:
        session.close()


def _create_ready_document_with_vector(runtime, tenant_id: str) -> str:
    from app.database import SessionLocal
    from app.document_repository import (
        DocumentChunkData,
        DocumentCreateData,
        create_document,
        replace_document_chunks,
        transition_document_status,
    )

    session = SessionLocal()
    try:
        document = create_document(
            session,
            tenant_id=tenant_id,
            data=DocumentCreateData(
                filename="api-delete.txt",
                mime_type="text/plain",
                size_bytes=96,
                sha256=sha256(f"{tenant_id}:{uuid4()}".encode()).hexdigest(),
            ),
        )
        transition_document_status(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="processing",
        )
        document = transition_document_status(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="ready",
        )
        chunks = replace_document_chunks(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            chunks=(DocumentChunkData(content="Chunk sintetico da API."),),
        )
        session.commit()
        runtime.make_indexer(tenant_id).index_document_chunk(document, chunks[0])
        return document.id
    finally:
        session.close()


def test_real_pgvector_index_and_reindex_are_idempotent_and_remove_orphans(
    real_rag_runtime,
) -> None:
    tenant_id = "pr12-idempotency"
    indexer = real_rag_runtime.make_indexer(tenant_id)
    document = _document("doc-1", tenant_id, "regulamento.pdf")
    chunk_zero = _chunk("chunk-0", document.id, tenant_id, 0, "Conteudo inicial.")
    orphan = _chunk("chunk-1", document.id, tenant_id, 1, "Conteudo orfao.")

    indexer.index_document_chunk(document, chunk_zero)
    indexer.index_document_chunk(document, chunk_zero)
    assert len(_documents_for(real_rag_runtime, tenant_id)) == 1

    indexer.index_document_chunk(document, orphan)
    updated = _chunk("chunk-0", document.id, tenant_id, 0, "Conteudo atualizado.")
    indexer.reindex_document_chunks(
        document,
        (updated,),
        previous_chunks=(chunk_zero, orphan),
    )

    stored = _documents_for(real_rag_runtime, tenant_id)
    assert len(stored) == 1
    assert stored[0].page_content.endswith("Conteudo atualizado.")
    assert stored[0].metadata["source_type"] == "document_chunk"
    assert stored[0].metadata["source_id"] == "chunk-0"
    assert stored[0].metadata["tenant_id"] == tenant_id
    assert stored[0].metadata["document_id"] == document.id
    assert stored[0].metadata["filename"] == "regulamento.pdf"
    assert stored[0].metadata["page_start"] == 1
    assert stored[0].metadata["page_end"] == 1
    assert stored[0].metadata["chunk_index"] == 0
    assert stored[0].metadata["published_at"] == "2026-02-01"


def test_real_pgvector_deletion_is_scoped_by_document_and_tenant(
    real_rag_runtime,
) -> None:
    tenant_a = "pr12-tenant-a"
    tenant_b = "pr12-tenant-b"
    indexer_a = real_rag_runtime.make_indexer(tenant_a)
    indexer_b = real_rag_runtime.make_indexer(tenant_b)
    document_a = _document("doc-a", tenant_a, "tenant-a.pdf")
    document_a_other = _document("doc-a-other", tenant_a, "outro-a.pdf")
    document_b = _document("doc-b", tenant_b, "tenant-b.pdf")
    chunk_a = _chunk("shared-chunk", document_a.id, tenant_a, 0, "Somente tenant A.")
    chunk_a_second = _chunk("chunk-a-second", document_a.id, tenant_a, 1, "Segundo chunk A.")
    chunk_a_other = _chunk("chunk-a-other", document_a_other.id, tenant_a, 0, "Outro doc A.")
    chunk_b = _chunk("shared-chunk", document_b.id, tenant_b, 0, "Somente tenant B.")

    indexer_a.index_document_chunk(document_a, chunk_a)
    indexer_a.index_document_chunk(document_a, chunk_a_second)
    indexer_a.index_document_chunk(document_a_other, chunk_a_other)
    indexer_b.index_document_chunk(document_b, chunk_b)

    assert {doc.metadata["tenant_id"] for doc in _documents_for(real_rag_runtime, tenant_b)} == {
        tenant_b
    }
    indexer_a.delete_document_chunks(document_a, (chunk_a, chunk_a_second))

    remaining_a = _documents_for(real_rag_runtime, tenant_a)
    remaining_b = _documents_for(real_rag_runtime, tenant_b)
    assert [doc.metadata["document_id"] for doc in remaining_a] == [document_a_other.id]
    assert [doc.metadata["document_id"] for doc in remaining_b] == [document_b.id]


def test_real_pgvector_keeps_faq_and_event_retrievable(real_rag_runtime) -> None:
    tenant_id = "pr12-regression"
    indexer = real_rag_runtime.make_indexer(tenant_id)
    faq = SimpleNamespace(id="faq-1", question="Qual o prazo?", answer="Trinta dias.")
    event = SimpleNamespace(
        id="event-1",
        title="Semana academica",
        event_date="2026-09-03",
        event_type="palestra",
        description="Evento sintetico.",
    )

    indexer.index_faq(faq)
    indexer.index_event(event)

    stored = _documents_for(real_rag_runtime, tenant_id)
    assert {doc.metadata["source_type"] for doc in stored} == {"faq", "event"}
    assert {doc.metadata["source_id"] for doc in stored} == {"faq-1", "event-1"}


def test_real_postgresql_parent_lookup_is_tenant_scoped_deduplicated_and_cascades() -> None:
    from langchain_core.documents import Document as RetrievedDocument

    from app.database import DocumentChunkParent, SessionLocal
    from app.document_repository import (
        DocumentChunkData,
        DocumentCreateData,
        DocumentParentData,
        create_document,
        delete_document,
        replace_document_chunks,
        transition_document_status,
    )
    from app.rag_engine import _expand_document_parents

    today = date(2026, 9, 1)
    created: list[tuple[str, str]] = []
    candidates: list[RetrievedDocument] = []
    session = SessionLocal()
    try:
        for tenant_id in ("parent-real-a", "parent-real-b"):
            document = create_document(
                session,
                tenant_id=tenant_id,
                data=DocumentCreateData(
                    filename=f"{tenant_id}.txt",
                    mime_type="text/plain",
                    size_bytes=128,
                    sha256=sha256(f"{tenant_id}:{uuid4()}".encode()).hexdigest(),
                    valid_until=today,
                ),
            )
            transition_document_status(
                session,
                tenant_id=tenant_id,
                document_id=document.id,
                target_status="processing",
            )
            chunks = replace_document_chunks(
                session,
                tenant_id=tenant_id,
                document_id=document.id,
                parents=(
                    DocumentParentData(
                        content=f"Regra completa e excecao do {tenant_id}.",
                        page_start=1,
                        page_end=2,
                    ),
                ),
                chunks=(
                    DocumentChunkData(content="Regra precisa.", page_start=1, parent_index=0),
                    DocumentChunkData(content="Excecao complementar.", page_start=2, parent_index=0),
                ),
            )
            transition_document_status(
                session,
                tenant_id=tenant_id,
                document_id=document.id,
                target_status="ready",
            )
            created.append((tenant_id, document.id))
            candidates.extend(
                RetrievedDocument(
                    page_content=chunk.content,
                    metadata={
                        "source_id": chunk.id,
                        "source_type": "document_chunk",
                        "tenant_id": tenant_id,
                        "document_id": document.id,
                        "parent_id": chunk.parent_id,
                        "valid_until": today.isoformat(),
                    },
                )
                for chunk in chunks
            )
        session.commit()
    finally:
        session.close()

    expanded = _expand_document_parents(
        candidates,
        tenant_id="parent-real-a",
        today=today,
    )
    assert len(expanded) == 1
    assert expanded[0].metadata["tenant_id"] == "parent-real-a"
    assert "Regra completa e excecao do parent-real-a" in expanded[0].page_content

    session = SessionLocal()
    try:
        for tenant_id, document_id in created:
            assert delete_document(session, tenant_id=tenant_id, document_id=document_id)
        session.commit()
        assert (
            session.query(DocumentChunkParent)
            .filter(DocumentChunkParent.tenant_id.in_([tenant for tenant, _ in created]))
            .count()
            == 0
        )
    finally:
        session.close()


@pytest.mark.asyncio
async def test_real_postgresql_hybrid_search_is_lexical_tenant_scoped_and_validity_aware(
    real_rag_runtime,
) -> None:
    """Exercita FTS real, fusão híbrida, tenant e validade documental."""
    from app.database import CompanyEvent, Document as StoredDocument, DocumentChunk, Faq, SessionLocal

    tenant_a, tenant_b = "hybrid-a", "hybrid-b"
    document_id, chunk_id = "hybrid-doc-a", "hybrid-chunk-a"
    session = SessionLocal()
    try:
        faq = Faq(id="hybrid-faq-a", tenant_id=tenant_a, question="Qual é a sigla NAI?", answer="NAI é o Núcleo de Acessibilidade Institucional.")
        event = CompanyEvent(id="hybrid-event-a", tenant_id=tenant_a, title="Semana SIGLAFEST", event_date="2026-09-14", event_type="institucional", description="Evento sintético.")
        document = StoredDocument(id=document_id, tenant_id=tenant_a, filename="edital-xyz.pdf", mime_type="application/pdf", size_bytes=128, sha256="a" * 64, status="ready", chunk_count=1, document_number="EDITALXYZ2026")
        chunk = DocumentChunk(id=chunk_id, tenant_id=tenant_a, document_id=document_id, chunk_index=0, content="O código EDITALXYZ2026 prevê inscrição até 14 de setembro.")
        expired_document = StoredDocument(id="hybrid-doc-expired", tenant_id=tenant_a, filename="expirado.pdf", mime_type="application/pdf", size_bytes=128, sha256="b" * 64, status="ready", chunk_count=1, valid_until=date(2026, 8, 23))
        expired_chunk = DocumentChunk(id="hybrid-chunk-expired", tenant_id=tenant_a, document_id=expired_document.id, chunk_index=0, content="O código EXPIRADOXYZ nunca deve ser retornado.")
        foreign_faq = Faq(id="hybrid-faq-b", tenant_id=tenant_b, question="EDITALXYZ2026 do tenant B", answer="Conteúdo exclusivo do tenant B.")
        session.add_all((faq, event, document, chunk, expired_document, expired_chunk, foreign_faq))
        session.commit()

        indexer = real_rag_runtime.make_indexer(tenant_a)
        indexer.index_faq(faq)  # a rota vetorial continua ativa

        lexical_code = real_rag_runtime.module._search_lexical_documents("EDITALXYZ2026", tenant_a, today=date(2026, 8, 24), limit=10)
        assert ("document_chunk", chunk_id) in {(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in lexical_code}
        assert all(doc.metadata["tenant_id"] == tenant_a for doc in lexical_code)
        assert ("faq", faq.id) in {(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in real_rag_runtime.module._search_lexical_documents("NAI", tenant_a, today=date(2026, 8, 24), limit=10)}
        assert ("event", event.id) in {(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in real_rag_runtime.module._search_lexical_documents("SIGLAFEST", tenant_a, today=date(2026, 8, 24), limit=10)}
        assert real_rag_runtime.module._search_lexical_documents("EXPIRADOXYZ", tenant_a, today=date(2026, 8, 24), limit=10) == []

        hybrid, _distance = await real_rag_runtime.module._retrieve_docs("EDITALXYZ2026", tenant_a, today=date(2026, 8, 24))
        assert ("document_chunk", chunk_id) in {(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in hybrid}
    finally:
        session.query(DocumentChunk).filter(DocumentChunk.id.in_((chunk_id, "hybrid-chunk-expired"))).delete(synchronize_session=False)
        session.query(StoredDocument).filter(StoredDocument.id.in_((document_id, "hybrid-doc-expired"))).delete(synchronize_session=False)
        session.query(Faq).filter(Faq.id.in_(("hybrid-faq-a", "hybrid-faq-b"))).delete(synchronize_session=False)
        session.query(CompanyEvent).filter(CompanyEvent.id == "hybrid-event-a").delete(synchronize_session=False)
        session.commit()
        session.close()


@pytest.mark.asyncio
async def test_real_pgvector_retrieval_excludes_expired_chunks_and_keeps_tenant(
    real_rag_runtime,
) -> None:
    query = "regra sintetica de validade"
    tenant_a = "pr17-validity-a"
    tenant_b = "pr17-validity-b"
    indexer_a = real_rag_runtime.make_indexer(tenant_a)
    indexer_b = real_rag_runtime.make_indexer(tenant_b)

    indexer_a._upsert_document(
        source_id="expired-a",
        source_type="document_chunk",
        content=query,
        extra_metadata={"valid_until": "2026-08-23"},
    )
    indexer_a._upsert_document(
        source_id="current-a",
        source_type="document_chunk",
        content=query,
        extra_metadata={"valid_until": "2026-08-24"},
    )
    indexer_a._upsert_document(
        source_id="faq-a",
        source_type="faq",
        content=query,
        extra_metadata={"valid_until": "2020-01-01"},
    )
    indexer_b._upsert_document(
        source_id="current-b",
        source_type="document_chunk",
        content=query,
        extra_metadata={"valid_until": "2027-01-01"},
    )

    docs_a, distance_a = await real_rag_runtime.module._retrieve_docs(
        query,
        tenant_a,
        today=date(2026, 8, 24),
    )
    docs_b, distance_b = await real_rag_runtime.module._retrieve_docs(
        query,
        tenant_b,
        today=date(2026, 8, 24),
    )

    assert {doc.metadata["source_id"] for doc in docs_a} == {"current-a", "faq-a"}
    assert {doc.metadata["tenant_id"] for doc in docs_a} == {tenant_a}
    assert [doc.metadata["source_id"] for doc in docs_b] == ["current-b"]
    assert [doc.metadata["tenant_id"] for doc in docs_b] == [tenant_b]
    assert distance_a == pytest.approx(0.0, abs=1e-6)
    assert distance_b == pytest.approx(0.0, abs=1e-6)


def test_manual_reindex_rebuilds_ready_sources_idempotently_per_tenant(
    real_rag_runtime,
) -> None:
    from app.database import CompanyEvent, Document, Faq, SessionLocal
    from app.document_repository import (
        DocumentChunkData,
        DocumentCreateData,
        create_document,
        replace_document_chunks,
        transition_document_status,
    )
    from scripts import reindex_all as reindex_script

    tenant_a = "pr18-reindex-a"
    tenant_b = "pr18-reindex-b"
    real_rag_runtime.make_indexer(tenant_a)
    indexer_b = real_rag_runtime.make_indexer(tenant_b)
    session = SessionLocal()
    try:
        faq = Faq(
            id="pr18-faq-a",
            tenant_id=tenant_a,
            question="Pergunta sintetica da PR 18?",
            answer="Resposta sintetica da PR 18.",
        )
        event = CompanyEvent(
            id="pr18-event-a",
            tenant_id=tenant_a,
            title="Evento sintetico da PR 18",
            event_date="2026-10-01",
            event_type="palestra",
        )
        session.add_all([faq, event])

        ready_document = create_document(
            session,
            tenant_id=tenant_a,
            data=DocumentCreateData(
                filename="ready-pr18.txt",
                mime_type="text/plain",
                size_bytes=128,
                sha256=sha256(b"ready-pr18").hexdigest(),
            ),
        )
        transition_document_status(
            session,
            tenant_id=tenant_a,
            document_id=ready_document.id,
            target_status="processing",
        )
        ready_chunks = replace_document_chunks(
            session,
            tenant_id=tenant_a,
            document_id=ready_document.id,
            chunks=(
                DocumentChunkData(content="Primeiro chunk ready da PR 18."),
                DocumentChunkData(content="Segundo chunk ready da PR 18."),
            ),
        )
        transition_document_status(
            session,
            tenant_id=tenant_a,
            document_id=ready_document.id,
            target_status="ready",
        )

        pending_document = create_document(
            session,
            tenant_id=tenant_a,
            data=DocumentCreateData(
                filename="pending-pr18.txt",
                mime_type="text/plain",
                size_bytes=64,
                sha256=sha256(b"pending-pr18").hexdigest(),
            ),
        )
        pending_chunks = replace_document_chunks(
            session,
            tenant_id=tenant_a,
            document_id=pending_document.id,
            chunks=(DocumentChunkData(content="Chunk pending que deve ser ignorado."),),
        )
        session.commit()

        tenant_b_faq = SimpleNamespace(
            id="pr18-faq-b",
            question="Pergunta preservada do tenant B?",
            answer="Resposta preservada do tenant B.",
        )
        indexer_b.index_faq(tenant_b_faq)
        tenant_b_before = {
            (doc.metadata["source_type"], doc.metadata["source_id"])
            for doc in _documents_for(real_rag_runtime, tenant_b)
        }

        first_result = reindex_script.reindex_tenant(session, tenant_a)
        first_set = {
            (doc.metadata["source_type"], doc.metadata["source_id"])
            for doc in _documents_for(real_rag_runtime, tenant_a)
        }
        second_result = reindex_script.reindex_tenant(session, tenant_a)
        second_set = {
            (doc.metadata["source_type"], doc.metadata["source_id"])
            for doc in _documents_for(real_rag_runtime, tenant_a)
        }
        tenant_b_after = {
            (doc.metadata["source_type"], doc.metadata["source_id"])
            for doc in _documents_for(real_rag_runtime, tenant_b)
        }

        expected_set = {
            ("faq", faq.id),
            ("event", event.id),
            *(("document_chunk", chunk.id) for chunk in ready_chunks),
        }
        assert first_result == reindex_script.ReindexResult(
            tenant_id=tenant_a,
            faq_count=1,
            event_count=1,
            document_count=1,
            document_chunk_count=2,
        )
        assert second_result == first_result
        assert first_set == expected_set
        assert second_set == expected_set
        assert tenant_b_after == tenant_b_before == {("faq", "pr18-faq-b")}
        assert ("document_chunk", pending_chunks[0].id) not in second_set
    finally:
        session.rollback()
        session.query(Faq).filter(Faq.tenant_id == tenant_a).delete(
            synchronize_session=False
        )
        session.query(CompanyEvent).filter(CompanyEvent.tenant_id == tenant_a).delete(
            synchronize_session=False
        )
        session.query(Document).filter(Document.tenant_id == tenant_a).delete(
            synchronize_session=False
        )
        session.commit()
        session.close()


def test_process_document_completes_with_real_postgres_and_pgvector(
    real_rag_runtime,
) -> None:
    from app.document_processing import process_document

    tenant_id = "pr13-processing-success"
    real_rag_runtime.make_indexer(tenant_id)
    document_id = _create_pending_processing_document(tenant_id)

    try:
        result = process_document(
            document_id=document_id,
            tenant_id=tenant_id,
            content=(
                b"Politica institucional sintetica. "
                b"O prazo oficial para resposta e de trinta dias."
            ),
        )

        stored = _processing_state(tenant_id, document_id)
        vectors = _documents_for(real_rag_runtime, tenant_id)
        assert result.status == "ready"
        assert stored.status == "ready"
        assert stored.chunk_count == 1
        assert stored.processed_at is not None
        assert stored.error_message is None
        assert len(vectors) == 1
        assert vectors[0].metadata["document_id"] == document_id
        assert vectors[0].metadata["tenant_id"] == tenant_id
        assert vectors[0].metadata["source_type"] == "document_chunk"
    finally:
        _remove_processing_document(tenant_id, document_id)


def test_process_document_compensates_real_partial_vector_failure(
    monkeypatch,
    real_rag_runtime,
) -> None:
    from app import rag_engine
    from app.document_processing import process_document

    tenant_id = "pr13-processing-failure"
    real_rag_runtime.make_indexer(tenant_id)
    document_id = _create_pending_processing_document(tenant_id)

    def fail_after_first_vector(self, document, chunks, *, previous_chunks=None):
        self.index_document_chunk(document, chunks[0])
        raise RuntimeError("falha sintetica apos vetor parcial")

    monkeypatch.setattr(
        rag_engine.RAGEngine,
        "reindex_document_chunks",
        fail_after_first_vector,
    )

    try:
        result = process_document(
            document_id=document_id,
            tenant_id=tenant_id,
            content=b"Conteudo sintetico para falha vetorial controlada.",
        )

        stored = _processing_state(tenant_id, document_id)
        assert result.status == "error"
        assert stored.status == "error"
        assert stored.chunk_count == 0
        assert stored.chunk_contents == []
        assert stored.error_message == "Falha ao indexar os chunks."
        assert _documents_for(real_rag_runtime, tenant_id) == []
    finally:
        _remove_processing_document(tenant_id, document_id)


def test_delete_document_endpoint_removes_real_record_chunks_and_vectors(
    monkeypatch,
    real_rag_runtime,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "integration-test-secret")

    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.database import SessionLocal
    from app.document_repository import get_document, list_document_chunks

    tenant_id = "pr14-api-delete"
    document_id = _create_ready_document_with_vector(real_rag_runtime, tenant_id)
    monkeypatch.setattr(main, "warm_up_rag_runtime", lambda: None)
    main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=tenant_id,
        email="pr14@example.test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    try:
        assert len(_documents_for(real_rag_runtime, tenant_id)) == 1
        with TestClient(main.app) as client:
            response = client.delete(f"/documents/{document_id}")

        assert response.status_code == 204
        assert response.content == b""
        assert _documents_for(real_rag_runtime, tenant_id) == []

        session = SessionLocal()
        try:
            assert get_document(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            ) is None
            assert list_document_chunks(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            ) == []
        finally:
            session.close()
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
        _remove_processing_document(tenant_id, document_id)


@pytest.mark.parametrize(
    ("payload_fixture", "filename", "mime_type"),
    (
        ("synthetic_txt_bytes", "aceite.txt", "text/plain"),
        (
            "synthetic_docx_bytes",
            "aceite.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("synthetic_pdf_bytes", "aceite.pdf", "application/pdf"),
    ),
    ids=("txt", "docx", "pdf"),
)
def test_integrated_upload_retrieval_source_validity_tenant_and_delete_flow(
    monkeypatch,
    real_rag_runtime,
    request,
    payload_fixture: str,
    filename: str,
    mime_type: str,
) -> None:
    """Fecha o fluxo transversal sem LLM e sem depender de polling ou timing real."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "integration-test-secret")

    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.database import SessionLocal
    from app.document_repository import (
        get_document,
        list_document_chunks,
        list_document_parents,
    )

    tenant_a = f"pr21-flow-{filename}-a"
    tenant_b = f"pr21-flow-{filename}-b"
    active_tenant = {"id": tenant_a}
    created_documents: list[tuple[str, str]] = []
    payload = request.getfixturevalue(payload_fixture)

    real_rag_runtime.make_indexer(tenant_a)
    real_rag_runtime.make_indexer(tenant_b)
    monkeypatch.setattr(main, "warm_up_rag_runtime", lambda: None)
    main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=active_tenant["id"],
        email=f"{active_tenant['id']}@example.test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    try:
        with TestClient(main.app) as client:
            live_response = client.post(
                "/documents/upload",
                files={"file": (filename, payload, mime_type)},
                data={
                    "document_type": "regulamento",
                    "document_number": "21/2026",
                    "valid_until": "2026-08-24",
                },
            )
            assert live_response.status_code == 202
            assert live_response.json()["status"] == "pending"
            live_id = live_response.json()["id"]
            created_documents.append((tenant_a, live_id))

            ready_response = client.get(f"/documents/{live_id}")
            assert ready_response.status_code == 200
            assert ready_response.json()["status"] == "ready"
            assert ready_response.json()["chunk_count"] >= 1

            expired_response = client.post(
                "/documents/upload",
                files={
                    "file": (
                        "vencido.txt",
                        b"Documento sintetico vencido e fora do contexto.",
                        "text/plain",
                    )
                },
                data={"valid_until": "2026-08-23"},
            )
            assert expired_response.status_code == 202
            expired_id = expired_response.json()["id"]
            created_documents.append((tenant_a, expired_id))
            assert client.get(f"/documents/{expired_id}").json()["status"] == "ready"

            active_tenant["id"] = tenant_b
            tenant_b_response = client.post(
                "/documents/upload",
                files={
                    "file": (
                        "isolado.txt",
                        b"Conteudo exclusivo e preservado do tenant B.",
                        "text/plain",
                    )
                },
            )
            assert tenant_b_response.status_code == 202
            tenant_b_id = tenant_b_response.json()["id"]
            created_documents.append((tenant_b, tenant_b_id))
            assert client.get(f"/documents/{tenant_b_id}").json()["status"] == "ready"

            tenant_a_vectors = _documents_for(real_rag_runtime, tenant_a)
            live_vector = next(
                doc for doc in tenant_a_vectors if doc.metadata["document_id"] == live_id
            )
            expired_vector = next(
                doc for doc in tenant_a_vectors if doc.metadata["document_id"] == expired_id
            )

            retrieved, distance = asyncio.run(
                real_rag_runtime.module._retrieve_docs(
                    live_vector.page_content,
                    tenant_a,
                    today=date(2026, 8, 24),
                )
            )
            assert len(retrieved) == 1
            assert (
                retrieved[0].metadata["source_id"]
                == live_vector.metadata["parent_id"]
            )
            assert (
                retrieved[0].metadata["matched_child_id"]
                == live_vector.metadata["source_id"]
            )
            assert retrieved[0].metadata["context_expanded"] is True
            assert {doc.metadata["tenant_id"] for doc in retrieved} == {tenant_a}
            assert distance == pytest.approx(0.0, abs=1e-6)
            formatted_source = real_rag_runtime.module._format_retrieved_document(
                retrieved[0]
            )
            assert "Fonte documental" in formatted_source
            assert f"Nome: {filename}" in formatted_source
            assert "Tipo: regulamento" in formatted_source
            assert "Número: 21/2026" in formatted_source
            assert "None" not in formatted_source

            expired_results, _ = asyncio.run(
                real_rag_runtime.module._retrieve_docs(
                    expired_vector.page_content,
                    tenant_a,
                    today=date(2026, 8, 24),
                )
            )
            assert {
                expired_vector.metadata["source_id"],
                expired_vector.metadata["parent_id"],
            }.isdisjoint({
                doc.metadata["source_id"] for doc in expired_results
            })

            tenant_b_before = {
                doc.metadata["source_id"]
                for doc in _documents_for(real_rag_runtime, tenant_b)
            }
            assert tenant_b_before

            active_tenant["id"] = tenant_a
            delete_response = client.delete(f"/documents/{live_id}")
            assert delete_response.status_code == 204
            assert client.get(f"/documents/{live_id}").status_code == 404

            after_delete, _ = asyncio.run(
                real_rag_runtime.module._retrieve_docs(
                    live_vector.page_content,
                    tenant_a,
                    today=date(2026, 8, 24),
                )
            )
            assert {
                live_vector.metadata["source_id"],
                live_vector.metadata["parent_id"],
            }.isdisjoint({
                doc.metadata["source_id"] for doc in after_delete
            })
            assert {
                doc.metadata["source_id"]
                for doc in _documents_for(real_rag_runtime, tenant_b)
            } == tenant_b_before

        session = SessionLocal()
        try:
            assert get_document(
                session,
                tenant_id=tenant_a,
                document_id=live_id,
            ) is None
            assert list_document_chunks(
                session,
                tenant_id=tenant_a,
                document_id=live_id,
            ) == []
            assert list_document_parents(
                session,
                tenant_id=tenant_a,
                document_id=live_id,
            ) == []
        finally:
            session.close()
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
        for tenant_id, document_id in created_documents:
            _remove_processing_document(tenant_id, document_id)


def test_integrated_parser_error_has_no_chunks_or_vectors(
    monkeypatch,
    real_rag_runtime,
) -> None:
    """Exercita erro real do parser sobre PostgreSQL, sem mockar o processamento."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "integration-test-secret")

    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.database import SessionLocal
    from app.document_repository import get_document, list_document_chunks

    tenant_id = "pr21-parser-error"
    document_id: str | None = None
    real_rag_runtime.make_indexer(tenant_id)
    monkeypatch.setattr(main, "warm_up_rag_runtime", lambda: None)
    main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=tenant_id,
        email="pr21-parser@example.test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    try:
        with TestClient(main.app) as client:
            upload_response = client.post(
                "/documents/upload",
                files={
                    "file": (
                        "corrompido.docx",
                        b"isto nao e um pacote DOCX valido",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert upload_response.status_code == 202
            document_id = upload_response.json()["id"]

            stored_response = client.get(f"/documents/{document_id}")
            assert stored_response.status_code == 200
            assert stored_response.json()["status"] == "error"
            assert stored_response.json()["chunk_count"] == 0
            assert stored_response.json()["error_message"] == (
                "Falha ao extrair o documento."
            )

        session = SessionLocal()
        try:
            stored = get_document(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            assert stored is not None
            assert list_document_chunks(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            ) == []
            assert _documents_for(real_rag_runtime, tenant_id) == []
        finally:
            session.close()
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
        if document_id is not None:
            _remove_processing_document(tenant_id, document_id)
