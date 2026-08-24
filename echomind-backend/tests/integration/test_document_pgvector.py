"""Ciclo documental no PGVector real com embeddings locais deterministicos."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

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
