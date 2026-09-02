"""Rate limiting de chat e upload com store e relogio locais controlados."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.rate_limit import (
    InMemoryFixedWindowRateLimiter,
    InvalidRateLimitConfigurationError,
    RateLimitConfig,
    RateLimitPolicy,
    _opaque_key,
    enforce_chat_rate_limit,
    load_rate_limit_config,
    rate_limiter,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _config(
    *,
    chat_requests: int = 2,
    chat_window: int = 60,
    upload_requests: int = 2,
    upload_window: int = 60,
) -> RateLimitConfig:
    return RateLimitConfig(
        chat=RateLimitPolicy(chat_requests, chat_window),
        upload=RateLimitPolicy(upload_requests, upload_window),
    )


def _chat(client: TestClient, tenant_id: str = "tenant-do-payload"):
    return client.post(
        "/chat",
        json={"message": "Qual e o horario?", "tenant_id": tenant_id},
    )


def _upload(client: TestClient, content: bytes):
    return client.post(
        "/documents/upload",
        files={"file": ("norma.txt", content, "text/plain")},
    )


@pytest.fixture(autouse=True)
def clear_global_rate_limiter():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


@pytest.fixture()
def upload_task_spy(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    from app import main

    task = MagicMock()
    monkeypatch.setattr(main, "process_document", task)
    return task


def test_fixed_window_allows_limit_rejects_excess_and_resets() -> None:
    clock = FakeClock()
    limiter = InMemoryFixedWindowRateLimiter(clock=clock)
    policy = RateLimitPolicy(max_requests=2, window_seconds=10)

    first = limiter.consume(scope="chat", key="opaque-a", policy=policy)
    second = limiter.consume(scope="chat", key="opaque-a", policy=policy)
    rejected = limiter.consume(scope="chat", key="opaque-a", policy=policy)

    assert first.allowed is True and first.remaining == 1
    assert second.allowed is True and second.remaining == 0
    assert rejected.allowed is False
    assert rejected.retry_after_seconds == 10

    clock.advance(9)
    almost_reset = limiter.consume(scope="chat", key="opaque-a", policy=policy)
    assert almost_reset.allowed is False
    assert almost_reset.retry_after_seconds == 1

    clock.advance(1)
    after_reset = limiter.consume(scope="chat", key="opaque-a", policy=policy)
    assert after_reset.allowed is True
    assert after_reset.remaining == 1


def test_scopes_and_opaque_keys_have_independent_quotas() -> None:
    limiter = InMemoryFixedWindowRateLimiter(clock=lambda: 100.0)
    policy = RateLimitPolicy(max_requests=1, window_seconds=60)

    assert limiter.consume(scope="chat", key="key-a", policy=policy).allowed
    assert not limiter.consume(scope="chat", key="key-a", policy=policy).allowed
    assert limiter.consume(scope="upload", key="key-a", policy=policy).allowed
    assert limiter.consume(scope="chat", key="key-b", policy=policy).allowed

    raw_identifier = "usuario-identificavel"
    opaque_key = _opaque_key("authenticated-user", raw_identifier)
    assert raw_identifier not in opaque_key
    assert len(opaque_key) == 64


def test_public_chat_uses_direct_client_ip_and_ignores_forwarded_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import rate_limit

    monkeypatch.setattr(rate_limit, "RATE_LIMIT_CONFIG", _config(chat_requests=1))

    def request_from(ip: str, forwarded_for: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/chat",
                "headers": [
                    (b"x-forwarded-for", forwarded_for.encode("ascii")),
                ],
                "client": (ip, 12345),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )

    enforce_chat_rate_limit(request_from("192.0.2.10", "203.0.113.1"))
    with pytest.raises(HTTPException) as rejected:
        enforce_chat_rate_limit(request_from("192.0.2.10", "203.0.113.2"))
    enforce_chat_rate_limit(request_from("192.0.2.11", "203.0.113.1"))

    assert rejected.value.status_code == 429


def test_configuration_loads_independent_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", "7")
    monkeypatch.setenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "11")
    monkeypatch.setenv("UPLOAD_RATE_LIMIT_REQUESTS", "3")
    monkeypatch.setenv("UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "120")

    assert load_rate_limit_config() == _config(
        chat_requests=7,
        chat_window=11,
        upload_requests=3,
        upload_window=120,
    )


@pytest.mark.parametrize("invalid_value", ("", "0", "-1", "1.5", "abc"))
def test_invalid_configuration_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    monkeypatch.setenv("CHAT_RATE_LIMIT_REQUESTS", invalid_value)

    with pytest.raises(
        InvalidRateLimitConfigurationError,
        match="CHAT_RATE_LIMIT_REQUESTS",
    ):
        load_rate_limit_config()


def test_chat_rejects_above_limit_without_using_payload_tenant_as_key(
    client: TestClient,
    fake_rag_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main, rate_limit

    monkeypatch.setattr(rate_limit, "RATE_LIMIT_CONFIG", _config(chat_requests=2))
    rag_factory = MagicMock(return_value=fake_rag_engine)
    monkeypatch.setattr(main, "get_rag_engine", rag_factory)

    first = _chat(client, tenant_id="tenant-a-fornecido-pelo-cliente")
    second = _chat(client, tenant_id="tenant-b-fornecido-pelo-cliente")
    rejected = _chat(client, tenant_id="tenant-c-fornecido-pelo-cliente")

    assert first.status_code == 200
    assert second.status_code == 200
    assert rejected.status_code == 429
    assert rejected.json() == {
        "detail": "Limite de requisicoes excedido. Tente novamente mais tarde."
    }
    assert int(rejected.headers["Retry-After"]) >= 1
    assert rag_factory.call_count == 2


def test_chat_and_upload_limits_are_independent_and_rejection_skips_costly_work(
    client: TestClient,
    fake_rag_engine,
    upload_task_spy: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main, rate_limit

    monkeypatch.setattr(
        rate_limit,
        "RATE_LIMIT_CONFIG",
        _config(chat_requests=1, upload_requests=2),
    )
    rag_factory = MagicMock(return_value=fake_rag_engine)
    monkeypatch.setattr(main, "get_rag_engine", rag_factory)
    read_spy = MagicMock(side_effect=main.read_limited_bytes)
    monkeypatch.setattr(main, "read_limited_bytes", read_spy)

    assert _chat(client).status_code == 200
    assert _chat(client).status_code == 429
    assert _upload(client, b"conteudo um").status_code == 202
    assert _upload(client, b"conteudo dois").status_code == 202
    rejected_upload = _upload(client, b"conteudo tres")

    assert rejected_upload.status_code == 429
    assert int(rejected_upload.headers["Retry-After"]) >= 1
    assert rag_factory.call_count == 1
    assert read_spy.call_count == 2
    assert upload_task_spy.call_count == 2


def test_authenticated_upload_users_have_isolated_quotas(
    client: TestClient,
    quick_test_context,
    upload_task_spy: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import rate_limit

    monkeypatch.setattr(rate_limit, "RATE_LIMIT_CONFIG", _config(upload_requests=1))
    app = quick_test_context.app

    def use_authenticated_user(user_id: str) -> None:
        app.dependency_overrides[quick_test_context.get_current_user] = lambda: (
            quick_test_context.current_user_type(
                id=user_id,
                email=f"{user_id}@example.test",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
        )

    use_authenticated_user("usuario-a")
    assert _upload(client, b"usuario a").status_code == 202
    use_authenticated_user("usuario-b")
    assert _upload(client, b"usuario b").status_code == 202
    use_authenticated_user("usuario-a")
    rejected = _upload(client, b"usuario a novamente")

    assert rejected.status_code == 429
    assert upload_task_spy.call_count == 2


def test_health_never_consumes_rate_limit_quota(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import rate_limit

    monkeypatch.setattr(
        rate_limit,
        "RATE_LIMIT_CONFIG",
        _config(chat_requests=1, upload_requests=1),
    )

    for _ in range(5):
        assert client.get("/health").status_code == 200
