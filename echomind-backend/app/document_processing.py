"""Orquestracao interna e sincrona do processamento documental."""

from __future__ import annotations

import logging
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
from .schemas import DocumentStatus


logger = logging.getLogger("echomind.document_processing")

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
        except Exception:
            vectors_removed = False
            logger.exception(
                "Falha ao compensar vetores do documento=%s tenant=%s.",
                document_id,
                tenant_id,
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
    except Exception:
        db.rollback()
        logger.exception(
            "Falha ao compensar chunks do documento=%s tenant=%s.",
            document_id,
            tenant_id,
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
    db = SessionLocal()
    try:
        if not isinstance(content, bytes):
            raise TypeError("process_document recebe somente bytes duraveis.")

        document = get_document(db, tenant_id=tenant_id, document_id=document_id)
        if document is None:
            raise DocumentNotFoundError("Documento nao encontrado para o tenant informado.")

        if document.status == DocumentStatus.READY.value:
            return _processing_result(document)
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
            return _processing_result(refreshed)
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

            stage = "persistence"
            previous_chunks = list_document_chunks(
                db,
                tenant_id=tenant_id,
                document_id=document_id,
            )
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
            return _processing_result(document)
        except Exception:
            error_message = _ERROR_MESSAGES[stage]
            logger.exception(
                "Processamento falhou na etapa=%s documento=%s tenant=%s.",
                stage,
                document_id,
                tenant_id,
            )
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
    finally:
        db.close()
