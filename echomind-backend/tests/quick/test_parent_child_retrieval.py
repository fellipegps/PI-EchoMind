"""Contratos Parent-Child determinísticos, tenant-scoped e sem rede."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document as RetrievedDocument

from scripts.eval_parent_child import evaluate_parent_child


def _stored_document(db, *, document_id: str, tenant_id: str, valid_until: date | None = None):
    from app.database import Document

    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        filename="regulamento.txt",
        mime_type="text/plain",
        size_bytes=100,
        sha256=(document_id[-1] or "a") * 64,
        status="ready",
        chunk_count=0,
        valid_until=valid_until,
    )
    db.add(document)
    db.flush()
    return document


def _parent_data():
    from app.document_repository import DocumentParentData

    return [
        DocumentParentData(
            content="Regra principal. Exceção obrigatória.",
            page_start=1,
            page_end=2,
            section_title="Art. 8º",
        )
    ]


def _child_data():
    from app.document_repository import DocumentChunkData

    return [
        DocumentChunkData(content="Regra principal.", page_start=1, parent_index=0),
        DocumentChunkData(content="Exceção obrigatória.", page_start=2, parent_index=0),
    ]


def test_parent_child_grouping_is_deterministic_ordered_and_page_aware() -> None:
    from app.document_ingestion import ChunkedTextBlock, group_document_children

    children = (
        ChunkedTextBlock(0, "ABCDEF", page_start=1, page_end=1, section_title="Seção A"),
        ChunkedTextBlock(1, "DEFGHI", page_start=2, page_end=2, section_title="Seção A"),
        ChunkedTextBlock(2, "Regra B", page_start=3, page_end=3, section_title="Seção B"),
        ChunkedTextBlock(3, "Exceção B", page_start=4, page_end=4, section_title="Seção B"),
    )

    first = group_document_children(children, chunk_overlap=3, children_per_parent=3)
    second = group_document_children(children, chunk_overlap=3, children_per_parent=3)

    assert first == second
    assert [(parent.parent_index, parent.page_start, parent.page_end) for parent in first.parents] == [
        (0, 1, 2),
        (1, 3, 4),
    ]
    assert [child.parent_index for child in first.children] == [0, 0, 1, 1]
    assert "ABCDEF" in first.parents[0].content
    assert "GHI" in first.parents[0].content


def test_replace_is_deterministic_and_delete_leaves_no_parent_or_child(db) -> None:
    from app.database import DocumentChunk, DocumentChunkParent
    from app.document_repository import (
        delete_document,
        list_document_parents,
        replace_document_chunks,
    )

    document = _stored_document(db, document_id="doc-parent-a", tenant_id="tenant-a")

    first_children = replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=_child_data(),
        parents=_parent_data(),
    )
    first_child_ids = [chunk.id for chunk in first_children]
    first_parent_ids = [parent.id for parent in list_document_parents(db, tenant_id="tenant-a", document_id=document.id)]

    second_children = replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=_child_data(),
        parents=_parent_data(),
    )

    assert [chunk.id for chunk in second_children] == first_child_ids
    assert [parent.id for parent in list_document_parents(db, tenant_id="tenant-a", document_id=document.id)] == first_parent_ids
    assert all(chunk.parent_id == first_parent_ids[0] for chunk in second_children)
    assert document.chunk_count == 2

    assert delete_document(db, tenant_id="tenant-a", document_id=document.id)
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count() == 0
    assert db.query(DocumentChunkParent).filter(DocumentChunkParent.document_id == document.id).count() == 0


class _NonClosingSession:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self) -> None:
        pass


def test_child_retrieval_expands_parent_deduplicates_and_preserves_tenant_validity(db) -> None:
    from app import rag_engine
    from app.database import DocumentChunk
    from app.document_repository import list_document_parents, replace_document_chunks

    today = date(2026, 9, 1)
    document = _stored_document(
        db,
        document_id="doc-parent-b",
        tenant_id="tenant-a",
        valid_until=today,
    )
    children = replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=_child_data(),
        parents=_parent_data(),
    )
    parent = list_document_parents(db, tenant_id="tenant-a", document_id=document.id)[0]

    def retrieved_child(chunk: DocumentChunk) -> RetrievedDocument:
        return RetrievedDocument(
            page_content=chunk.content,
            metadata={
                "source_id": chunk.id,
                "source_type": "document_chunk",
                "tenant_id": chunk.tenant_id,
                "document_id": chunk.document_id,
                "parent_id": chunk.parent_id,
                "valid_until": today.isoformat(),
            },
        )

    faq = RetrievedDocument(
        page_content="FAQ preservada",
        metadata={"source_id": "faq-a", "source_type": "faq", "tenant_id": "tenant-a"},
    )
    wrong_tenant = RetrievedDocument(
        page_content="não pode vazar",
        metadata={"source_id": "other", "source_type": "faq", "tenant_id": "tenant-b"},
    )
    expired = RetrievedDocument(
        page_content="vencido",
        metadata={
            "source_id": "expired",
            "source_type": "document_chunk",
            "tenant_id": "tenant-a",
            "valid_until": (today - timedelta(days=1)).isoformat(),
        },
    )

    with patch.object(rag_engine, "SessionLocal", return_value=_NonClosingSession(db)):
        expanded = rag_engine._expand_document_parents(
            [retrieved_child(children[0]), retrieved_child(children[1]), faq, wrong_tenant, expired],
            tenant_id="tenant-a",
            today=today,
        )

    assert [item.metadata["source_id"] for item in expanded] == [parent.id, "faq-a"]
    assert "Regra principal" in expanded[0].page_content
    assert "Exceção obrigatória" in expanded[0].page_content
    assert expanded[0].metadata["matched_child_id"] == children[0].id
    assert expanded[0].metadata["page_start"] == 1
    assert expanded[0].metadata["page_end"] == 2


def test_parent_lookup_never_uses_id_without_tenant_and_document(db) -> None:
    from app import rag_engine
    from app.document_repository import replace_document_chunks

    document = _stored_document(db, document_id="doc-parent-c", tenant_id="tenant-a")
    chunks = replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=_child_data(),
        parents=_parent_data(),
    )
    child = RetrievedDocument(
        page_content=chunks[0].content,
        metadata={
            "source_id": chunks[0].id,
            "source_type": "document_chunk",
            "tenant_id": "tenant-a",
            "document_id": "documento-incorreto",
            "parent_id": chunks[0].parent_id,
        },
    )

    with patch.object(rag_engine, "SessionLocal", return_value=_NonClosingSession(db)):
        result = rag_engine._expand_document_parents(
            [child],
            tenant_id="tenant-a",
            today=date(2026, 9, 1),
        )

    assert result == [child]


def test_explicit_backfill_and_rollback_preserve_children(db, monkeypatch) -> None:
    from app.document_repository import (
        DocumentChunkData,
        list_document_chunks,
        list_document_parents,
        replace_document_chunks,
    )
    from scripts.reindex_all import rewrite_parent_child

    document = _stored_document(db, document_id="doc-parent-d", tenant_id="tenant-a")
    replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=[DocumentChunkData(content=f"Trecho {index}") for index in range(4)],
    )
    monkeypatch.setattr(db, "commit", db.flush)

    assert rewrite_parent_child(db) == 1
    backfilled = list_document_chunks(db, tenant_id="tenant-a", document_id=document.id)
    assert all(chunk.parent_id for chunk in backfilled)
    assert len(list_document_parents(db, tenant_id="tenant-a", document_id=document.id)) == 2

    assert rewrite_parent_child(db, rollback=True) == 1
    rolled_back = list_document_chunks(db, tenant_id="tenant-a", document_id=document.id)
    assert all(chunk.parent_id is None for chunk in rolled_back)
    assert list_document_parents(db, tenant_id="tenant-a", document_id=document.id) == []


def test_parent_child_eval_proves_context_gain_with_bounded_cost() -> None:
    evals = Path(__file__).parents[2] / "evals"
    report = evaluate_parent_child(
        json.loads((evals / "parent_child_eval.json").read_text(encoding="utf-8")),
        json.loads((evals / "reranker_report.json").read_text(encoding="utf-8")),
    )

    assert report["quality"] == {
        "pr25_context_complete_rate": 0.0,
        "parent_context_complete_rate": 1.0,
        "context_complete_gain": 1.0,
    }
    assert report["latency_ms"]["parent_lookup_overhead_mean"] == 1.125
    assert report["context"]["mean_growth_ratio"] == 2.421
