"""Vetores residuais nunca autorizam uma fonte documental por si mesmos."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document as RetrievedDocument


class NonClosingSession:
    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)

    def close(self):
        pass


@pytest.mark.parametrize("with_parent", [False, True])
@pytest.mark.parametrize(
    "state",
    ["ready", "pending", "processing", "error", "deleted", "expired",
     "other-tenant", "missing-chunk", "wrong-document", "wrong-parent"],
)
def test_expansion_requires_current_ready_document_and_matching_chunk(
    db, monkeypatch, state, with_parent,
):
    from app import rag_engine
    from app.database import Document, DocumentChunk
    from app.document_repository import (
        DocumentChunkData, DocumentParentData, replace_document_chunks,
    )

    today = date(2026, 9, 1)
    tenant = "tenant-b" if state == "other-tenant" else "tenant-a"
    stored = Document(
        id="document-a", tenant_id=tenant, filename="norma.txt",
        mime_type="text/plain", size_bytes=32, sha256="a" * 64,
        status=state if state in {"pending", "processing", "error"} else "ready",
        valid_until=today - timedelta(days=1) if state == "expired" else today,
    )
    db.add(stored)
    db.flush()
    chunk = replace_document_chunks(
        db, tenant_id=tenant, document_id=stored.id,
        chunks=[DocumentChunkData(content="Regra.", parent_index=0 if with_parent else None)],
        parents=[DocumentParentData(content="Regra. Excecao.")] if with_parent else (),
    )[0]
    child = RetrievedDocument(page_content=chunk.content, metadata={
        "source_type": "document_chunk", "source_id": chunk.id,
        "document_id": stored.id, "tenant_id": "tenant-a",
        "parent_id": "parent-forjado" if state == "wrong-parent" else chunk.parent_id,
        # Metadata vetorial antiga ou forjada nao deve autorizar a fonte.
        "valid_until": "2099-01-01",
    })
    if state == "deleted":
        db.delete(stored)
    elif state == "missing-chunk":
        db.query(DocumentChunk).filter_by(id=chunk.id).delete(synchronize_session=False)
    elif state == "wrong-document":
        child.metadata["document_id"] = "documento-incorreto"
    db.flush()
    monkeypatch.setattr(rag_engine, "SessionLocal", lambda: NonClosingSession(db))

    result = rag_engine._expand_document_parents([child], tenant_id="tenant-a", today=today)

    if state in {"ready", "wrong-parent"}:
        assert len(result) == 1
        assert result[0].metadata["source_type"] == (
            "document_parent" if with_parent and state == "ready" else "document_chunk"
        )
    else:
        assert result == []


def test_database_validation_failure_excludes_documents_and_preserves_faq(
    quick_test_context, monkeypatch,
):
    from app import rag_engine

    child = RetrievedDocument(page_content="Nao autorizado", metadata={
        "source_type": "document_chunk", "source_id": "chunk-a",
        "document_id": "document-a", "parent_id": "parent-a", "tenant_id": "tenant-a",
    })
    faq = RetrievedDocument(page_content="FAQ", metadata={
        "source_type": "faq", "source_id": "faq-a", "tenant_id": "tenant-a",
    })
    session = MagicMock()
    session.query.side_effect = RuntimeError("Banco indisponivel")
    monkeypatch.setattr(rag_engine, "SessionLocal", lambda: session)

    assert rag_engine._expand_document_parents(
        [child, faq], tenant_id="tenant-a", today=date(2026, 9, 1),
    ) == [faq]
    session.close.assert_called_once()


def test_parent_lookup_failure_falls_back_only_to_validated_children(
    db, monkeypatch, persist_retrieval_sources,
):
    from app import rag_engine
    from app.database import Document

    sources = [RetrievedDocument(page_content=state, metadata={
        "source_type": "document_chunk", "source_id": state,
        "document_id": f"doc-{state}", "parent_id": "missing-parent", "tenant_id": "tenant-a",
    }) for state in ("ready", "processing", "error")]
    persist_retrieval_sources(sources)
    for state in ("processing", "error"):
        db.get(Document, f"doc-{state}").status = state
    db.flush()
    query = MagicMock(side_effect=[db.query, RuntimeError("parent lookup indisponivel")])

    class LookupSession(NonClosingSession):
        def query(self, *args):
            outcome = query()
            return outcome(*args)

    monkeypatch.setattr(rag_engine, "SessionLocal", lambda: LookupSession(db))
    assert rag_engine._expand_document_parents(
        sources, tenant_id="tenant-a", today=date(2026, 9, 1),
    ) == [sources[0]]
    assert query.call_count == 2


def test_parent_must_be_linked_to_the_matched_child_and_parent_source_keeps_validation(
    db, monkeypatch, persist_retrieval_sources,
):
    from app import rag_engine
    from app.database import DocumentChunk
    from app.document_repository import (
        DocumentChunkData, DocumentParentData, list_document_parents, replace_document_chunks,
    )

    child = RetrievedDocument(page_content="Regra", metadata={
        "source_type": "document_chunk", "source_id": "initial",
        "document_id": "doc-a", "tenant_id": "tenant-a",
    })
    persist_retrieval_sources([child])
    chunk = replace_document_chunks(
        db, tenant_id="tenant-a", document_id="doc-a",
        chunks=[DocumentChunkData(content="Regra", parent_index=0)],
        parents=[DocumentParentData(content="Regra. Excecao."), DocumentParentData(content="Outra secao.")],
    )[0]
    parents = list_document_parents(db, tenant_id="tenant-a", document_id="doc-a")
    child.metadata.update(source_id=chunk.id, parent_id=parents[1].id)
    assert rag_engine._expand_document_parents(
        [child], tenant_id="tenant-a", today=date(2026, 9, 1),
    ) == [child]

    child.metadata["parent_id"] = chunk.parent_id
    expanded = rag_engine._expand_document_parents([child], tenant_id="tenant-a", today=date(2026, 9, 1))
    assert expanded[0].metadata["source_type"] == "document_parent"
    assert rag_engine._expand_document_parents(expanded, tenant_id="tenant-a", today=date(2026, 9, 1)) == expanded
    db.query(DocumentChunk).filter_by(id=chunk.id).delete(synchronize_session=False)
    db.flush()
    assert rag_engine._expand_document_parents(expanded, tenant_id="tenant-a", today=date(2026, 9, 1)) == []
