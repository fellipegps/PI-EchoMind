#!/usr/bin/env python3
"""Executa a avaliacao offline e reproduzivel da busca hibrida da PR 24."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from langchain_core.documents import Document

try:  # suporta importacao e execucao direta a partir da raiz do backend
    from app.hybrid_search import fuse_hybrid_results
    from scripts.calibrate_similarity_threshold import (
        EmbeddingAdapter,
        ProductionFastEmbedAdapter,
        _cosine_distance,
    )
except ImportError:  # pragma: no cover - caminho de execucao direta
    from app.hybrid_search import fuse_hybrid_results
    from calibrate_similarity_threshold import (  # type: ignore[no-redef]
        EmbeddingAdapter,
        ProductionFastEmbedAdapter,
        _cosine_distance,
    )

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_LEXICAL_STOPWORDS = {
    "a",
    "as",
    "ate",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "o",
    "os",
    "para",
    "por",
    "qual",
    "que",
    "quando",
    "um",
    "uma",
}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(character for character in normalized if not unicodedata.combining(character))
    return _TOKEN_PATTERN.findall(ascii_value)


def _source_text(source: dict[str, Any]) -> str:
    return f"{source['label']}\n{source['content']}"


def _is_current(source: dict[str, Any], *, evaluation_date: date) -> bool:
    valid_until = source.get("valid_until")
    return valid_until is None or date.fromisoformat(valid_until) >= evaluation_date


def _document(source: dict[str, Any]) -> Document:
    return Document(
        page_content=source["content"],
        metadata={
            "source_type": source["type"],
            "source_id": source["id"],
            "tenant_id": source["tenant_id"],
            "label": source["label"],
        },
    )


def _lexical_rank(question: str, sources: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Proxy offline deterministico; PostgreSQL FTS real e coberto na integracao."""
    query_tokens = [
        token for token in _normalized_tokens(question)
        if token not in _LEXICAL_STOPWORDS
    ]
    ranked = []
    for source in sources:
        source_tokens = _normalized_tokens(_source_text(source))
        source_token_set = set(source_tokens)
        if not query_tokens or not all(token in source_token_set for token in query_tokens):
            continue
        frequency = sum(source_tokens.count(token) for token in query_tokens)
        ranked.append({"source": source, "score": frequency / len(source_tokens)})
    ranked.sort(key=lambda item: (-item["score"], item["source"]["id"]))
    return ranked


def _rank_of(expected: str, source_ids: Sequence[str]) -> int | None:
    try:
        return source_ids.index(expected) + 1
    except ValueError:
        return None


def _reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def _validate_dataset(dataset: dict[str, Any]) -> None:
    corpus = dataset.get("corpus")
    cases = dataset.get("cases")
    configuration = dataset.get("retrieval_configuration")
    if not isinstance(corpus, list) or not corpus:
        raise ValueError("Eval hibrido exige corpus nao vazio.")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval hibrido exige casos nao vazios.")
    if not isinstance(configuration, dict):
        raise ValueError("Eval hibrido exige retrieval_configuration.")
    source_ids = [source.get("id") for source in corpus]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("IDs do corpus devem ser unicos.")
    known_ids = set(source_ids)
    for case in cases:
        if case.get("expected_source_id") not in known_ids:
            raise ValueError(f"Fonte esperada inexistente no caso {case.get('id')}.")
        if "vector_source_ids" in case or "lexical_source_ids" in case:
            raise ValueError("O eval nao aceita rankings previamente preenchidos.")


