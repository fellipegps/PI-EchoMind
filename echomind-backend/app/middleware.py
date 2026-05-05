"""
middleware.py – Middlewares da aplicação EchoMind

1. TimingMiddleware   → mede tempo real de cada request e salva nas métricas
2. RequestLogMiddleware → loga method, path, status e latência
3. Funções auxiliares para o Dashboard usar tempos reais
"""

from __future__ import annotations

import time
import logging
import statistics
from collections import deque
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("echomind.middleware")


# ──────────────────────────────────────────────────────────────────────────────
#  Armazenamento em memória das métricas de latência
#  (em produção, substitua por Redis ou Prometheus)
# ──────────────────────────────────────────────────────────────────────────────

class LatencyStore:
    """
    Circular buffer dos últimos N tempos de resposta do /chat.
    Thread-safe para leituras e escritas simples (GIL do CPython).
    """
    MAX_SAMPLES = 500

    def __init__(self):
        self._samples: deque[float] = deque(maxlen=self.MAX_SAMPLES)
        self._total_requests: int = 0
        self._error_count: int = 0

    def record(self, duration_ms: float, is_error: bool = False):
        self._samples.append(duration_ms)
        self._total_requests += 1
        if is_error:
            self._error_count += 1

    @property
    def avg_ms(self) -> float:
        if not self._samples:
            return 0.0
        return statistics.mean(self._samples)

    @property
    def p95_ms(self) -> float:
        if not self._samples:
            return 0.0
        sorted_s = sorted(self._samples)
        idx = int(len(sorted_s) * 0.95)
        return sorted_s[min(idx, len(sorted_s) - 1)]

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def error_rate(self) -> float:
        if self._total_requests == 0:
            return 0.0
        return self._error_count / self._total_requests

    def summary(self) -> dict:
        avg = self.avg_ms
        if avg < 1000:
            avg_str = f"~{avg:.0f}ms"
        else:
            avg_str = f"~{avg/1000:.1f}s"

        return {
            "avg_response_time": avg_str,
            "p95_response_time": f"~{self.p95_ms:.0f}ms",
            "total_requests": self._total_requests,
            "error_rate": f"{self.error_rate:.1%}",
            "samples": len(self._samples),
        }


# Singleton global — importado pelo crud.py
latency_store = LatencyStore()


# ──────────────────────────────────────────────────────────────────────────────
#  Timing Middleware
# ──────────────────────────────────────────────────────────────────────────────

class TimingMiddleware(BaseHTTPMiddleware):
    """
    Mede o tempo de resposta de cada request.
    Injeta o header X-Process-Time na resposta.
    Registra métricas de /chat no LatencyStore.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        is_error = False

        try:
            response = await call_next(request)
            if response.status_code >= 500:
                is_error = True
            return response
        except Exception as exc:
            is_error = True
            raise exc
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Registra métricas apenas do endpoint de chat
            if request.url.path == "/chat":
                latency_store.record(elapsed_ms, is_error=is_error)

            # Injeta header de timing (útil para debug no front)
            # Nota: não podemos modificar a response aqui pois já foi enviada
            # em streaming — apenas logamos.
            logger.info(
                f"{request.method} {request.url.path} "
                f"→ {elapsed_ms:.1f}ms"
                + (" [ERRO]" if is_error else "")
            )


# ──────────────────────────────────────────────────────────────────────────────
#  Request Log Middleware (mais detalhado)
# ──────────────────────────────────────────────────────────────────────────────

class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    Loga cada request com método, path, status code e duração.
    Ignora /health para não poluir os logs.
    """

    IGNORE_PATHS = {"/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.IGNORE_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        client = request.client.host if request.client else "unknown"

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"[{client}] {request.method} {request.url.path} "
            f"HTTP/{response.status_code} {elapsed_ms:.1f}ms"
        )

        # Adiciona header de latência na resposta (visível no DevTools)
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
