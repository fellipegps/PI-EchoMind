"""Contratos unitarios da fronteira de validacao documental."""

from __future__ import annotations

from io import BytesIO

import pytest


@pytest.fixture()
def ingestion():
    from app import document_ingestion

    return document_ingestion


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("regulamento.pdf", "application/pdf"),
        ("notas.TXT", "text/plain; charset=utf-8"),
        (
            "ata.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_allowed_extension_and_matching_mime_are_accepted(
    ingestion, filename, mime_type
) -> None:
    document = ingestion.validate_document_bytes(
        filename=filename,
        mime_type=mime_type,
        content=b"conteudo original",
        max_size_bytes=100,
    )

    assert document.filename == filename
    assert document.mime_type == mime_type.split(";", maxsplit=1)[0].lower()


@pytest.mark.parametrize(
    ("filename", "mime_type", "error_name"),
    [
        ("arquivo.exe", "application/octet-stream", "UnsupportedDocumentTypeError"),
        ("arquivo.pdf", "text/plain", "InvalidDocumentMimeTypeError"),
        ("arquivo.txt", "application/pdf", "InvalidDocumentMimeTypeError"),
        ("arquivo.docx", None, "InvalidDocumentMimeTypeError"),
    ],
)
def test_invalid_extension_or_mime_combination_is_rejected(
    ingestion, filename, mime_type, error_name
) -> None:
    with pytest.raises(getattr(ingestion, error_name)):
        ingestion.validate_document_bytes(
            filename=filename,
            mime_type=mime_type,
            content=b"conteudo original",
            max_size_bytes=100,
        )


def test_empty_document_is_rejected(ingestion) -> None:
    with pytest.raises(ingestion.EmptyDocumentError):
        ingestion.validate_document_bytes(
            filename="vazio.txt",
            mime_type="text/plain",
            content=b"",
            max_size_bytes=1,
        )


def test_document_at_limit_is_accepted_and_above_limit_is_rejected(ingestion) -> None:
    accepted = ingestion.validate_document_bytes(
        filename="limite.txt",
        mime_type="text/plain",
        content=b"12345",
        max_size_bytes=5,
    )

    assert accepted.size_bytes == 5
    with pytest.raises(ingestion.DocumentTooLargeError):
        ingestion.validate_document_bytes(
            filename="excesso.txt",
            mime_type="text/plain",
            content=b"123456",
            max_size_bytes=5,
        )


def test_max_document_size_is_configurable(monkeypatch, ingestion) -> None:
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "2")

    assert ingestion.get_max_document_size_bytes() == 2 * 1024 * 1024
    with pytest.raises(ingestion.InvalidDocumentConfigurationError):
        ingestion.get_max_document_size_bytes("zero")


def test_stream_is_read_only_until_the_first_byte_over_the_limit(ingestion) -> None:
    source = BytesIO(b"123456")

    with pytest.raises(ingestion.DocumentTooLargeError):
        ingestion.read_limited_bytes(source, max_size_bytes=5, chunk_size=2)

    assert source.tell() == 6


def test_sha256_is_deterministic_and_sensitive_to_original_bytes(ingestion) -> None:
    first = ingestion.validate_document_bytes(
        filename="original.txt",
        mime_type="text/plain",
        content=b"linha 1\r\nlinha 2",
        max_size_bytes=100,
    )
    same_bytes = ingestion.validate_document_bytes(
        filename="outro-nome.txt",
        mime_type="text/plain",
        content=b"linha 1\r\nlinha 2",
        max_size_bytes=100,
    )
    changed_bytes = ingestion.validate_document_bytes(
        filename="normalizado.txt",
        mime_type="text/plain",
        content=b"linha 1\nlinha 2",
        max_size_bytes=100,
    )

    assert first.sha256 == same_bytes.sha256
    assert first.sha256 != changed_bytes.sha256


@pytest.mark.parametrize(
    ("raw_filename", "expected_filename"),
    [
        ("../../segredo.txt", "segredo.txt"),
        (r"C:\upload\relatorio.pdf", "relatorio.pdf"),
        ("  pasta/ata\x00.docx  ", "ata.docx"),
    ],
)
def test_filename_is_sanitized_to_a_safe_basename(
    ingestion, raw_filename, expected_filename
) -> None:
    assert ingestion.sanitize_filename(raw_filename) == expected_filename


@pytest.mark.parametrize("filename", ["", ".", "..", "../"])
def test_filename_without_safe_basename_is_rejected(ingestion, filename) -> None:
    with pytest.raises(ingestion.InvalidDocumentFilenameError):
        ingestion.sanitize_filename(filename)


@pytest.mark.parametrize("status", ["pending", "processing", "ready"])
def test_active_duplicate_is_rejected_only_inside_the_same_tenant(
    db, ingestion, status
) -> None:
    from app import document_repository

    content = b"mesmo conteudo"
    sha256 = ingestion.validate_document_bytes(
        filename="original.txt",
        mime_type="text/plain",
        content=content,
        max_size_bytes=100,
    ).sha256
    existing_document = document_repository.create_document(
        db,
        tenant_id="tenant-a",
        data=document_repository.DocumentCreateData(
            filename="original.txt",
            mime_type="text/plain",
            size_bytes=len(content),
            sha256=sha256,
        ),
    )
    if status in {"processing", "ready"}:
        document_repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=existing_document.id,
            target_status="processing",
        )
    if status == "ready":
        document_repository.transition_document_status(
            db,
            tenant_id="tenant-a",
            document_id=existing_document.id,
            target_status="ready",
        )

    with pytest.raises(document_repository.DuplicateDocumentError):
        ingestion.validate_document_for_tenant(
            db,
            tenant_id="tenant-a",
            filename="copia.txt",
            mime_type="text/plain",
            content=content,
            max_size_bytes=100,
        )

    other_tenant_document = ingestion.validate_document_for_tenant(
        db,
        tenant_id="tenant-b",
        filename="copia.txt",
        mime_type="text/plain",
        content=content,
        max_size_bytes=100,
    )

    assert other_tenant_document.sha256 == sha256