def evaluate_hybrid(
    dataset: dict[str, Any],
    embeddings: EmbeddingAdapter,
    *,
    embedding_backend: str = "injected",
    embedding_version: str = "test",
    baseline_pr22: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calcula os dois rankings a partir do corpus e aplica o RRF de producao."""
    _validate_dataset(dataset)
    configuration = dataset["retrieval_configuration"]
    threshold = float(configuration["similarity_threshold"])
    top_k = int(configuration["top_k"])
    candidate_k = int(configuration["candidate_k"])
    rrf_k = int(configuration["rrf_k"])
    if top_k <= 0 or candidate_k < top_k:
        raise ValueError("candidate_k deve ser maior ou igual a top_k positivo.")

    corpus = dataset["corpus"]
    corpus_vectors = embeddings.embed_documents([_source_text(source) for source in corpus])
    if len(corpus_vectors) != len(corpus):
        raise ValueError("O adaptador nao retornou um embedding por fonte.")

    evaluation_date = date.fromisoformat(dataset["evaluation_date"])
    metrics_by_category: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"vector_hit": [], "hybrid_hit": [], "vector_rr": [], "hybrid_rr": []}
    )
    details = []
    for case in dataset["cases"]:
        eligible = [
            (source, vector)
            for source, vector in zip(corpus, corpus_vectors)
            if source["tenant_id"] == case["tenant_id"]
            and _is_current(source, evaluation_date=evaluation_date)
        ]
        filtered_tenant = sum(source["tenant_id"] != case["tenant_id"] for source in corpus)
        filtered_expired = sum(
            source["tenant_id"] == case["tenant_id"]
            and not _is_current(source, evaluation_date=evaluation_date)
            for source in corpus
        )

        query_vector = embeddings.embed_query(case["question"])
        vector_candidates = [
            {
                "source": source,
                "distance": round(_cosine_distance(query_vector, source_vector), 6),
            }
            for source, source_vector in eligible
        ]
        vector_candidates.sort(key=lambda item: (item["distance"], item["source"]["id"]))
        vector_selected = [
            item for item in vector_candidates[:candidate_k]
            if item["distance"] <= threshold
        ]
        vector_documents = [_document(item["source"]) for item in vector_selected]

        lexical_selected = _lexical_rank(
            case["question"],
            [source for source, _vector in eligible],
        )[:candidate_k]
        lexical_documents = [_document(item["source"]) for item in lexical_selected]
        hybrid_documents = fuse_hybrid_results(
            vector_documents,
            lexical_documents,
            limit=top_k,
            rrf_k=rrf_k,
        )

        vector_ids = [item["source"]["id"] for item in vector_selected[:top_k]]
        lexical_ids = [item["source"]["id"] for item in lexical_selected]
        hybrid_ids = [document.metadata["source_id"] for document in hybrid_documents]
        expected = case["expected_source_id"]
        vector_rank = _rank_of(expected, vector_ids)
        hybrid_rank = _rank_of(expected, hybrid_ids)
        category = metrics_by_category[case["category"]]
        category["vector_hit"].append(float(vector_rank is not None))
        category["hybrid_hit"].append(float(hybrid_rank is not None))
        category["vector_rr"].append(_reciprocal_rank(vector_rank))
        category["hybrid_rr"].append(_reciprocal_rank(hybrid_rank))
        details.append({
            "id": case["id"],
            "category": case["category"],
            "tenant_id": case["tenant_id"],
            "expected_source_id": expected,
            "vector_source_ids": vector_ids,
            "vector_distances": [item["distance"] for item in vector_selected[:top_k]],
            "lexical_source_ids": lexical_ids,
            "hybrid_source_ids": hybrid_ids,
            "vector_rank": vector_rank,
            "hybrid_rank": hybrid_rank,
            "tenant_candidates_filtered": filtered_tenant,
            "expired_candidates_filtered": filtered_expired,
        })

    def mean(values: Sequence[float]) -> float:
        return round(sum(values) / len(values), 3)

    category_report = {
        category: {
            "vector_recall": mean(values["vector_hit"]),
            "hybrid_recall": mean(values["hybrid_hit"]),
            "vector_mrr_at_k": mean(values["vector_rr"]),
            "hybrid_mrr_at_k": mean(values["hybrid_rr"]),
        }
        for category, values in sorted(metrics_by_category.items())
    }
    vector_hits = [float(item["vector_rank"] is not None) for item in details]
    hybrid_hits = [float(item["hybrid_rank"] is not None) for item in details]
    vector_rr = [_reciprocal_rank(item["vector_rank"]) for item in details]
    hybrid_rr = [_reciprocal_rank(item["hybrid_rank"]) for item in details]
    vector_recall = mean(vector_hits)
    hybrid_recall = mean(hybrid_hits)
    vector_mrr = mean(vector_rr)
    hybrid_mrr = mean(hybrid_rr)
    baseline_metrics = (baseline_pr22 or {}).get("metrics", {})
    baseline_retrieval = baseline_metrics.get("retrieval", {})
    baseline_latency = baseline_metrics.get("latency_ms", {})
    return {
        "report_version": 2,
        "dataset_version": dataset["dataset_version"],
        "dataset_sha256": _canonical_hash(dataset),
        "mode": "offline-executed-retrieval",
        "embedding_execution": {
            "backend": embedding_backend,
            "backend_version": embedding_version,
            "model": configuration["embedding_model"],
            "dimensions": configuration["embedding_dimensions"],
            "external_llm": False,
        },
        "retrieval_configuration": configuration,
        "lexical_evaluation": {
            "mode": "deterministic-token-proxy",
            "production_fts_covered_by": "tests/integration/test_document_pgvector.py",
        },
        "baseline_pr22": {
            "report": "evals/baseline_report.json",
            "dataset_version": (baseline_pr22 or {}).get("dataset_version"),
            "source_recall": baseline_retrieval.get("source_recall"),
            "source_precision": baseline_retrieval.get("source_precision"),
            "retrieval_mean_ms": baseline_latency.get("retrieval_mean"),
            "retrieval_p95_ms": baseline_latency.get("retrieval_p95"),
            "comparison_note": "A PR 22 usa seu corpus de baseline e latencias controladas; a PR 24 usa casos lexicais dedicados, portanto os valores sao referencias lado a lado, nao um delta do mesmo dataset.",
        },
        "metrics_by_category": category_report,
        "overall": {
            "vector_recall": vector_recall,
            "hybrid_recall": hybrid_recall,
        },
        "ranking": {
            "vector_mrr_at_k": vector_mrr,
            "hybrid_mrr_at_k": hybrid_mrr,
            "recall_gain": round(hybrid_recall - vector_recall, 3),
            "mrr_gain": round(hybrid_mrr - vector_mrr, 3),
        },
        "comparison": {
            "pr23_vector_only": {
                "recall_at_k": vector_recall,
                "mrr_at_k": vector_mrr,
            },
            "pr24_hybrid": {
                "recall_at_k": hybrid_recall,
                "mrr_at_k": hybrid_mrr,
            },
        },
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara busca vetorial e hibrida sem rede.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/hybrid_search_eval.json"))
    parser.add_argument("--baseline-pr22", type=Path, default=Path("evals/baseline_report.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/hybrid_search_report.json"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "echomind_models"))),
    )
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    configuration = dataset["retrieval_configuration"]
    embeddings = ProductionFastEmbedAdapter(
        model_name=configuration["embedding_model"],
        dimensions=int(configuration["embedding_dimensions"]),
        cache_dir=args.cache_dir,
        allow_model_download=args.allow_model_download,
    )
    report = evaluate_hybrid(
        dataset,
        embeddings,
        embedding_backend="fastembed",
        embedding_version=importlib.metadata.version("fastembed"),
        baseline_pr22=json.loads(args.baseline_pr22.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report["overall"], **report["ranking"]}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
