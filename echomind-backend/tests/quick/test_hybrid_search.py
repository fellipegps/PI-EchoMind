"""Fusão híbrida determinística e avaliação offline da PR 24."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document

from scripts.eval_hybrid_search import evaluate_hybrid


def _document(source_type: str, source_id: str) -> Document:
    return Document(page_content=source_id, metadata={"source_type": source_type, "source_id": source_id, "tenant_id": "tenant-a"})


def test_rrf_fusion_is_deterministic_deduplicated_and_preserves_vector_document(quick_test_context) -> None:
    from app.rag_engine import _fuse_hybrid_results

    vector = [_document("faq", "shared"), _document("event", "vector-only")]
    lexical = [_document("faq", "shared"), _document("document_chunk", "lexical-only")]

    merged = _fuse_hybrid_results(vector, lexical, limit=3)

    assert [(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in merged] == [
        ("faq", "shared"),
        ("event", "vector-only"),
        ("document_chunk", "lexical-only"),
    ]


def test_hybrid_eval_shows_gain_for_exact_terms_without_semantic_regression() -> None:
    dataset = json.loads((Path(__file__).parents[2] / "evals" / "hybrid_search_eval.json").read_text(encoding="utf-8"))
    report = evaluate_hybrid(dataset)

    assert report["metrics_by_category"]["codigo"] == {"hybrid_recall": 1.0, "vector_recall": 0.0}
    assert report["metrics_by_category"]["sigla"] == {"hybrid_recall": 1.0, "vector_recall": 0.0}
    assert report["metrics_by_category"]["semantica"] == {"hybrid_recall": 1.0, "vector_recall": 1.0}
    assert report["overall"] == {"vector_recall": 0.5, "hybrid_recall": 1.0}
