"""Contratos de ranking, fallback e avaliacao executavel da PR 24."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from langchain_core.documents import Document

from app.hybrid_search import fuse_hybrid_results
from scripts.eval_hybrid_search import evaluate_hybrid


EVALS = Path(__file__).parents[2] / "evals"


def _document(
    source_type: str,
    source_id: str,
    *,
    tenant_id: str = "tenant-a",
) -> Document:
    return Document(
        page_content=source_id,
        metadata={
            "source_type": source_type,
            "source_id": source_id,
            "tenant_id": tenant_id,
        },
    )


class ControlledEmbeddings:
    """Fake local que produz rankings, sem rede nem resultados precomputados."""

    def __init__(self, dataset: dict) -> None:
        corpus = dataset["corpus"]
        self._source_index = {source["id"]: index for index, source in enumerate(corpus)}
        self._dimension = len(corpus)
        self._query_target = {
            "codigo-edital": "alfa-doc-edital-x18",
            "sigla-nucleo": "alfa-faq-nae",
            "nome-institucional": "beta-evento-forum",
            "reformulacao-matricula": "alfa-faq-matricula",
            "reformulacao-recurso": "alfa-doc-recurso",
            "reformulacao-pagamento": "beta-doc-pagamento",
        }
        self._question_case = {case["question"]: case["id"] for case in dataset["cases"]}

    def _vector(self, source_id: str) -> list[float]:
        vector = [0.0] * self._dimension
        vector[self._source_index[source_id]] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == len(self._source_index)
        return [self._vector(source_id) for source_id in self._source_index]

    def embed_query(self, text: str) -> list[float]:
        case_id = self._question_case[text]
        return self._vector(self._query_target[case_id])


def _dataset() -> dict:
    return json.loads((EVALS / "hybrid_search_eval.json").read_text(encoding="utf-8"))


def test_rrf_fusion_is_deterministic_deduplicated_and_preserves_vector_document() -> None:
    vector = [_document("faq", "shared"), _document("event", "vector-only")]
    lexical = [_document("faq", "shared"), _document("document_chunk", "lexical-only")]

    first = fuse_hybrid_results(vector, lexical, limit=3)
    second = fuse_hybrid_results(vector, lexical, limit=3)

    assert first == second
    assert [(doc.metadata["source_type"], doc.metadata["source_id"]) for doc in first] == [
        ("faq", "shared"),
        ("event", "vector-only"),
        ("document_chunk", "lexical-only"),
    ]
    assert first[0] is vector[0]


def test_rrf_uses_positions_and_enforces_top_k() -> None:
    vector = [_document("faq", "a"), _document("faq", "b"), _document("faq", "c")]
    lexical = [_document("faq", "b"), _document("faq", "c"), _document("faq", "a")]

    result = fuse_hybrid_results(vector, lexical, limit=2, rrf_k=60)

    assert [document.metadata["source_id"] for document in result] == ["b", "a"]
    assert fuse_hybrid_results(vector, lexical, limit=0) == []
    with pytest.raises(ValueError, match="rrf_k"):
        fuse_hybrid_results(vector, lexical, limit=2, rrf_k=0)


def test_executable_eval_calculates_rankings_and_hybrid_gain_without_network() -> None:
    dataset = _dataset()
    report = evaluate_hybrid(dataset, ControlledEmbeddings(dataset))

    assert all("vector_source_ids" not in case for case in dataset["cases"])
    assert all("lexical_source_ids" not in case for case in dataset["cases"])
    assert report["mode"] == "offline-executed-retrieval"
    assert report["metrics_by_category"]["codigo"]["vector_recall"] == 0.0
    assert report["metrics_by_category"]["codigo"]["hybrid_recall"] == 1.0
    assert report["metrics_by_category"]["sigla"]["hybrid_recall"] == 1.0
    assert report["metrics_by_category"]["semantica"]["vector_recall"] == 1.0
    assert report["metrics_by_category"]["semantica"]["hybrid_recall"] == 1.0
    assert report["overall"] == {"vector_recall": 0.5, "hybrid_recall": 1.0}
    assert report["ranking"]["recall_gain"] == 0.5
    assert report["comparison"] == {
        "pr23_vector_only": {"recall_at_k": 0.5, "mrr_at_k": 0.5},
        "pr24_hybrid": {"recall_at_k": 1.0, "mrr_at_k": 0.75},
    }
    assert all(item["tenant_candidates_filtered"] > 0 for item in report["cases"])
    assert all(item["expired_candidates_filtered"] == 1 for item in report["cases"])


@pytest.mark.asyncio
async def test_lexical_failure_falls_back_to_tenant_scoped_current_vector_results(
    quick_test_context,
    monkeypatch,
) -> None:
    from app import rag_engine

    current = _document("faq", "current")
    cross_tenant = _document("faq", "cross-tenant", tenant_id="tenant-b")
    expired = _document("document_chunk", "expired")
    expired.metadata["valid_until"] = "2026-08-29"

    class VectorStore:
        def similarity_search_with_score(self, question: str, *, k: int):
            assert question == "pergunta"
            assert k >= 10
            return [(cross_tenant, 0.01), (expired, 0.02), (current, 0.10)]

    def fail_lexical(*_args, **_kwargs):
        raise RuntimeError("fts indisponivel")

    events = []
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: VectorStore())
    monkeypatch.setattr(rag_engine, "_search_lexical_documents", fail_lexical)
    monkeypatch.setattr(rag_engine, "_expand_document_parents", lambda documents, **_kwargs: list(documents))
    monkeypatch.setattr(rag_engine, "RERANKER_ENABLED", False)
    monkeypatch.setattr(rag_engine, "emit_event", lambda **fields: events.append(fields))

    documents, nearest_distance = await rag_engine._retrieve_docs(
        "pergunta",
        "tenant-a",
        today=date(2026, 8, 30),
    )

    assert documents == [current]
    assert nearest_distance == 0.10
    assert any(
        event["event"] == "rag.lexical-retrieval"
        and event["stage"] == "fallback-vector"
        and event["status"] == "error"
        for event in events
    )


@pytest.mark.asyncio
async def test_vector_failure_remains_an_error(quick_test_context, monkeypatch) -> None:
    from app import rag_engine

    class VectorStore:
        def similarity_search_with_score(self, question: str, *, k: int):
            raise RuntimeError("pgvector indisponivel")

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: VectorStore())
    monkeypatch.setattr(
        rag_engine,
        "_search_lexical_documents",
        lambda *_args, **_kwargs: [_document("faq", "lexical")],
    )

    with pytest.raises(RuntimeError, match="pgvector indisponivel"):
        await rag_engine._retrieve_docs("pergunta", "tenant-a", today=date(2026, 8, 30))


def test_fts_expression_indexes_only_use_immutable_concatenation() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0010_hybrid_search_fts.py"
    ).read_text(encoding="utf-8")

    assert "concat_ws" not in migration
    assert migration.count("CREATE INDEX ix_") == 4
