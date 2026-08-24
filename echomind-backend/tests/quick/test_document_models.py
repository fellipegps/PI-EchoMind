"""Testes rapidos dos models e schemas documentais em SQLite."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect

from app.schemas import DocumentListResponse, DocumentResponse, DocumentStatus


@pytest.fixture()
def document_models(quick_test_context):
    from app.database import Document, DocumentChunk

    return SimpleNamespace(Document=Document, DocumentChunk=DocumentChunk)


def test_document_tables_are_created_by_metadata_in_sqlite(quick_test_context) -> None:
    tables = set(inspect(quick_test_context.engine).get_table_names())

    assert {"documents", "document_chunks"} <= tables
    assert "knowledge_documents" not in tables


def test_document_defaults_relationship_and_schema_serialization(db, document_models) -> None:
    document = document_models.Document(
        tenant_id="tenant-a",
        filename="regulamento.pdf",
        mime_type="application/pdf",
        size_bytes=128,
        sha256="a" * 64,
        document_type="regulamento",
        document_number="001/2026",
        department="Secretaria Academica",
        published_at=date(2026, 8, 1),
        valid_until=None,
    )
    document.chunks.append(
        document_models.DocumentChunk(
            tenant_id="tenant-a",
            chunk_index=0,
            content="Conteudo institucional.",
            page_start=1,
            page_end=1,
            section_title="Apresentacao",
        )
    )
    db.add(document)
    db.flush()

    assert document.status == DocumentStatus.PENDING.value
    assert document.chunk_count == 0
    assert document.error_message is None
    assert document.processed_at is None
    assert document.valid_until is None
    assert document.chunks[0].document_id == document.id

    response = DocumentResponse.model_validate(document)
    listing = DocumentListResponse(documents=[response], total=1)
    payload = listing.model_dump(mode="json")

    assert payload["documents"][0]["status"] == "pending"
    assert payload["documents"][0]["valid_until"] is None
    assert payload["documents"][0]["published_at"] == "2026-08-01"
    assert payload["total"] == 1


def test_document_status_contract_rejects_unknown_state() -> None:
    assert {status.value for status in DocumentStatus} == {
        "pending",
        "processing",
        "ready",
        "error",
    }

    with pytest.raises(ValidationError):
        DocumentResponse(
            id="doc-1",
            filename="arquivo.txt",
            mime_type="text/plain",
            size_bytes=10,
            sha256="b" * 64,
            status="unknown",
            chunk_count=0,
            document_type=None,
            document_number=None,
            department=None,
            published_at=None,
            valid_until=None,
            error_message=None,
            created_at="2026-08-24T12:00:00",
            updated_at="2026-08-24T12:00:00",
            processed_at=None,
        )
