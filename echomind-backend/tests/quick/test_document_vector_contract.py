"""Contrato unitario do ciclo vetorial de chunks documentais."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def rag_engine_module(quick_test_context):
    from app import rag_engine

    return rag_engine


def _document(**overrides):
    values = {
        "id": "doc-1",
        "tenant_id": "tenant-a",
        "filename": "regulamento.pdf",
        "mime_type": "application/pdf",
        "document_type": "regulamento",
        "document_number": "42/2026",
        "department": "Secretaria Academica",
        "published_at": date(2026, 2, 1),
        "valid_until": date(2027, 2, 1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _chunk(**overrides):
    values = {
        "id": "chunk-1",
        "tenant_id": "tenant-a",
        "document_id": "doc-1",
        "chunk_index": 0,
        "content": "Prazo institucional de trinta dias.",
        "page_start": 2,
        "page_end": 3,
        "section_title": "Dos prazos",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _indexer(rag_engine_module, tenant_id="tenant-a"):
    indexer = object.__new__(rag_engine_module.RAGEngine)
    indexer.tenant_id = tenant_id
    return indexer


def test_document_chunk_uses_deterministic_id_header_and_metadata(
    monkeypatch,
    rag_engine_module,
) -> None:
    store = MagicMock()
    requested_tenants: list[str] = []

    def get_store(tenant_id: str):
        requested_tenants.append(tenant_id)
        return store

    monkeypatch.setattr(rag_engine_module, "_get_vector_store", get_store)
    indexer = _indexer(rag_engine_module)
    document = _document()
    chunk = _chunk()

    indexer.index_document_chunk(document, chunk)

    vector_id = rag_engine_module._make_vector_id(
        "chunk-1",
        "document_chunk",
        "tenant-a",
    )
    assert rag_engine_module._tenant_collection_name("tenant-a") == "knowledge_tenant_a"
    store.delete.assert_called_once_with(ids=[vector_id], collection_only=True)
    stored = store.add_documents.call_args.args[0][0]
    assert store.add_documents.call_args.kwargs == {"ids": [vector_id]}
    assert requested_tenants == ["tenant-a", "tenant-a"]
    assert stored.page_content == (
        "Arquivo: regulamento.pdf\n"
        "Tipo: regulamento\n"
        "Numero: 42/2026\n"
        "Departamento: Secretaria Academica\n"
        "Publicado em: 2026-02-01\n"
        "Valido ate: 2027-02-01\n"
        "Secao: Dos prazos\n"
        "Paginas: 2-3\n\n"
        "Prazo institucional de trinta dias."
    )
    assert stored.metadata == {
        "document_id": "doc-1",
        "filename": "regulamento.pdf",
        "mime_type": "application/pdf",
        "document_type": "regulamento",
        "document_number": "42/2026",
        "department": "Secretaria Academica",
        "published_at": "2026-02-01",
        "valid_until": "2027-02-01",
        "chunk_index": 0,
        "page_start": 2,
        "page_end": 3,
        "section_title": "Dos prazos",
        "source_id": "chunk-1",
        "source_type": "document_chunk",
        "tenant_id": "tenant-a",
    }


def test_reindex_removes_previous_orphans_before_indexing_current_chunks(
    monkeypatch,
    rag_engine_module,
) -> None:
    store = MagicMock()
    monkeypatch.setattr(rag_engine_module, "_get_vector_store", lambda tenant_id: store)
    indexer = _indexer(rag_engine_module)
    document = _document()
    old_chunks = (_chunk(), _chunk(id="chunk-orphan", chunk_index=1))
    current_chunk = _chunk(content="Conteudo atualizado.")

    indexer.reindex_document_chunks(
        document,
        (current_chunk,),
        previous_chunks=old_chunks,
    )

    expected_ids = [
        rag_engine_module._make_vector_id(chunk.id, "document_chunk", "tenant-a")
        for chunk in old_chunks
    ]
    store.delete.assert_called_once_with(ids=expected_ids, collection_only=True)
    assert store.add_documents.call_count == 1
    assert store.add_documents.call_args.args[0][0].page_content.endswith("Conteudo atualizado.")


def test_delete_rejects_chunks_from_another_tenant_before_touching_store(
    monkeypatch,
    rag_engine_module,
) -> None:
    store = MagicMock()
    monkeypatch.setattr(rag_engine_module, "_get_vector_store", lambda tenant_id: store)
    indexer = _indexer(rag_engine_module)

    with pytest.raises(ValueError, match="tenant"):
        indexer.delete_document_chunks(
            _document(),
            (_chunk(tenant_id="tenant-b"),),
        )

    store.delete.assert_not_called()
    store.add_documents.assert_not_called()


def test_reindex_rejects_empty_chunk_before_deleting_existing_vectors(
    monkeypatch,
    rag_engine_module,
) -> None:
    store = MagicMock()
    monkeypatch.setattr(rag_engine_module, "_get_vector_store", lambda tenant_id: store)
    indexer = _indexer(rag_engine_module)

    with pytest.raises(ValueError, match="vazio"):
        indexer.reindex_document_chunks(
            _document(),
            (_chunk(content="  "),),
        )

    store.delete.assert_not_called()
    store.add_documents.assert_not_called()
