"""Contratos do repository documental multi-tenant."""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
def repository(quick_test_context):
    return importlib.import_module("app.document_repository")


def document_data(repository, sha256: str, filename: str = "documento.txt"):
    return repository.DocumentCreateData(
        filename=filename,
        mime_type="text/plain",
        size_bytes=128,
        sha256=sha256,
    )


def create_document(db, repository, tenant_id: str, sha256: str, filename: str = "documento.txt"):
    return repository.create_document(
        db,
        tenant_id=tenant_id,
        data=document_data(repository, sha256, filename),
    )


def move_to_status(db, repository, document, tenant_id: str, status: str):
    if status in {"processing", "ready", "error"}:
        repository.transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status=repository.DocumentStatus.PROCESSING,
        )
    if status == "ready":
        repository.transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status=repository.DocumentStatus.READY,
        )
    if status == "error":
        repository.transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status=repository.DocumentStatus.ERROR,
            error_message="Falha sintetica de processamento.",
        )


def test_create_list_and_get_are_tenant_scoped(db, repository) -> None:
    tenant_a_document = create_document(db, repository, "tenant-a", "a" * 64, "a.txt")
    create_document(db, repository, "tenant-a", "b" * 64, "b.txt")
    tenant_b_document = create_document(db, repository, "tenant-b", "c" * 64, "c.txt")

    tenant_a_documents = repository.list_documents(db, tenant_id="tenant-a")
    tenant_b_documents = repository.list_documents(db, tenant_id="tenant-b")

    assert {document.filename for document in tenant_a_documents} == {"a.txt", "b.txt"}
    assert [document.id for document in tenant_b_documents] == [tenant_b_document.id]
    assert repository.get_document(
        db,
        tenant_id="tenant-a",
        document_id=tenant_a_document.id,
    ) is tenant_a_document
    assert repository.get_document(
        db,
        tenant_id="tenant-b",
        document_id=tenant_a_document.id,
    ) is None


@pytest.mark.parametrize("active_status", ["pending", "processing", "ready"])
def test_duplicate_hash_is_rejected_only_for_active_states(db, repository, active_status) -> None:
    sha256 = active_status[0] * 64
    original = create_document(db, repository, "tenant-a", sha256)
    move_to_status(db, repository, original, "tenant-a", active_status)

    with pytest.raises(repository.DuplicateDocumentError):
        create_document(db, repository, "tenant-a", sha256, "duplicado.txt")

    duplicate = repository.find_active_duplicate_document(
        db,
        tenant_id="tenant-a",
        sha256=sha256,
    )
    assert duplicate.id == original.id


def test_error_document_allows_same_hash_in_same_tenant(db, repository) -> None:
    sha256 = "e" * 64
    failed = create_document(db, repository, "tenant-a", sha256, "falhou.txt")
    move_to_status(db, repository, failed, "tenant-a", "error")

    replacement = create_document(db, repository, "tenant-a", sha256, "nova-tentativa.txt")

    assert replacement.id != failed.id
    assert replacement.status == "pending"


def test_same_hash_is_allowed_in_different_tenants(db, repository) -> None:
    sha256 = "d" * 64
    tenant_a_document = create_document(db, repository, "tenant-a", sha256)
    tenant_b_document = create_document(db, repository, "tenant-b", sha256)

    assert tenant_a_document.id != tenant_b_document.id


def test_valid_transition_to_ready_sets_completion_fields(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "f" * 64)

    processing = repository.transition_document_status(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        target_status="processing",
    )
    assert processing.status == "processing"
    assert processing.processed_at is None
    assert processing.error_message is None

    ready = repository.transition_document_status(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        target_status=repository.DocumentStatus.READY,
    )
    assert ready.status == "ready"
    assert ready.processed_at is not None
    assert ready.error_message is None


def test_valid_transition_to_error_records_short_message(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "0" * 64)
    move_to_status(db, repository, document, "tenant-a", "processing")

    failed = repository.transition_document_status(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        target_status=repository.DocumentStatus.ERROR,
        error_message="  Parser indisponivel.  ",
    )

    assert failed.status == "error"
    assert failed.error_message == "Parser indisponivel."
    assert failed.processed_at is not None


@pytest.mark.parametrize(
    "error_message",
    [None, "   ", "x" * 1001],
    ids=["missing", "blank", "too-long"],
)
def test_error_transition_rejects_invalid_message_without_mutation(
    db,
    repository,
    error_message,
) -> None:
    document = create_document(db, repository, "tenant-a", "5" * 64)
    move_to_status(db, repository, document, "tenant-a", "processing")

    with pytest.raises(repository.InvalidDocumentErrorMessageError):
        repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=document.id,
            target_status="error",
            error_message=error_message,
        )

    assert document.status == "processing"
    assert document.error_message is None
    assert document.processed_at is None


def test_unknown_status_is_rejected_without_mutation(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "6" * 64)

    with pytest.raises(repository.InvalidDocumentTransitionError):
        repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=document.id,
            target_status="unknown",
        )

    assert document.status == "pending"


def test_error_message_is_rejected_outside_error_transition(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "7" * 64)

    with pytest.raises(repository.InvalidDocumentErrorMessageError):
        repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=document.id,
            target_status="processing",
            error_message="Mensagem indevida.",
        )

    assert document.status == "pending"
    assert document.error_message is None


