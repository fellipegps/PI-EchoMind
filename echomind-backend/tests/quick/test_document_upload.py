"""Contrato multipart e agendamento do upload documental administrativo."""

from __future__ import annotations

from hashlib import sha256
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


TXT_MIME_TYPE = "text/plain"
PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@pytest.fixture()
def upload_task_spy(monkeypatch) -> MagicMock:
    from app import main

    task = MagicMock()
    monkeypatch.setattr(main, "process_document", task)
    return task


def _post_upload(
    client: TestClient,
    *,
    filename: str = "norma.txt",
    content: bytes = b"Conteudo institucional sintetico.",
    mime_type: str = TXT_MIME_TYPE,
    data: dict[str, str] | None = None,
):
    return client.post(
        "/documents/upload",
        files={"file": (filename, content, mime_type)},
        data=data or {},
    )


def _request_without_auth(client, quick_test_context, request):
    app = quick_test_context.app
    auth_dependency = quick_test_context.get_current_user
    override = app.dependency_overrides.pop(auth_dependency)
    try:
        return request()
    finally:
        app.dependency_overrides[auth_dependency] = override


def test_upload_requires_authentication(client: TestClient, quick_test_context) -> None:
    response = _request_without_auth(
        client,
        quick_test_context,
        lambda: _post_upload(client),
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("norma.txt", TXT_MIME_TYPE),
        ("norma.pdf", PDF_MIME_TYPE),
        ("norma.docx", DOCX_MIME_TYPE),
    ],
    ids=["txt", "pdf", "docx"],
)
def test_valid_upload_returns_202_and_schedules_exactly_one_task(
    client: TestClient,
    db,
    upload_task_spy: MagicMock,
    filename: str,
    mime_type: str,
) -> None:
    from app.document_repository import get_document

    original_bytes = f"bytes:{filename}".encode()
    response = _post_upload(
        client,
        filename=filename,
        content=original_bytes,
        mime_type=mime_type,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    document_id = response.json()["id"]
    stored = get_document(db, tenant_id="test-admin", document_id=document_id)
    assert stored is not None
    assert stored.tenant_id == "test-admin"
    upload_task_spy.assert_called_once_with(
        document_id=document_id,
        tenant_id="test-admin",
        content=original_bytes,
    )


def test_tenant_id_multipart_field_is_rejected(
    client: TestClient,
    upload_task_spy: MagicMock,
) -> None:
    response = _post_upload(
        client,
        data={"tenant_id": "outro-tenant"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "tenant_id não é permitido."}
    upload_task_spy.assert_not_called()


def test_multiple_files_are_rejected(
    client: TestClient,
    upload_task_spy: MagicMock,
) -> None:
    response = client.post(
        "/documents/upload",
        files=[
            ("file", ("primeiro.txt", b"primeiro", TXT_MIME_TYPE)),
            ("file", ("segundo.txt", b"segundo", TXT_MIME_TYPE)),
        ],
    )

    assert response.status_code == 400
    upload_task_spy.assert_not_called()


@pytest.mark.parametrize(
    ("filename", "mime_type"),
    [
        ("executavel.exe", "application/octet-stream"),
        ("norma.txt", PDF_MIME_TYPE),
    ],
    ids=["extension", "mime"],
)
def test_unsupported_extension_or_mime_returns_415(
    client: TestClient,
    upload_task_spy: MagicMock,
    filename: str,
    mime_type: str,
) -> None:
    response = _post_upload(
        client,
        filename=filename,
        mime_type=mime_type,
    )

    assert response.status_code == 415
    upload_task_spy.assert_not_called()


def test_oversized_upload_returns_413(
    client: TestClient,
    monkeypatch,
    upload_task_spy: MagicMock,
) -> None:
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", "1")

    response = _post_upload(client, content=b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    upload_task_spy.assert_not_called()


def test_empty_upload_returns_400(
    client: TestClient,
    upload_task_spy: MagicMock,
) -> None:
    response = _post_upload(client, content=b"")

    assert response.status_code == 400
    upload_task_spy.assert_not_called()


def test_duplicate_is_scoped_to_authenticated_tenant(
    client: TestClient,
    db,
    upload_task_spy: MagicMock,
) -> None:
    from app.document_repository import DocumentCreateData, create_document

    content = b"Mesmo hash entre tenants."
    digest = sha256(content).hexdigest()
    create_document(
        db,
        tenant_id="outro-tenant",
        data=DocumentCreateData(
            filename="outro.txt",
            mime_type=TXT_MIME_TYPE,
            size_bytes=len(content),
            sha256=digest,
        ),
    )
    db.commit()

    allowed = _post_upload(client, content=content)
    duplicate = _post_upload(client, content=content)

    assert allowed.status_code == 202
    assert duplicate.status_code == 409
    upload_task_spy.assert_called_once()


def test_filename_is_sanitized_before_persistence(
    client: TestClient,
    db,
    upload_task_spy: MagicMock,
) -> None:
    from app.document_repository import get_document

    response = _post_upload(client, filename="../../norma.txt")

    assert response.status_code == 202
    assert response.json()["filename"] == "norma.txt"
    stored = get_document(
        db,
        tenant_id="test-admin",
        document_id=response.json()["id"],
    )
    assert stored.filename == "norma.txt"


def test_optional_metadata_is_normalized_and_persisted(
    client: TestClient,
    db,
    upload_task_spy: MagicMock,
) -> None:
    from app.document_repository import get_document

    response = _post_upload(
        client,
        data={
            "document_type": "  regulamento  ",
            "document_number": "  42/2026  ",
            "department": "   ",
            "published_at": "2026-08-24",
            "valid_until": "2027-08-24",
        },
    )

    assert response.status_code == 202
    stored = get_document(
        db,
        tenant_id="test-admin",
        document_id=response.json()["id"],
    )
    assert stored.document_type == "regulamento"
    assert stored.document_number == "42/2026"
    assert stored.department is None
    assert stored.published_at.isoformat() == "2026-08-24"
    assert stored.valid_until.isoformat() == "2027-08-24"


def test_background_task_receives_durable_bytes_not_upload_file(
    client: TestClient,
    monkeypatch,
) -> None:
    from app import main

    captured: dict[str, object] = {}

    def capture_task(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(main, "process_document", capture_task)
    original_bytes = b"Bytes copiados antes do fechamento."

    response = _post_upload(client, content=original_bytes)

    assert response.status_code == 202
    assert captured["content"] == original_bytes
    assert type(captured["content"]) is bytes
    assert set(captured) == {"document_id", "tenant_id", "content"}


def test_internal_persistence_error_does_not_leak_details(
    client: TestClient,
    monkeypatch,
    upload_task_spy: MagicMock,
) -> None:
    from app import main

    monkeypatch.setattr(
        main,
        "create_document",
        MagicMock(side_effect=RuntimeError("segredo interno e stack trace")),
    )

    response = _post_upload(client)

    assert response.status_code == 500
    assert response.json() == {"detail": "Não foi possível criar o documento."}
    assert "segredo interno" not in response.text
    upload_task_spy.assert_not_called()


def test_parser_failure_in_background_marks_document_as_error(
    client: TestClient,
    db,
    monkeypatch,
) -> None:
    from app import document_processing
    from app.document_repository import get_document

    processing_sessions = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db.connection(),
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(document_processing, "SessionLocal", processing_sessions)
    monkeypatch.setitem(
        document_processing._EXTRACTORS,
        TXT_MIME_TYPE,
        MagicMock(side_effect=RuntimeError("falha sintetica do parser")),
    )

    response = _post_upload(client, content=b"Conteudo que falhara no parser.")

    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    db.expire_all()
    stored = get_document(
        db,
        tenant_id="test-admin",
        document_id=response.json()["id"],
    )
    assert stored.status == "error"
    assert stored.error_message == "Falha ao extrair o documento."
