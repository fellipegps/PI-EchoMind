"""Persistencia documental com escopo obrigatorio de tenant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .database import Document, DocumentChunk, DocumentChunkParent, utc_now
from .schemas import DocumentStatus


ACTIVE_DOCUMENT_STATUSES = (
    DocumentStatus.PENDING.value,
    DocumentStatus.PROCESSING.value,
    DocumentStatus.READY.value,
)
MAX_ERROR_MESSAGE_LENGTH = 1000


class DocumentRepositoryError(Exception):
    """Erro de dominio da persistencia documental."""


class DocumentNotFoundError(DocumentRepositoryError):
    """Documento ausente ou fora do tenant informado."""


class DuplicateDocumentError(DocumentRepositoryError):
    """SHA-256 ja ativo no mesmo tenant."""


class InvalidDocumentTransitionError(DocumentRepositoryError):
    """Transicao de estado nao permitida pelo fluxo documental."""


class InvalidDocumentErrorMessageError(DocumentRepositoryError):
    """Mensagem de erro ausente, indevida ou excessivamente longa."""


class DocumentDeletionBlockedError(DocumentRepositoryError):
    """Documento ainda pendente ou em processamento nao pode ser removido."""


@dataclass(frozen=True, slots=True)
class DocumentCreateData:
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    document_type: str | None = None
    document_number: str | None = None
    department: str | None = None
    published_at: date | None = None
    valid_until: date | None = None


@dataclass(frozen=True, slots=True)
class DocumentChunkData:
    content: str
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    parent_index: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentParentData:
    content: str
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None


_DOCUMENT_NODE_NAMESPACE = uuid.UUID("d86b7998-13ef-4a2f-b900-a618dc96801a")


def _document_node_id(
    *,
    tenant_id: str,
    document_id: str,
    node_type: str,
    node_index: int,
) -> str:
    return str(
        uuid.uuid5(
            _DOCUMENT_NODE_NAMESPACE,
            f"{tenant_id}:{document_id}:{node_type}:{node_index}",
        )
    )


def get_document(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.id == document_id, Document.tenant_id == tenant_id)
        .first()
    )


def list_documents(db: Session, *, tenant_id: str) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.tenant_id == tenant_id)
        .order_by(desc(Document.created_at), desc(Document.id))
        .all()
    )


def find_active_duplicate_document(
    db: Session,
    *,
    tenant_id: str,
    sha256: str,
) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.sha256 == sha256,
            Document.status.in_(ACTIVE_DOCUMENT_STATUSES),
        )
        .order_by(desc(Document.created_at), desc(Document.id))
        .first()
    )


def create_document(
    db: Session,
    *,
    tenant_id: str,
    data: DocumentCreateData,
) -> Document:
    duplicate = find_active_duplicate_document(
        db,
        tenant_id=tenant_id,
        sha256=data.sha256,
    )
    if duplicate is not None:
        raise DuplicateDocumentError("Documento ativo com o mesmo SHA-256 neste tenant.")

    document = Document(
        tenant_id=tenant_id,
        filename=data.filename,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        sha256=data.sha256,
        document_type=data.document_type,
        document_number=data.document_number,
        department=data.department,
        published_at=data.published_at,
        valid_until=data.valid_until,
    )
    db.add(document)
    db.flush()
    return document


def transition_document_status(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
    target_status: DocumentStatus | str,
    error_message: str | None = None,
) -> Document:
    document = get_document(db, tenant_id=tenant_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Documento nao encontrado para o tenant informado.")

    current_status = DocumentStatus(document.status)
    try:
        normalized_target_status = DocumentStatus(target_status)
    except ValueError as exc:
        raise InvalidDocumentTransitionError(
            f"Estado documental desconhecido: {target_status}."
        ) from exc

    allowed_targets = {
        DocumentStatus.PENDING: {DocumentStatus.PROCESSING},
        DocumentStatus.PROCESSING: {DocumentStatus.READY, DocumentStatus.ERROR},
    }.get(current_status, set())
    if normalized_target_status not in allowed_targets:
        raise InvalidDocumentTransitionError(
            "Transicao documental invalida: "
            f"{current_status.value} -> {normalized_target_status.value}."
        )

    normalized_error = error_message.strip() if error_message is not None else None
    if normalized_target_status == DocumentStatus.ERROR:
        if not normalized_error or len(normalized_error) > MAX_ERROR_MESSAGE_LENGTH:
            raise InvalidDocumentErrorMessageError(
                "O estado error exige uma mensagem entre 1 e 1000 caracteres."
            )
    elif error_message is not None:
        raise InvalidDocumentErrorMessageError(
            "error_message so pode ser informado ao concluir em error."
        )

    now = utc_now()
    document.status = normalized_target_status.value
    document.updated_at = now
    if normalized_target_status == DocumentStatus.PROCESSING:
        document.error_message = None
        document.processed_at = None
    else:
        document.error_message = normalized_error
        document.processed_at = now

    db.flush()
    return document


def list_document_chunks(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
) -> list[DocumentChunk]:
    return (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        .order_by(DocumentChunk.chunk_index, DocumentChunk.id)
        .all()
    )


def list_document_parents(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
) -> list[DocumentChunkParent]:
    return (
        db.query(DocumentChunkParent)
        .filter(
            DocumentChunkParent.document_id == document_id,
            DocumentChunkParent.tenant_id == tenant_id,
        )
        .order_by(DocumentChunkParent.parent_index, DocumentChunkParent.id)
        .all()
    )


def replace_document_chunks(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
    chunks: Iterable[DocumentChunkData],
    parents: Iterable[DocumentParentData] = (),
) -> list[DocumentChunk]:
    document = get_document(db, tenant_id=tenant_id, document_id=document_id)
    if document is None:
        raise DocumentNotFoundError("Documento nao encontrado para o tenant informado.")

    ordered_chunks = list(chunks)
    ordered_parents = list(parents)
    if any(
        chunk.parent_index is not None
        and not 0 <= chunk.parent_index < len(ordered_parents)
        for chunk in ordered_chunks
    ):
        raise ValueError("Chunk referencia parent_index inexistente.")
    (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        .delete(synchronize_session="fetch")
    )
    (
        db.query(DocumentChunkParent)
        .filter(
            DocumentChunkParent.document_id == document_id,
            DocumentChunkParent.tenant_id == tenant_id,
        )
        .delete(synchronize_session="fetch")
    )

    persisted_parents = [
        DocumentChunkParent(
            id=_document_node_id(
                tenant_id=tenant_id,
                document_id=document_id,
                node_type="parent",
                node_index=parent_index,
            ),
            tenant_id=tenant_id,
            document_id=document_id,
            parent_index=parent_index,
            content=parent.content,
            page_start=parent.page_start,
            page_end=parent.page_end,
            section_title=parent.section_title,
        )
        for parent_index, parent in enumerate(ordered_parents)
    ]
    db.add_all(persisted_parents)
    db.flush()

    db.add_all(
        [
            DocumentChunk(
                id=_document_node_id(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    node_type="child",
                    node_index=chunk_index,
                ),
                tenant_id=tenant_id,
                document_id=document_id,
                parent_id=(
                    persisted_parents[chunk.parent_index].id
                    if chunk.parent_index is not None
                    else None
                ),
                chunk_index=chunk_index,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=chunk.section_title,
            )
            for chunk_index, chunk in enumerate(ordered_chunks)
        ]
    )
    document.chunk_count = len(ordered_chunks)
    document.updated_at = utc_now()
    db.flush()

    return list_document_chunks(db, tenant_id=tenant_id, document_id=document_id)


def delete_document(
    db: Session,
    *,
    tenant_id: str,
    document_id: str,
) -> bool:
    document = get_document(db, tenant_id=tenant_id, document_id=document_id)
    if document is None:
        return False
    if document.status in {
        DocumentStatus.PENDING.value,
        DocumentStatus.PROCESSING.value,
    }:
        raise DocumentDeletionBlockedError(
            "Documento pending ou processing nao pode ser removido."
        )

    deleted_count = (
        db.query(Document)
        .filter(Document.id == document_id, Document.tenant_id == tenant_id)
        .delete(synchronize_session="fetch")
    )
    db.flush()
    return deleted_count == 1
