"""Testes da allowlist configuravel de CORS, sem chamadas externas."""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.cors_config import (
    CORS_ALLOW_HEADERS,
    CORS_ALLOW_METHODS,
    DEFAULT_ALLOWED_ORIGINS,
    InvalidCORSConfigurationError,
    configure_cors,
    parse_allowed_origins,
)


ALLOWED_ORIGIN = "https://app.example.test"
BLOCKED_ORIGIN = "https://blocked.example.test"


def _cors_client(origins: str = ALLOWED_ORIGIN) -> TestClient:
    application = FastAPI()
    configure_cors(application, origins)

    @application.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(application)


def test_parse_one_or_multiple_origins_with_whitespace_and_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        " https://one.example.test , http://localhost:3000, https://one.example.test ",
    )

    assert parse_allowed_origins() == (
        "https://one.example.test",
        "http://localhost:3000",
    )
    assert parse_allowed_origins("https://single.example.test") == (
        "https://single.example.test",
    )


def test_missing_configuration_uses_only_restricted_local_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    assert parse_allowed_origins() == DEFAULT_ALLOWED_ORIGINS
    assert "*" not in DEFAULT_ALLOWED_ORIGINS


@pytest.mark.parametrize(
    "raw_value",
    (
        "",
        "https://one.example.test,",
        "*",
        "https://*.example.test",
        "ftp://example.test",
        "example.test",
        "https://invalid host.example.test",
        "https://user:secret@example.test",
        "https://example.test/path",
        "https://example.test?token=secret",
        "https://example.test/#fragment",
        "http://example.test:invalid",
    ),
)
def test_invalid_configuration_fails_clearly(raw_value: str) -> None:
    with pytest.raises(
        InvalidCORSConfigurationError,
        match="ALLOWED_ORIGINS",
    ):
        parse_allowed_origins(raw_value)


def test_invalid_configuration_fails_before_registering_middleware() -> None:
    application = FastAPI()

    with pytest.raises(InvalidCORSConfigurationError, match="ALLOWED_ORIGINS"):
        configure_cors(application, "*")

    assert all(item.cls is not CORSMiddleware for item in application.user_middleware)


def test_allowed_origin_receives_exact_headers_with_credentials() -> None:
    with _cors_client() as client:
        response = client.get(
            "/probe",
            headers={"Origin": ALLOWED_ORIGIN, "Cookie": "session=test"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"
    assert response.headers["access-control-allow-origin"] != "*"


def test_blocked_origin_receives_no_cors_authorization() -> None:
    with _cors_client() as client:
        response = client.get(
            "/probe",
            headers={"Origin": BLOCKED_ORIGIN},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_valid_preflight_allows_only_configured_methods_and_headers() -> None:
    with _cors_client() as client:
        response = client.options(
            "/probe",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert set(response.headers["access-control-allow-methods"].split(", ")) == set(
        CORS_ALLOW_METHODS
    )
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    for header in CORS_ALLOW_HEADERS:
        assert header.lower() in allowed_headers


@pytest.mark.parametrize(
    ("origin", "method", "headers"),
    (
        (BLOCKED_ORIGIN, "GET", "Authorization"),
        (ALLOWED_ORIGIN, "TRACE", "Authorization"),
        (ALLOWED_ORIGIN, "GET", "X-Admin-Secret"),
    ),
)
def test_invalid_preflight_is_rejected(
    origin: str,
    method: str,
    headers: str,
) -> None:
    with _cors_client() as client:
        response = client.options(
            "/probe",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": headers,
            },
        )

    assert response.status_code == 400
    if origin == BLOCKED_ORIGIN:
        assert "access-control-allow-origin" not in response.headers


def test_main_app_registers_restricted_cors_middleware(
    quick_test_context,
) -> None:
    middleware = next(
        item
        for item in quick_test_context.app.user_middleware
        if item.cls is CORSMiddleware
    )

    assert middleware.kwargs["allow_credentials"] is True
    assert "*" not in middleware.kwargs["allow_origins"]
    assert tuple(middleware.kwargs["allow_methods"]) == CORS_ALLOW_METHODS
    assert tuple(middleware.kwargs["allow_headers"]) == CORS_ALLOW_HEADERS
