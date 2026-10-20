"""Real pgvector batch boundaries, ambiguous writes and interrupted ingestion."""
import asyncio
from datetime import date
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.test_document_pgvector import (
    real_rag_runtime, _chunk, _document, _create_pending_processing_document,
    _processing_state, _remove_processing_document,
)

pytestmark = pytest.mark.integration


def _snapshot(runtime, tenant):
    from app.database import engine
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT e.custom_id,e.document,e.cmetadata,e.embedding::text AS embedding "
            "FROM langchain_pg_embedding e JOIN langchain_pg_collection c ON c.uuid=e.collection_id "
            "WHERE c.name=:name ORDER BY e.custom_id"
        ), {"name": runtime._tenant_collection_name(tenant)}).mappings().all()


def test_batches_preserve_all_vectors_metadata_and_idempotency(real_rag_runtime):
    runtime = real_rag_runtime.module
    tenant = "batch-" + uuid4().hex
    other = "protected-" + uuid4().hex
    indexer = real_rag_runtime.make_indexer(tenant)
    real_rag_runtime.make_indexer(other)._upsert_document("faq", "faq", "Conteudo protegido.")
    protected = _snapshot(runtime, other)
    document = _document("synthetic-document", tenant, "synthetic.pdf")
    chunks = [_chunk(f"chunk-{i}", document.id, tenant, i, f"Conteudo sintetico {i}.") for i in range(65)]
    orphan = _chunk("orphan", document.id, tenant, 66, "Remover somente este trecho antigo.")
    indexer.index_document_chunk(document, orphan)
    indexer.reindex_document_chunks(document, chunks, previous_chunks=[orphan])
    first = _snapshot(runtime, tenant)
    assert len(first) == 65
    assert {row["custom_id"] for row in first} == {
        runtime._make_vector_id(chunk.id, "document_chunk", tenant) for chunk in chunks
    }
    for row in first:
        metadata = row["cmetadata"]
        chunk = chunks[int(metadata["source_id"].split("-")[1])]
        assert row["document"] == runtime._document_chunk_content(document, chunk)
        assert metadata["tenant_id"] == tenant and metadata["document_id"] == document.id
        assert metadata["valid_until"] == "2027-02-01"
        expected = runtime._get_vector_store(tenant).embedding_function.embed_documents([row["document"]])[0]
        assert json.loads(row["embedding"]) == pytest.approx(expected, abs=1e-6)
    indexer.reindex_document_chunks(document, chunks)
    assert _snapshot(runtime, tenant) == first
    assert _snapshot(runtime, other) == protected


CONTENT = ("Regra sintetica de atendimento. O prazo de resposta e trinta dias.\n\n" * 1200).encode()


@pytest.mark.parametrize("committed_before_failure", [False, True])
def test_second_batch_failure_compensates_even_if_write_committed(
    real_rag_runtime, monkeypatch, committed_before_failure,
):
    from app.document_processing import process_document
    runtime = real_rag_runtime.module
    tenant = "batch-failure-" + uuid4().hex
    real_rag_runtime.make_indexer(tenant)
    document_id = _create_pending_processing_document(tenant)
    store = runtime._get_vector_store(tenant)
    original = store.add_embeddings
    calls = []
    def fail(**kwargs):
        calls.append(len(kwargs["ids"]))
        if len(calls) == 2:
            if committed_before_failure:
                original(**kwargs)
            raise RuntimeError("Synthetic lost acknowledgement")
        return original(**kwargs)
    monkeypatch.setattr(store, "add_embeddings", fail)
    try:
        result = process_document(document_id=document_id, tenant_id=tenant, content=CONTENT)
        assert calls == [32, 32]
        assert result.status == "error"
        state = _processing_state(tenant, document_id)
        assert state.chunk_count == 0 and state.chunk_contents == []
        assert _snapshot(runtime, tenant) == []
    finally:
        _remove_processing_document(tenant, document_id)


def test_crash_after_committed_batch_resumes_without_orphans(real_rag_runtime, monkeypatch):
    from app.database import Document, DocumentChunk, SessionLocal
    from app.document_processing import process_document
    runtime = real_rag_runtime.module
    tenant = "batch-resume-" + uuid4().hex
    real_rag_runtime.make_indexer(tenant)
    document_id = _create_pending_processing_document(tenant)
    store = runtime._get_vector_store(tenant)
    original = store.add_embeddings
    class SimulatedCrash(BaseException):
        pass
    def interrupt(**kwargs):
        original(**kwargs)
        raise SimulatedCrash()
    monkeypatch.setattr(store, "add_embeddings", interrupt)
    try:
        with pytest.raises(SimulatedCrash):
            process_document(document_id=document_id, tenant_id=tenant, content=CONTENT)
        assert _processing_state(tenant, document_id).status == "processing"
        interrupted = _snapshot(runtime, tenant)
        assert len(interrupted) == 32
        # The safety fix remains effective for committed partial batches.
        retrieved = asyncio.run(runtime._retrieve_docs(
            "Regra sintetica", tenant, today=date(2026, 10, 19),
        ))
        assert retrieved == ([], None)
        monkeypatch.setattr(store, "add_embeddings", original)
        result = process_document(document_id=document_id, tenant_id=tenant, content=CONTENT, resume_interrupted=True)
        assert result.status == "ready" and result.chunk_count > 32
        restored = _snapshot(runtime, tenant)
        assert len(restored) == result.chunk_count
        assert len({row['custom_id'] for row in restored}) == result.chunk_count
        with SessionLocal() as session:
            chunk_ids = [row[0] for row in session.query(DocumentChunk.id).filter_by(
                tenant_id=tenant, document_id=document_id,
            ).all()]
        assert {row['custom_id'] for row in restored} == {
            runtime._make_vector_id(chunk_id, "document_chunk", tenant) for chunk_id in chunk_ids
        }
    finally:
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                session.delete(document)
                session.commit()
