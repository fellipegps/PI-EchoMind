"""Contrato E5 observado na entrada do tokenizer, sem modelo nem rede."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.embedding_fakes import install_fake_fastembed


@pytest.fixture()
def embedding_runtime(monkeypatch, quick_test_context):
    from app import rag_engine

    rag_engine._register_default_embedding_model()
    fake = install_fake_fastembed(monkeypatch)
    monkeypatch.setattr(rag_engine, "EMBED_MODEL", rag_engine.DEFAULT_EMBED_MODEL)
    monkeypatch.setattr(rag_engine, "_register_default_embedding_model", lambda: None)
    rag_engine._get_embeddings.cache_clear()
    try:
        yield SimpleNamespace(rag=rag_engine, fake=fake, adapter=rag_engine._get_embeddings())
    finally:
        rag_engine._get_embeddings.cache_clear()


@pytest.mark.parametrize("doc_embed_type", ["default", "passage"])
def test_e5_query_and_document_prefixes_reach_tokenizer_once(embedding_runtime, doc_embed_type):
    runtime = embedding_runtime
    runtime.adapter.doc_embed_type = doc_embed_type
    runtime.adapter.batch_size = 1
    query = "Como funciona a matrícula?"
    texts = ["Regulamento acadêmico.", "Texto com query: e passage: no conteúdo."]

    query_vector = runtime.adapter.embed_query(query)
    vectors = runtime.adapter.embed_documents(texts)

    assert runtime.fake.received == ["query: " + query, *("passage: " + text for text in texts)]
    assert len(query_vector) == 384
    assert [len(vector) for vector in vectors] == [384, 384]
    assert texts == ["Regulamento acadêmico.", "Texto com query: e passage: no conteúdo."]


def test_faq_and_document_chunk_prefix_only_embedding_input(embedding_runtime, monkeypatch):
    runtime = embedding_runtime
    stored = []

    def add_documents(documents, ids):
        runtime.adapter.embed_documents([document.page_content for document in documents])
        stored.extend(zip(documents, ids))

    store = MagicMock()
    store.add_documents.side_effect = add_documents
    monkeypatch.setattr(runtime.rag, "_get_vector_store", lambda tenant: store)
    indexer = object.__new__(runtime.rag.RAGEngine)
    indexer.tenant_id = "tenant-e5"
    faq = SimpleNamespace(id="faq-e5", tenant_id=indexer.tenant_id, question="Horário?", answer="Às 8h.")
    document = SimpleNamespace(
        id="doc-e5", tenant_id=indexer.tenant_id, filename="norma.txt",
        mime_type="text/plain", document_type="regulamento", document_number="42",
        department=None, published_at=None, valid_until=None,
    )
    chunk = SimpleNamespace(
        id="chunk-e5", document_id=document.id, tenant_id=indexer.tenant_id,
        chunk_index=0, content="Atendimento às 8h.", page_start=1, page_end=1,
        section_title="Atendimento",
    )

    indexer.index_faq(faq)
    indexer.index_document_chunk(document, chunk)

    originals = [f"Pergunta: {faq.question}\nResposta: {faq.answer}", runtime.rag._document_chunk_content(document, chunk)]
    assert runtime.fake.received == ["passage: " + text for text in originals]
    assert [vector_document.page_content for vector_document, _ in stored] == originals
    assert [vector_id for _, vector_id in stored] == [
        runtime.rag._make_vector_id(faq.id, "faq", indexer.tenant_id),
        runtime.rag._make_vector_id(chunk.id, "document_chunk", indexer.tenant_id),
    ]
    assert stored[0][0].metadata == {"source_id": faq.id, "source_type": "faq", "tenant_id": indexer.tenant_id}
    assert stored[1][0].metadata == {
        "document_id": document.id, "filename": "norma.txt", "mime_type": "text/plain",
        "document_type": "regulamento", "document_number": "42", "chunk_index": 0,
        "page_start": 1, "page_end": 1, "section_title": "Atendimento",
        "source_id": chunk.id, "source_type": "document_chunk", "tenant_id": indexer.tenant_id,
    }
    assert chunk.content == "Atendimento às 8h."


def test_adapter_bypasses_model_specific_automatic_prefixes(embedding_runtime, monkeypatch):
    runtime = embedding_runtime

    def automatic_prefix(*args, **kwargs):
        pytest.fail("Adapter E5 nao deve delegar a metodos com prefixacao automatica.")

    monkeypatch.setattr(runtime.fake.wrapper, "query_embed", automatic_prefix)
    monkeypatch.setattr(runtime.fake.wrapper, "passage_embed", automatic_prefix)
    runtime.adapter.doc_embed_type = "passage"
    runtime.adapter.embed_query("Consulta original")
    runtime.adapter.embed_documents(["Fonte original"])
    assert runtime.fake.received == ["query: Consulta original", "passage: Fonte original"]
