"""Atualizacao do contrato E5 via reindexacao existente no pgvector descartavel."""

from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.embedding_fakes import install_fake_fastembed


pytestmark = pytest.mark.integration


def test_reindex_replaces_legacy_vectors_preserving_sources_ids_and_tenants(
    monkeypatch, postgres_engine, integration_database_url,
):
    from app import rag_engine
    from app.database import Document, DocumentChunk, Faq
    from scripts import reindex_all

    rag_engine._register_default_embedding_model()
    fake = install_fake_fastembed(monkeypatch)
    monkeypatch.setattr(rag_engine, "EMBED_MODEL", rag_engine.DEFAULT_EMBED_MODEL)
    monkeypatch.setattr(rag_engine, "DATABASE_URL", integration_database_url)
    monkeypatch.setattr(rag_engine, "_register_default_embedding_model", lambda: None)
    rag_engine._get_embeddings.cache_clear()
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()
    tenants = ["e5-" + uuid4().hex for _ in range(2)]
    stores = []

    def snapshot(tenant):
        with postgres_engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(
                "SELECT e.custom_id, e.document, e.cmetadata, e.embedding::text AS embedding "
                "FROM langchain_pg_embedding e JOIN langchain_pg_collection c "
                "ON c.uuid = e.collection_id WHERE c.name = :name ORDER BY e.custom_id"
            ), {"name": rag_engine._tenant_collection_name(tenant)}).mappings()]

    try:
        with Session(postgres_engine) as session:
            for tenant in tenants:
                faq = Faq(tenant_id=tenant, question="Horário da secretaria?", answer="Às 8h.")
                document = Document(
                    id=str(uuid4()), tenant_id=tenant, filename="norma.txt",
                    mime_type="text/plain", size_bytes=32, sha256=sha256(tenant.encode()).hexdigest(),
                    status="ready", chunk_count=1,
                )
                chunk = DocumentChunk(
                    id=str(uuid4()), document_id=document.id, tenant_id=tenant,
                    chunk_index=0, content="Atendimento às 8h.", page_start=1, page_end=1,
                    section_title="Atendimento",
                )
                session.add_all([faq, document])
                session.flush()
                session.add(chunk)
                session.commit()
                store = rag_engine._get_vector_store(tenant)
                stores.append(store)
                # Simula vetores anteriores, preservando o contrato de fontes/IDs.
                contents = [f"Pergunta: {faq.question}\nResposta: {faq.answer}", rag_engine._document_chunk_content(document, chunk)]
                metadatas = [
                    {"source_id": faq.id, "source_type": "faq", "tenant_id": tenant},
                    {**rag_engine._normalize_extra_metadata(rag_engine._document_chunk_metadata(document, chunk)),
                     "source_id": chunk.id, "source_type": "document_chunk", "tenant_id": tenant},
                ]
                store.add_embeddings(
                    texts=contents, embeddings=[[1.0, *([0.0] * 383)]] * 2,
                    metadatas=metadatas,
                    ids=[rag_engine._make_vector_id(metadata["source_id"], metadata["source_type"], tenant) for metadata in metadatas],
                )

        before = snapshot(tenants[0])
        protected = snapshot(tenants[1])
        assert fake.received == []
        with Session(postgres_engine) as session:
            first = reindex_all.reindex_tenant(session, tenants[0])
            rebuilt = snapshot(tenants[0])
            assert (first.faq_count, first.document_count, first.document_chunk_count) == (1, 1, 1)
            assert sorted(fake.received) == sorted("passage: " + row["document"] for row in before)
            assert [{key: value for key, value in row.items() if key != "embedding"} for row in rebuilt] == [
                {key: value for key, value in row.items() if key != "embedding"} for row in before
            ]
            assert all(new["embedding"] != old["embedding"] for new, old in zip(rebuilt, before))
            assert snapshot(tenants[1]) == protected
            assert session.query(DocumentChunk).filter_by(tenant_id=tenants[0]).one().content == "Atendimento às 8h."
            second = reindex_all.reindex_tenant(session, tenants[0])
            assert second == first
            assert snapshot(tenants[0]) == rebuilt

        results = stores[0].similarity_search("Horário da secretaria?", k=2)
        assert fake.received[-1] == "query: Horário da secretaria?"
        assert {result.page_content for result in results} == {row["document"] for row in before}
        assert all(result.metadata["tenant_id"] == tenants[0] for result in results)
    finally:
        for store in stores:
            store.delete_collection()
        with Session(postgres_engine) as session:
            session.query(Faq).filter(Faq.tenant_id.in_(tenants)).delete(synchronize_session=False)
            session.query(Document).filter(Document.tenant_id.in_(tenants)).delete(synchronize_session=False)
            session.commit()
        rag_engine._get_embeddings.cache_clear()
        rag_engine._get_vector_store.cache_clear()
        rag_engine._enable_langchain_rls_if_possible.cache_clear()