@pytest.mark.parametrize(
    ("initial_status", "target_status"),
    [
        ("pending", "ready"),
        ("pending", "error"),
        ("processing", "pending"),
        ("ready", "processing"),
        ("error", "processing"),
    ],
)
def test_invalid_transition_does_not_change_document(
    db,
    repository,
    initial_status,
    target_status,
) -> None:
    sha256 = (initial_status + target_status).encode().hex().ljust(64, "0")[:64]
    document = create_document(db, repository, "tenant-a", sha256)
    move_to_status(db, repository, document, "tenant-a", initial_status)
    original_processed_at = document.processed_at
    original_error_message = document.error_message

    with pytest.raises(repository.InvalidDocumentTransitionError):
        repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=document.id,
            target_status=repository.DocumentStatus(target_status),
            error_message="erro" if target_status == "error" else None,
        )

    assert document.status == initial_status
    assert document.processed_at == original_processed_at
    assert document.error_message == original_error_message


def test_other_tenant_cannot_transition_document(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "1" * 64)

    with pytest.raises(repository.DocumentNotFoundError):
        repository.transition_document_status(
            db,
            tenant_id="tenant-b",
            document_id=document.id,
            target_status=repository.DocumentStatus.PROCESSING,
        )

    assert document.status == "pending"


def test_other_tenant_cannot_delete_document(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "4" * 64)
    move_to_status(db, repository, document, "tenant-a", "ready")

    assert repository.delete_document(
        db,
        tenant_id="tenant-b",
        document_id=document.id,
    ) is False
    assert repository.get_document(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
    ) is document


def test_chunks_are_replaced_in_order_with_consistent_count(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "2" * 64)
    chunks = repository.replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=[
            repository.DocumentChunkData(content="Primeiro", page_start=1, page_end=1),
            repository.DocumentChunkData(content="Segundo", page_start=2, page_end=2),
            repository.DocumentChunkData(content="Terceiro", page_start=3, page_end=3),
        ],
    )

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert [chunk.content for chunk in chunks] == ["Primeiro", "Segundo", "Terceiro"]
    assert len({chunk.chunk_index for chunk in chunks}) == len(chunks)
    assert document.chunk_count == 3
    assert all(chunk.tenant_id == "tenant-a" for chunk in chunks)

    replacement = repository.replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=[
            repository.DocumentChunkData(content="Novo primeiro"),
            repository.DocumentChunkData(content="Novo segundo"),
        ],
    )
    assert [chunk.chunk_index for chunk in replacement] == [0, 1]
    assert [chunk.content for chunk in replacement] == ["Novo primeiro", "Novo segundo"]
    assert document.chunk_count == 2


def test_other_tenant_cannot_replace_or_list_chunks(db, repository) -> None:
    document = create_document(db, repository, "tenant-a", "3" * 64)

    with pytest.raises(repository.DocumentNotFoundError):
        repository.replace_document_chunks(
            db,
            tenant_id="tenant-b",
            document_id=document.id,
            chunks=[repository.DocumentChunkData(content="Tentativa indevida")],
        )

    assert repository.list_document_chunks(
        db,
        tenant_id="tenant-b",
        document_id=document.id,
    ) == []
    assert document.chunk_count == 0


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_delete_is_blocked_while_document_is_active(db, repository, status) -> None:
    sha256 = (status * 8).ljust(64, "0")[:64]
    document = create_document(db, repository, "tenant-a", sha256)
    move_to_status(db, repository, document, "tenant-a", status)

    with pytest.raises(repository.DocumentDeletionBlockedError):
        repository.delete_document(
            db,
            tenant_id="tenant-a",
            document_id=document.id,
        )

    assert repository.get_document(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
    ) is document


@pytest.mark.parametrize("status", ["ready", "error"])
def test_terminal_document_deletion_cascades_chunks(db, repository, status) -> None:
    sha256 = ("delete-" + status).encode().hex().ljust(64, "0")[:64]
    document = create_document(db, repository, "tenant-a", sha256)
    move_to_status(db, repository, document, "tenant-a", status)
    repository.replace_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
        chunks=[repository.DocumentChunkData(content="Chunk auditavel")],
    )

    assert repository.delete_document(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
    ) is True
    assert repository.get_document(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
    ) is None
    assert repository.list_document_chunks(
        db,
        tenant_id="tenant-a",
        document_id=document.id,
    ) == []


def test_session_rollback_leaves_no_partial_document_or_chunks(
    quick_test_context,
    repository,
) -> None:
    session = quick_test_context.session_factory()
    try:
        document = create_document(session, repository, "tenant-rollback", "9" * 64)
        document_id = document.id

        with pytest.raises(IntegrityError):
            repository.replace_document_chunks(
                session,
                tenant_id="tenant-rollback",
                document_id=document.id,
                chunks=[
                    repository.DocumentChunkData(content="Valido", page_start=1),
                    repository.DocumentChunkData(content="Invalido", page_start=0),
                ],
            )

        session.rollback()

        assert repository.list_documents(session, tenant_id="tenant-rollback") == []
        assert repository.list_document_chunks(
            session,
            tenant_id="tenant-rollback",
            document_id=document_id,
        ) == []
    finally:
        session.close()
