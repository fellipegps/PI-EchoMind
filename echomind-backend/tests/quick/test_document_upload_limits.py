"""Limite efetivo divulgado a UI e validacao independente do upload."""

from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("configured,expected_mb", [(None, 10), (" ", 10), ("2", 2), ("20", 20)])
def test_upload_limits_reports_only_effective_bytes(client, monkeypatch, configured, expected_mb):
    if configured is None:
        monkeypatch.delenv("MAX_DOCUMENT_SIZE_MB", raising=False)
    else:
        monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", configured)
    monkeypatch.setenv("GROQ_API_KEY", "private-not-for-response")
    response = client.get("/documents/upload-limits")
    assert response.status_code == 200
    assert response.json() == {"max_document_size_bytes": expected_mb * 1024 * 1024}
    assert response.headers["cache-control"] == "no-store"


def test_upload_limits_requires_authentication(client, quick_test_context):
    app = quick_test_context.app
    auth = quick_test_context.get_current_user
    override = app.dependency_overrides.pop(auth)
    try:
        assert client.get("/documents/upload-limits").status_code == 403
    finally:
        app.dependency_overrides[auth] = override


@pytest.mark.parametrize("configured", ["0", "-1", "invalid", "1.5"])
def test_invalid_server_limit_has_safe_error(client, monkeypatch, configured):
    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", configured)
    response = client.get("/documents/upload-limits")
    assert response.status_code == 500
    assert response.json() == {"detail": "Configuração inválida do limite de upload."}


@pytest.mark.parametrize("limit_mb", [2, 20])
def test_upload_enforces_advertised_limit_without_trusting_ui(client, monkeypatch, limit_mb):
    from app import main

    monkeypatch.setenv("MAX_DOCUMENT_SIZE_MB", str(limit_mb))
    task = MagicMock()
    monkeypatch.setattr(main, "process_document", task)
    limit = client.get("/documents/upload-limits").json()["max_document_size_bytes"]
    assert limit == limit_mb * 1024 * 1024
    accepted = client.post("/documents/upload", files={"file": ("at-limit.txt", b"x" * limit, "text/plain")})
    assert accepted.status_code == 202
    assert accepted.json()["size_bytes"] == limit
    task.assert_called_once()
    rejected = client.post("/documents/upload", files={"file": ("above-limit.txt", b"y" * (limit + 1), "text/plain")})
    assert rejected.status_code == 413
    task.assert_called_once()
