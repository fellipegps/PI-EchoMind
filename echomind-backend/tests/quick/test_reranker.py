"""Contratos offline do reranker da PR 25."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import date
from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.reranker import RerankerBusyError, RerankerExecutionGate, rerank_documents
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


def test_fastembed_runtime_uses_local_cache_only_and_reports_missing_model(monkeypatch) -> None:
    from app import reranker as reranker_module

    received = []

    class Model:
        def rerank(self, query: str, documents: list[str]) -> list[float]:
            return [0.5] * len(documents)

    def load(model_name: str, cache_dir: str, allow_model_download: bool):
        received.append((model_name, cache_dir, allow_model_download))
        return Model()

    monkeypatch.setattr(reranker_module, "_load_cross_encoder", load)
    local = reranker_module.FastEmbedCrossEncoderReranker("modelo", "cache")

    assert local.score("consulta", ["documento"]) == [0.5]
    assert received == [("modelo", "cache", False)]

    monkeypatch.setattr(
        reranker_module,
        "_load_cross_encoder",
        lambda *_args: (_ for _ in ()).throw(ValueError("ausente")),
    )
    with pytest.raises(RuntimeError, match="ausente ou indisponivel"):
        local.score("consulta", ["documento"])


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
async def test_timeout_keeps_capacity_bounded_until_abandoned_inference_finishes() -> None:
    started = threading.Event()
    release = threading.Event()

    class BlockingReranker:
        def __init__(self) -> None:
            self.calls = 0

        def score(self, query: str, documents: list[str]) -> list[float]:
            self.calls += 1
            started.set()
            release.wait(timeout=1)
            return [1.0] * len(documents)

    fake = BlockingReranker()
    gate = RerankerExecutionGate()
    try:
        with pytest.raises(asyncio.TimeoutError):
            await rerank_documents(
                "pergunta sintetica",
                [_document("a")],
                reranker=fake,
                candidate_limit=10,
                top_k=1,
                max_chars=100,
                timeout_seconds=0.01,
                execution_gate=gate,
            )
        assert started.is_set()

        with pytest.raises(RerankerBusyError):
            await rerank_documents(
                "pergunta sintetica",
                [_document("b")],
                reranker=fake,
                candidate_limit=10,
                top_k=1,
                max_chars=100,
                timeout_seconds=0.01,
                execution_gate=gate,
            )
        assert fake.calls == 1

        release.set()
        for _attempt in range(20):
            await asyncio.sleep(0.01)
            if fake.calls == 1:
                try:
                    result = await rerank_documents(
                        "pergunta sintetica",
                        [_document("c")],
                        reranker=fake,
                        candidate_limit=10,
                        top_k=1,
                        max_chars=100,
                        timeout_seconds=1,
                        execution_gate=gate,
                    )
                except RerankerBusyError:
                    continue
                assert result[0].metadata["source_id"] == "c"
                break
        else:
            pytest.fail("Gate nao liberou a capacidade apos a inferencia terminar.")
        assert fake.calls == 2
    finally:
        release.set()
        gate.shutdown()


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


class ControlledEmbeddings:
    """Produz candidatos em execucao, sem rede ou rankings no dataset."""

    def __init__(self, dataset: dict) -> None:
        corpus = dataset["corpus"]
        self._source_index = {source["id"]: index for index, source in enumerate(corpus)}
        self._dimension = len(corpus)
        self._question_case = {case["question"]: case["id"] for case in dataset["cases"]}
        self._query_target = {
            "codigo-edital": "alfa-doc-edital-x18",
            "sigla-nucleo": "alfa-faq-nae",
            "nome-institucional": "beta-evento-forum",
            "reformulacao-matricula": "alfa-faq-matricula",
            "reformulacao-recurso": "alfa-doc-recurso",
            "reformulacao-pagamento": "beta-doc-pagamento",
        }

    def _vector(self, source_id: str) -> list[float]:
        vector = [0.0] * self._dimension
        vector[self._source_index[source_id]] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == len(self._source_index)
        return [self._vector(source_id) for source_id in self._source_index]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(self._query_target[self._question_case[text]])


class ContentLengthReranker:
    def score(self, query: str, documents: list[str]) -> list[float]:
        return [float(len(document)) for document in documents]


class StepClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        current = self.value
        self.value += 0.001
        return current


def test_offline_eval_executes_retrieval_scores_and_measured_latency() -> None:
    evals = Path(__file__).parents[2] / "evals"
    baseline_pr22 = json.loads((evals / "baseline_report.json").read_text(encoding="utf-8"))
    dataset = json.loads((evals / "hybrid_search_eval.json").read_text(encoding="utf-8"))
    configuration = json.loads((evals / "reranker_eval.json").read_text(encoding="utf-8"))
    report = evaluate_reranker(
        dataset,
        configuration,
        ControlledEmbeddings(dataset),
        ContentLengthReranker(),
        baseline_pr22=baseline_pr22,
        baseline_pr24=json.loads((evals / "hybrid_search_report.json").read_text(encoding="utf-8")),
        clock=StepClock(),
    )

    assert report["mode"] == "offline-executed-reranker-benchmark"
    assert report["references"]["pr22"] == {
        "source_recall": baseline_pr22["metrics"]["retrieval"]["source_recall"],
        "source_precision": baseline_pr22["metrics"]["retrieval"]["source_precision"],
        "retrieval_mean_ms": baseline_pr22["metrics"]["latency_ms"]["retrieval_mean"],
        "retrieval_p95_ms": baseline_pr22["metrics"]["latency_ms"]["retrieval_p95"],
    }
    assert report["references"]["pr24"] == {
        "vector_recall": 0.5,
        "hybrid_recall": 1.0,
    }
    assert report["latency_ms"] == {
        "model_warmup": 1.0,
        "hybrid_retrieval_total": 1.0,
        "hybrid_retrieval_mean_per_case": 0.167,
        "reranker_mean": 1.0,
        "reranker_p95": 1.0,
        "retrieval_plus_reranker_mean": 1.167,
        "controlled_reranked_mean": 1.167,
    }
    corpus = {source["id"]: source for source in dataset["corpus"]}

    def runtime_text(source: dict) -> str:
        if source["type"] == "faq":
            return f"Pergunta: {source['label']}\nResposta: {source['content']}"
        if source["type"] == "event":
            return f"Evento: {source['label']}\n{source['content']}"
        return f"Fonte: {source['label']}\n{source['content']}"

    assert all(
        detail["reranker_scores"] == [
            float(len(runtime_text(corpus[source_id])[: configuration["reranker_configuration"]["max_chars"]]))
            for source_id in detail["hybrid_source_ids"]
        ]
        for detail in report["cases"]
    )
    assert all(
        all(corpus[source_id]["tenant_id"] == detail["tenant_id"] for source_id in detail["hybrid_source_ids"])
        for detail in report["cases"]
    )


def test_versioned_real_benchmark_rejects_activation_without_prefilled_outputs() -> None:
    evals = Path(__file__).parents[2] / "evals"
    configuration = json.loads((evals / "reranker_eval.json").read_text(encoding="utf-8"))
    report = json.loads((evals / "reranker_report.json").read_text(encoding="utf-8"))

    assert "cases" not in configuration
    assert report["mode"] == "offline-executed-reranker-benchmark"
    assert report["execution"]["reranker_backend"] == "fastembed-text-cross-encoder"
    assert report["ranking"] == {
        "hybrid_hit_rate_at_k": 1.0,
        "reranked_hit_rate_at_k": 1.0,
        "hybrid_mrr_at_k": 1.0,
        "reranked_mrr_at_k": 0.889,
        "hit_rate_gain": 0.0,
        "mrr_gain": -0.111,
    }
    assert report["activation_assessment"]["configured_default_enabled"] is False
    assert report["activation_assessment"]["benchmark_supports_activation"] is False
    assert all(case["reranker_scores"] for case in report["cases"])
