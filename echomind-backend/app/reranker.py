"""Reranking isolado e injetavel para candidatos ja recuperados."""

from __future__ import annotations

import asyncio
import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Sequence

from langchain_core.documents import Document


class Reranker(Protocol):
    """Contrato minimo de pontuacao; scores maiores indicam maior relevancia."""

    def score(self, query: str, documents: Sequence[str]) -> Sequence[float]: ...


class RerankerBusyError(RuntimeError):
    """Indica que uma inferencia anterior ainda ocupa a capacidade limitada."""


class RerankerExecutionGate:
    """Mantem no maximo uma inferencia ativa, inclusive depois de timeout."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-reranker")
        self._lock = threading.Lock()
        self._active: Future[Sequence[float]] | None = None

    def submit(
        self,
        reranker: Reranker,
        query: str,
        documents: Sequence[str],
    ) -> Future[Sequence[float]]:
        with self._lock:
            if self._active is not None and not self._active.done():
                raise RerankerBusyError("Reranker ocupado por inferencia anterior.")
            future = self._executor.submit(reranker.score, query, documents)
            self._active = future
        future.add_done_callback(self._release)
        return future

    def _release(self, future: Future[Sequence[float]]) -> None:
        with self._lock:
            if self._active is future:
                self._active = None

    def shutdown(self) -> None:
        """Libera o executor; destinado a runners/testes com gate proprio."""
        self._executor.shutdown(wait=True, cancel_futures=True)


_DEFAULT_EXECUTION_GATE = RerankerExecutionGate()


def rank_documents_by_scores(
    candidates: Sequence[Document],
    scores: Sequence[float],
    *,
    top_k: int,
) -> list[Document]:
    """Valida scores e aplica a mesma ordenacao estavel no runtime e no eval."""
    if len(scores) != len(candidates):
        raise ValueError("Reranker retornou quantidade de scores diferente dos candidatos.")

    normalized_scores: list[float] = []
    for score in scores:
        if isinstance(score, bool):
            raise ValueError("Reranker retornou score booleano invalido.")
        numeric_score = float(score)
        if not math.isfinite(numeric_score):
            raise ValueError("Reranker retornou score nao finito.")
        normalized_scores.append(numeric_score)

    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (-normalized_scores[item[0]], item[0]),
    )
    return [document for _index, document in ranked[:top_k]]


@dataclass(frozen=True)
class FastEmbedCrossEncoderReranker:
    """Cross-encoder ONNX local, carregado sob demanda pelo FastEmbed."""

    model_name: str
    cache_dir: str
    allow_model_download: bool = False

    def score(self, query: str, documents: Sequence[str]) -> Sequence[float]:
        try:
            model = _load_cross_encoder(
                self.model_name,
                self.cache_dir,
                self.allow_model_download,
            )
        except ValueError as exc:
            raise RuntimeError(
                "Modelo do reranker ausente ou indisponivel no cache configurado."
            ) from exc
        return list(model.rerank(query, documents))


@lru_cache(maxsize=4)
def _load_cross_encoder(model_name: str, cache_dir: str, allow_model_download: bool):
    """Mantem uma unica sessao ONNX por configuracao no processo."""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(
        model_name=model_name,
        cache_dir=cache_dir,
        lazy_load=True,
        local_files_only=not allow_model_download,
    )


async def rerank_documents(
    query: str,
    candidates: Sequence[Document],
    *,
    reranker: Reranker,
    candidate_limit: int,
    top_k: int,
    max_chars: int,
    timeout_seconds: float,
    execution_gate: RerankerExecutionGate | None = None,
) -> list[Document]:
    """Pontua candidatos limitados sem modificar conteudo ou metadata."""
    limited = list(candidates[:candidate_limit])
    if not limited or top_k <= 0:
        return []

    texts = [document.page_content[:max_chars] for document in limited]
    gate = execution_gate or _DEFAULT_EXECUTION_GATE
    concurrent_future = gate.submit(reranker, query, texts)
    scores = await asyncio.wait_for(
        asyncio.shield(asyncio.wrap_future(concurrent_future)),
        timeout=timeout_seconds,
    )
    return rank_documents_by_scores(limited, scores, top_k=top_k)
