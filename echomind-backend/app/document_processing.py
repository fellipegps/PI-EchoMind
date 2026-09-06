"""Orquestracao interna e sincrona do processamento documental."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from .database import Document, SessionLocal
from .document_ingestion import (
    ChunkedTextBlock,
    DocumentExtractionError,
    ExtractedDocument,
    ParentTextBlock,
    chunk_document,
    extract_docx,
    extract_pdf,
    extract_txt,
    group_document_children,
)
from .document_repository import (
    DocumentChunkData,
    DocumentNotFoundError,
    DocumentParentData,
    get_document,
    list_document_chunks,
    replace_document_chunks,
    transition_document_status,
)
from .rag_engine import get_rag_indexer
from .observability import (
    current_correlation_id,
    emit_observability_event,
    new_correlation_id,
)
from .schemas import DocumentStatus


DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_EXTRACTORS: dict[str, Callable[[bytes], ExtractedDocument]] = {
    "text/plain": extract_txt,
    DOCX_MIME_TYPE: extract_docx,
    "application/pdf": extract_pdf,
}
_ERROR_MESSAGES = {
    "state": "Falha ao iniciar o processamento.",
    "extraction": "Falha ao extrair o documento.",
    "chunking": "Falha ao dividir o documento.",
    "persistence": "Falha ao persistir os chunks.",
    "indexing": "Falha ao indexar os chunks.",
    "finalization": "Falha ao concluir o processamento.",
}


class DocumentProcessingInProgressError(Exception):
    """Impede duas execucoes concorrentes do mesmo registro."""


@dataclass(frozen=True, slots=True)
class DocumentProcessingResult:
    document_id: str
    tenant_id: str
    status: str
    chunk_count: int
    error_message: str | None


def _processing_result(document: Document) -> DocumentProcessingResult:
    return DocumentProcessingResult(
        document_id=document.id,
        tenant_id=document.tenant_id,
        status=document.status,
        chunk_count=document.chunk_count,
        error_message=document.error_message,
    )


def _extract_document(mime_type: str, content: bytes) -> ExtractedDocument:
    extractor = _EXTRACTORS.get(mime_type)
    if extractor is None:
        raise DocumentExtractionError("MIME documental sem extrator configurado.")
    return extractor(content)


def _chunk_data(chunks: tuple[ChunkedTextBlock, ...]) -> list[DocumentChunkData]:
    return [
        DocumentChunkData(
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_title=chunk.section_title,
            parent_index=chunk.parent_index,
        )
        for chunk in chunks
    ]


def _parent_data(parents: tuple[ParentTextBlock, ...]) -> list[DocumentParentData]:
    return [
        DocumentParentData(
            content=parent.content,
            page_start=parent.page_start,
            page_end=parent.page_end,
            section_title=parent.section_title,
        )
        for parent in parents
    ]


def _cleanup_partial_state(
    db: Session,
    *,
    document: Document,
    tenant_id: str,
    document_id: str,
) -> None:
    """Compensa vetores antes dos chunks para permitir retry seguro do cleanup."""
    db.rollback()
    persisted_chunks = list_document_chunks(
        db,
        tenant_id=tenant_id,
        document_id=document_id,
    )

    vectors_removed = True
    if persisted_chunks:
        try:
            get_rag_indexer(db, tenant_id).delete_document_chunks(
                document,
                persisted_chunks,
            )
        except Exception as exc:
            vectors_removed = False
            emit_observability_event(
                "ingestion.failed",
                status="error",
                stage="cleanup",
                tenant_id=tenant_id,
                duration_ms=0,
                counts={"chunks": len(persisted_chunks)},
                source_types=["document_chunk"],
                error=exc,
                level="error",
            )

    if not vectors_removed:
        return

    try:
        replace_document_chunks(
            db,
            tenant_id=tenant_id,
            document_id=document_id,
            chunks=(),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        emit_observability_event(
            "ingestion.failed",
            status="error",
            stage="cleanup",
            tenant_id=tenant_id,
            duration_ms=0,
            counts={"chunks": len(persisted_chunks)},
            source_types=["document_chunk"],
            error=exc,
            level="error",
        )


def _persist_error_state(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
    error_message: str,
) -> Document:
    """Garante processing -> error mesmo apos rollback do primeiro commit."""
    db.rollback()
    document = get_document(db, tenant_id=tenant_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Documento nao encontrado para registrar erro.")

    if document.status == DocumentStatus.PENDING.value:
        transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document_id,
            target_status=DocumentStatus.PROCESSING,
        )
    if document.status == DocumentStatus.PROCESSING.value:
        document = transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document_id,
            target_status=DocumentStatus.ERROR,
            error_message=error_message,
        )
    db.commit()
    return document


def process_document(
    *,
    document_id: str,
    tenant_id: str,
    content: bytes,
) -> DocumentProcessingResult:
    """Processa bytes duraveis com sessao propria e compensacao tenant-scoped."""
    started = time.monotonic()
    correlation_id = current_correlation_id() or new_correlation_id()
    stage = "lookup"
    event_emitted = False
    chunk_count = 0
    parent_count = 0
    previous_chunk_count = 0
    db = SessionLocal()
    try:
        if not isinstance(content, bytes):
            raise TypeError("process_document recebe somente bytes duraveis.")

        document = get_document(db, tenant_id=tenant_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Documento nao encontrado para o tenant informado.")

        if document.status == DocumentStatus.READY.value:
            result = _processing_result(document)
            emit_observability_event(
                "ingestion.completed",
                status="success",
                stage="state",
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                duration_ms=(time.monotonic() - started) * 1000,
                counts={"chunks": result.chunk_count},
                source_types=["document_chunk"],
            )
            event_emitted = True
            return result
        if document.status == DocumentStatus.ERROR.value:
            _cleanup_partial_state(
                db,
                document=document,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            refreshed = get_document(db, tenant_id=tenant_id, document_id=document_id)
            if refreshed is None:
                raise DocumentNotFoundError("Documento nao encontrado apos cleanup.")
            result = _processing_result(refreshed)
            emit_observability_event(
                "ingestion.failed",
                status="error",
                stage="cleanup",
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                duration_ms=(time.monotonic() - started) * 1000,
                counts={"chunks": result.chunk_count},
                source_types=["document_chunk"],
                level="error",
            )
            event_emitted = True
            return result
        if document.status == DocumentStatus.PROCESSING.value:
            raise DocumentProcessingInProgressError(
                "Documento ja esta sendo processado."
            )

        stage = "state"
        try:
            document = transition_document_status(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
                target_status=DocumentStatus.PROCESSING,
            )
            db.commit()

            stage = "extraction"
            extracted = _extract_document(document.mime_type, content)

            stage = "chunking"
            chunked = group_document_children(chunk_document(extracted))
            chunk_count = len(chunked.children)
            parent_count = len(chunked.parents)

            stage = "persistence"
            previous_chunks = list_document_chunks(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            previous_chunk_count = len(previous_chunks)
            persisted_chunks = replace_document_chunks(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
                chunks=_chunk_data(chunked.children),
                parents=_parent_data(chunked.parents),
            )
            db.commit()

            document = get_document(db, tenant_id=tenant_id, document_id=document_id)
            if document is None:
                raise DocumentNotFoundError("Documento desapareceu durante o processamento.")

            stage = "indexing"
            get_rag_indexer(db, tenant_id).reindex_document_chunks(
                document,
                persisted_chunks,
                previous_chunks=previous_chunks,
            )

            stage = "finalization"
            document = transition_document_status(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
                target_status=DocumentStatus.READY,
            )
            db.commit()
            result = _processing_result(document)
            emit_observability_event(
                "ingestion.completed",
                status="success",
                stage="finalization",
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                duration_ms=(time.monotonic() - started) * 1000,
                counts={
                    "chunks": chunk_count,
                    "parents": parent_count,
                    "previous_chunks": previous_chunk_count,
                },
                source_types=["document_chunk"],
            )
            event_emitted = True
            return result
        except Exception as exc:
            error_message = _ERROR_MESSAGES[stage]
            emit_observability_event(
                "ingestion.failed",
                status="error",
                stage=stage,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                duration_ms=(time.monotonic() - started) * 1000,
                counts={
                    "chunks": chunk_count,
                    "parents": parent_count,
                    "previous_chunks": previous_chunk_count,
                },
                source_types=["document_chunk"],
                error=exc,
                level="error",
            )
            event_emitted = True
            _cleanup_partial_state(
                db,
                document=document,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            failed = _persist_error_state(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
                error_message=error_message,
            )
            return _processing_result(failed)
    except Exception as exc:
        if not event_emitted:
            emit_observability_event(
                "ingestion.failed",
                status="error",
                stage=stage,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                duration_ms=(time.monotonic() - started) * 1000,
                counts={"chunks": chunk_count, "parents": parent_count},
                source_types=["document_chunk"],
                error=exc,
                level="error",
            )
        raise
    finally:
        db.close()
