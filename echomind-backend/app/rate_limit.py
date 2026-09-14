"""Rate limiting local e deterministico para rotas custosas da API."""

from __future__ import annotations

import hashlib
import heapq
import math
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request, status


DEFAULT_CHAT_RATE_LIMIT_REQUESTS = 20
DEFAULT_CHAT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_UPLOAD_RATE_LIMIT_REQUESTS = 5
DEFAULT_UPLOAD_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_MAX_BUCKETS = 10_000


class InvalidRateLimitConfigurationError(ValueError):
    """Indica limites ausentes ou numericamente invalidos."""


@dataclass(frozen=True)
class RateLimitPolicy:
    max_requests: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitConfig:
    chat: RateLimitPolicy
    upload: RateLimitPolicy
    max_buckets: int = DEFAULT_RATE_LIMIT_MAX_BUCKETS
    instance_count: int = 1


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


@dataclass
class _FixedWindow:
    count: int
    reset_at: float


def _positive_environment_integer(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise InvalidRateLimitConfigurationError(
            f"{name} deve ser um numero inteiro positivo."
        ) from exc
    if value <= 0:
        raise InvalidRateLimitConfigurationError(
            f"{name} deve ser um numero inteiro positivo."
        )
    return value


def load_rate_limit_config() -> RateLimitConfig:
    """Carrega limites independentes e falha cedo para valores invalidos."""
    instance_count = _positive_environment_integer("RATE_LIMIT_INSTANCE_COUNT", 1)
    worker_count = _positive_environment_integer(
        "UVICORN_WORKERS",
        _positive_environment_integer("WEB_CONCURRENCY", 1),
    )
    if instance_count != 1 or worker_count != 1:
        raise InvalidRateLimitConfigurationError(
            "O rate limiter em memoria exige exatamente uma instancia e um worker. "
            "Defina um store compartilhado antes de aumentar RATE_LIMIT_INSTANCE_COUNT, "
            "UVICORN_WORKERS ou WEB_CONCURRENCY."
        )

    return RateLimitConfig(
        chat=RateLimitPolicy(
            max_requests=_positive_environment_integer(
                "CHAT_RATE_LIMIT_REQUESTS",
                DEFAULT_CHAT_RATE_LIMIT_REQUESTS,
            ),
            window_seconds=_positive_environment_integer(
                "CHAT_RATE_LIMIT_WINDOW_SECONDS",
                DEFAULT_CHAT_RATE_LIMIT_WINDOW_SECONDS,
            ),
        ),
        upload=RateLimitPolicy(
            max_requests=_positive_environment_integer(
                "UPLOAD_RATE_LIMIT_REQUESTS",
                DEFAULT_UPLOAD_RATE_LIMIT_REQUESTS,
            ),
            window_seconds=_positive_environment_integer(
                "UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
                DEFAULT_UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
            ),
        ),
        max_buckets=_positive_environment_integer(
            "RATE_LIMIT_MAX_BUCKETS",
            DEFAULT_RATE_LIMIT_MAX_BUCKETS,
        ),
        instance_count=instance_count,
    )


class InMemoryFixedWindowRateLimiter:
    """Store thread-safe por processo, sem prometer coordenacao entre replicas."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = DEFAULT_RATE_LIMIT_MAX_BUCKETS,
    ) -> None:
        if max_buckets <= 0:
            raise InvalidRateLimitConfigurationError(
                "RATE_LIMIT_MAX_BUCKETS deve ser um numero inteiro positivo."
            )
        self._clock = clock
        self._max_buckets = max_buckets
        self._windows: dict[tuple[str, str], _FixedWindow] = {}
        self._expirations: list[tuple[float, tuple[str, str]]] = []
        self._lock = Lock()

    def consume(
        self,
        *,
        scope: str,
        key: str,
        policy: RateLimitPolicy,
    ) -> RateLimitDecision:
        now = self._clock()
        bucket_key = (scope, key)

        with self._lock:
            self._discard_expired(now)
            window = self._windows.get(bucket_key)
            if window is None:
                if len(self._windows) >= self._max_buckets:
                    next_reset = self._expirations[0][0] if self._expirations else now + 1
                    return RateLimitDecision(
                        allowed=False,
                        remaining=0,
                        retry_after_seconds=max(1, math.ceil(next_reset - now)),
                    )
                reset_at = now + policy.window_seconds
                self._windows[bucket_key] = _FixedWindow(
                    count=1,
                    reset_at=reset_at,
                )
                heapq.heappush(self._expirations, (reset_at, bucket_key))
                return RateLimitDecision(
                    allowed=True,
                    remaining=policy.max_requests - 1,
                    retry_after_seconds=policy.window_seconds,
                )

            retry_after = max(1, math.ceil(window.reset_at - now))
            if window.count >= policy.max_requests:
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            window.count += 1
            return RateLimitDecision(
                allowed=True,
                remaining=policy.max_requests - window.count,
                retry_after_seconds=retry_after,
            )

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()
            self._expirations.clear()

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._windows)

    def _discard_expired(self, now: float) -> None:
        while self._expirations and self._expirations[0][0] <= now:
            reset_at, key = heapq.heappop(self._expirations)
            window = self._windows.get(key)
            if window is not None and window.reset_at == reset_at:
                del self._windows[key]


def _opaque_key(namespace: str, identifier: str) -> str:
    safe_identifier = identifier or "unknown"
    return hashlib.sha256(
        f"{namespace}:{safe_identifier}".encode("utf-8")
    ).hexdigest()


def _reject_if_limited(decision: RateLimitDecision) -> None:
    if decision.allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Limite de requisicoes excedido. Tente novamente mais tarde.",
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


RATE_LIMIT_CONFIG = load_rate_limit_config()
rate_limiter = InMemoryFixedWindowRateLimiter(
    max_buckets=RATE_LIMIT_CONFIG.max_buckets,
)


def enforce_chat_rate_limit(request: Request) -> None:
    """Limita o chat publico pelo IP direto, nunca pelo tenant do payload."""
    client_host = request.client.host if request.client else "unknown"
    decision = rate_limiter.consume(
        scope="chat",
        key=_opaque_key("chat-client", client_host),
        policy=RATE_LIMIT_CONFIG.chat,
    )
    _reject_if_limited(decision)


def enforce_upload_rate_limit_for_user(user_id: str) -> None:
    """Limita upload pela identidade validada no backend."""
    decision = rate_limiter.consume(
        scope="documents-upload",
        key=_opaque_key("authenticated-user", user_id),
        policy=RATE_LIMIT_CONFIG.upload,
    )
    _reject_if_limited(decision)
