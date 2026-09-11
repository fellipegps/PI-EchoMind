"""Primitivas puras da fusao hibrida compartilhadas pelo runtime e pelo eval."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from langchain_core.documents import Document

DEFAULT_RRF_K = 60


def hybrid_source_key(document: Document) -> tuple[str, str]:
    """Identifica uma fonte sem misturar IDs iguais de tipos diferentes."""
    metadata = document.metadata if isinstance(document.metadata, Mapping) else {}
    return (
        str(metadata.get("source_type", "")),
        str(metadata.get("source_id", "")),
    )


def fuse_hybrid_results(
    vector_documents: Sequence[Document],
    lexical_documents: Sequence[Document],
    *,
    limit: int,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[Document]:
    """Aplica RRF deterministico, deduplica e preserva o documento vetorial."""
    if limit <= 0:
        return []
    if rrf_k <= 0:
        raise ValueError("rrf_k deve ser positivo.")
    fused: dict[tuple[str, str], dict[str, Any]] = {}
    for channel, documents in (
        ("vector", vector_documents),
        ("lexical", lexical_documents),
    ):
        for position, document in enumerate(documents, start=1):
            key = hybrid_source_key(document)
            candidate = fused.setdefault(
                key,
                {
                    "document": document,
                    "score": 0.0,
                    "vector": None,
                    "lexical": None,
                },
            )
            candidate["score"] += 1 / (rrf_k + position)
            candidate[channel] = position
            if channel == "vector":
                candidate["document"] = document
    return [
        candidate["document"]
        for candidate in sorted(
            fused.values(),
            key=lambda candidate: (
                -candidate["score"],
                candidate["vector"] if candidate["vector"] is not None else float("inf"),
                candidate["lexical"] if candidate["lexical"] is not None else float("inf"),
                *hybrid_source_key(candidate["document"]),
            ),
        )[:limit]
    ]
