"""Contratos offline do reranker da PR 25."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.reranker import rerank_documents
from scripts.eval_reranker import evaluate_reranker


def _document(
    source_id: str,
    *,
    tenant_id: str = "tenant-a",
    valid_until: str | None = None,
    content: str | None = None,
) -> Document:
    metadata = {
        "source_type": "document_chunk",
        "source_id": source_id,
        "tenant_id": tenant_id,
        "filename": f"{source_id}.pdf",
    }
    if valid_until is not None:
        metadata["valid_until"] = valid_until
    return Document(page_content=content or f"conteudo {source_id}", metadata=metadata)


class FixedReranker:
    def __init__(self, scores: list[float]):
        self.scores = scores
        self.received: list[str] = []

    def score(self, query: str, documents: list[str]) -> list[float]:
        assert query == "pergunta sintetica"
        self.received = list(documents)
        return self.scores[: len(documents)]


@pytest.mark.asyncio
async def test_fake_orders_known_scores_and_preserves_documents_metadata() -> None:
    candidates = [_document("a"), _document("b"), _document("c")]
    metadata_ids = [id(document.metadata) for document in candidates]

    ranked = await rerank_documents(
        "pergunta sintetica",
        candidates,
        reranker=FixedReranker([0.2, 0.9, 0.5]),
        candidate_limit=10,
        top_k=3,
        max_chars=100,
        timeout_seconds=1,
    )

    assert ranked == [candidates[1], candidates[2], candidates[0]]
    assert [id(document.metadata) for document in candidates] == metadata_ids
    assert all(document.metadata["tenant_id"] == "tenant-a" for document in ranked)
    assert [document.metadata["filename"] for document in ranked] == ["b.pdf", "c.pdf", "a.pdf"]


@pytest.mark.asyncio
async def test_candidate_text_and_top_k_limits_are_enforced() -> None:
    candidates = [
        _document(str(index), content=f"{index:02d}-conteudo-muito-longo")
        for index in range(14)
    ]
    fake = FixedReranker([float(index) for index in range(12)])

    ranked = await rerank_documents(
        "pergunta sintetica",
        candidates,
        reranker=fake,
        candidate_limit=12,
        top_k=3,
        max_chars=5,
        timeout_seconds=1,
    )

    assert len(fake.received) == 12
    assert all(len(text_value) == 5 for text_value in fake.received)
    assert [document.metadata["source_id"] for document in ranked] == ["11", "10", "9"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scores",
    [[], [True], [float("nan")]],
)
async def test_invalid_provider_scores_are_rejected(scores: list[float]) -> None:
    with pytest.raises(ValueError):
        await rerank_documents(
            "pergunta sintetica",
            [_document("a")],
            reranker=FixedReranker(scores),
            candidate_limit=10,
            top_k=3,
            max_chars=100,
            timeout_seconds=1,
        )


class ErrorReranker:
    def score(self, query: str, documents: list[str]) -> list[float]:
        raise RuntimeError("modelo indisponivel")


class SlowReranker:
    def score(self, query: str, documents: list[str]) -> list[float]:
        time.sleep(0.05)
        return [1.0] * len(documents)


@pytest.mark.asyncio
async def test_retrieval_reranks_only_the_fused_candidate_pool(
    quick_test_context,
    monkeypatch,
) -> None:
    from app import rag_engine

    vector_documents = [(_document(f"vector-{index}"), 0.01 * index) for index in range(1, 8)]
    lexical_documents = [_document(f"lexical-{index}") for index in range(1, 8)]

    class VectorStore:
        def similarity_search_with_score(self, question: str, *, k: int):
            return vector_documents

    class CapturingReranker:
        def __init__(self):
            self.received: list[str] = []

        def score(self, query: str, documents: list[str]) -> list[float]:
            self.received = list(documents)
            return [float(index) for index in range(len(documents))]

    fake = CapturingReranker()
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: VectorStore())
    monkeypatch.setattr(
        rag_engine,
        "_search_lexical_documents",
        lambda question, tenant_id, *, today, limit: lexical_documents,
    )
    monkeypatch.setattr(rag_engine, "RERANKER_CANDIDATE_LIMIT", 12)

    fused = rag_engine._fuse_hybrid_results(
        [document for document, _distance in vector_documents],
        lexical_documents,
        limit=12,
    )
    documents, _distance = await rag_engine._retrieve_docs(
        "pergunta sintetica",
        "tenant-a",
        today=date(2026, 8, 24),
        reranker=fake,
    )

    assert fake.received == [document.page_content for document in fused]
    assert documents == list(reversed(fused))[: rag_engine.TOP_K_DOCS]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fake", "timeout_seconds"),
    [(ErrorReranker(), 1.0), (SlowReranker(), 0.001)],
)
async def test_retrieval_falls_back_to_pr24_on_error_or_timeout(
    quick_test_context,
    monkeypatch,
    fake,
    timeout_seconds: float,
) -> None:
    from app import rag_engine

    vector_documents = [
        (_document("shared"), 0.10),
        (_document("vector-only"), 0.20),
        (_document("expired", valid_until="2026-08-23"), 0.05),
    ]
    lexical_documents = [
        _document("shared"),
        _document("lexical-only"),
    ]

    class VectorStore:
        def similarity_search_with_score(self, question: str, *, k: int):
            assert k >= 10
            return vector_documents

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: VectorStore())
    monkeypatch.setattr(
        rag_engine,
        "_search_lexical_documents",
        lambda question, tenant_id, *, today, limit: lexical_documents,
    )
    monkeypatch.setattr(rag_engine, "RERANKER_TIMEOUT_SECONDS", timeout_seconds)

    expected = rag_engine._fuse_hybrid_results(
        [vector_documents[0][0], vector_documents[1][0]],
        lexical_documents,
        limit=rag_engine.TOP_K_DOCS,
    )
    documents, nearest_distance = await rag_engine._retrieve_docs(
        "pergunta sintetica",
        "tenant-a",
        today=date(2026, 8, 24),
        reranker=fake,
    )

    assert documents == expected
    assert nearest_distance == 0.10
    assert "expired" not in {document.metadata["source_id"] for document in documents}
    assert all(document.metadata["tenant_id"] == "tenant-a" for document in documents)
    assert all(document.metadata["filename"].endswith(".pdf") for document in documents)


def test_offline_eval_reports_ranking_gain_latency_and_pr22_reference() -> None:
    evals = Path(__file__).parents[2] / "evals"
    report = evaluate_reranker(
        json.loads((evals / "reranker_eval.json").read_text(encoding="utf-8")),
        baseline_pr22=json.loads((evals / "baseline_report.json").read_text(encoding="utf-8")),
        baseline_pr24=json.loads((evals / "hybrid_search_report.json").read_text(encoding="utf-8")),
    )

    assert report["references"]["pr22"] == {
        "source_recall": 1.0,
        "source_precision": 1.0,
        "retrieval_mean_ms": 14.05,
        "retrieval_p95_ms": 18.0,
    }
    assert report["references"]["pr24"] == {
        "vector_recall": 0.5,
        "hybrid_recall": 1.0,
    }
    assert report["ranking"] == {
        "hybrid_hit_rate_at_k": 0.833,
        "reranked_hit_rate_at_k": 1.0,
        "hybrid_mrr_at_k": 0.556,
        "reranked_mrr_at_k": 1.0,
        "hit_rate_gain": 0.167,
        "mrr_gain": 0.444,
    }
    assert report["latency_ms"] == {
        "controlled_hybrid_mean": 15.0,
        "controlled_hybrid_p95": 16.0,
        "controlled_reranked_mean": 18.667,
        "controlled_reranked_p95": 19.0,
        "reranker_overhead_mean": 3.667,
        "reranker_overhead_p95": 5.0,
    }
