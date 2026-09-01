"""Reranking isolado e injetavel para candidatos ja recuperados."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Sequence

from langchain_core.documents import Document


class Reranker(Protocol):
    """Contrato minimo de pontuacao; scores maiores indicam maior relevancia."""

    def score(self, query: str, documents: Sequence[str]) -> Sequence[float]: ...


@dataclass(frozen=True)
class FastEmbedCrossEncoderReranker:
    """Cross-encoder ONNX local, carregado sob demanda pelo FastEmbed."""

    model_name: str
    cache_dir: str

    def score(self, query: str, documents: Sequence[str]) -> Sequence[float]:
        model = _load_cross_encoder(self.model_name, self.cache_dir)
        return list(model.rerank(query, documents))


@lru_cache(maxsize=4)
def _load_cross_encoder(model_name: str, cache_dir: str):
    """Mantem uma unica sessao ONNX por configuracao no processo."""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(
        model_name=model_name,
        cache_dir=cache_dir,
        lazy_load=True,
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
) -> list[Document]:
    """Pontua candidatos limitados sem modificar conteudo ou metadata."""
    limited = list(candidates[:candidate_limit])
    if not limited or top_k <= 0:
        return []

    texts = [document.page_content[:max_chars] for document in limited]
    scores = await asyncio.wait_for(
        asyncio.to_thread(reranker.score, query, texts),
        timeout=timeout_seconds,
    )
    if len(scores) != len(limited):
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
        enumerate(limited),
        key=lambda item: (-normalized_scores[item[0]], item[0]),
    )
    return [document for _index, document in ranked[:top_k]]
