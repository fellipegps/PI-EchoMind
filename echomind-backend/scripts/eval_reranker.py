#!/usr/bin/env python3
"""Benchmark executavel do reranker sobre candidatos hibridos gerados."""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from langchain_core.documents import Document

from app.reranker import (
    FastEmbedCrossEncoderReranker,
    Reranker,
    rank_documents_by_scores,
)
from scripts.calibrate_similarity_threshold import (
    EmbeddingAdapter,
    ProductionFastEmbedAdapter,
)
from scripts.eval_hybrid_search import evaluate_hybrid


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 3)


def _p95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 3)


def _rank_metrics(expected: str, ranked: Sequence[str], top_k: int) -> tuple[float, float, int | None]:
    top = list(ranked[:top_k])
    if expected not in top:
        return 0.0, 0.0, None
    rank = top.index(expected) + 1
    return 1.0, 1.0 / rank, rank


def _document(source: dict[str, Any]) -> Document:
    if source["type"] == "faq":
        page_content = f"Pergunta: {source['label']}\nResposta: {source['content']}"
    elif source["type"] == "event":
        page_content = f"Evento: {source['label']}\n{source['content']}"
    else:
        page_content = f"Fonte: {source['label']}\n{source['content']}"
    return Document(
        page_content=page_content,
        metadata={
            "source_id": source["id"],
            "source_type": source["type"],
            "tenant_id": source["tenant_id"],
            "label": source["label"],
        },
    )


def _validate_configuration(configuration: dict[str, Any]) -> None:
    reranker = configuration.get("reranker_configuration")
    if not isinstance(reranker, dict):
        raise ValueError("Eval do reranker exige reranker_configuration.")
    candidate_limit = reranker.get("candidate_limit")
    top_k = reranker.get("top_k")
    max_chars = reranker.get("max_chars")
    if not isinstance(candidate_limit, int) or not 10 <= candidate_limit <= 15:
        raise ValueError("candidate_limit deve estar entre 10 e 15.")
    if not isinstance(top_k, int) or not 0 < top_k <= candidate_limit:
        raise ValueError("top_k deve ser positivo e nao exceder candidate_limit.")
    if not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError("max_chars deve ser positivo.")


def evaluate_reranker(
    dataset: dict[str, Any],
    configuration: dict[str, Any],
    embeddings: EmbeddingAdapter,
    reranker: Reranker,
    *,
    baseline_pr22: dict[str, Any],
    baseline_pr24: dict[str, Any],
    embedding_backend: str = "injected",
    embedding_version: str = "test",
    reranker_backend: str = "injected",
    reranker_version: str = "test",
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Gera candidatos, mede scores/tempos e aplica a ordenacao de producao."""
    _validate_configuration(configuration)
    reranker_config = configuration["reranker_configuration"]
    candidate_limit = int(reranker_config["candidate_limit"])
    top_k = int(reranker_config["top_k"])
    max_chars = int(reranker_config["max_chars"])

    retrieval_dataset = copy.deepcopy(dataset)
    retrieval_dataset["retrieval_configuration"]["candidate_k"] = max(
        candidate_limit,
        int(retrieval_dataset["retrieval_configuration"]["candidate_k"]),
    )
    retrieval_dataset["retrieval_configuration"]["top_k"] = candidate_limit
    retrieval_started = clock()
    hybrid_report = evaluate_hybrid(
        retrieval_dataset,
        embeddings,
        embedding_backend=embedding_backend,
        embedding_version=embedding_version,
        baseline_pr22=baseline_pr22,
    )
    retrieval_duration_ms = (clock() - retrieval_started) * 1000

    cases_by_id = {case["id"]: case for case in dataset["cases"]}
    sources = {source["id"]: source for source in dataset["corpus"]}
    if not hybrid_report["cases"]:
        raise ValueError("Eval do reranker exige ao menos um caso recuperado.")

    first_case = hybrid_report["cases"][0]
    first_source_ids = first_case["hybrid_source_ids"]
    if not first_source_ids:
        raise ValueError("Warm-up exige ao menos um candidato hibrido.")
    warmup_started = clock()
    reranker.score(
        cases_by_id[first_case["id"]]["question"],
        [_document(sources[first_source_ids[0]]).page_content[:max_chars]],
    )
    warmup_ms = (clock() - warmup_started) * 1000

    details: list[dict[str, Any]] = []
    hybrid_hits: list[float] = []
    hybrid_mrr: list[float] = []
    reranked_hits: list[float] = []
    reranked_mrr: list[float] = []
    reranker_latencies: list[float] = []
    average_retrieval_ms = retrieval_duration_ms / len(hybrid_report["cases"])

    for hybrid_case in hybrid_report["cases"]:
        case = cases_by_id[hybrid_case["id"]]
        candidate_ids = hybrid_case["hybrid_source_ids"][:candidate_limit]
        candidate_documents = [_document(sources[source_id]) for source_id in candidate_ids]
        texts = [document.page_content[:max_chars] for document in candidate_documents]
        score_started = clock()
        scores = list(reranker.score(case["question"], texts))
        score_duration_ms = (clock() - score_started) * 1000
        reranker_latencies.append(score_duration_ms)
        reranked_documents = rank_documents_by_scores(candidate_documents, scores, top_k=top_k)
        reranked_ids = [document.metadata["source_id"] for document in reranked_documents]

        expected = case["expected_source_id"]
        hybrid_hit, hybrid_rr, hybrid_rank = _rank_metrics(expected, candidate_ids, top_k)
        reranked_hit, reranked_rr, reranked_rank = _rank_metrics(expected, reranked_ids, top_k)
        hybrid_hits.append(hybrid_hit)
        hybrid_mrr.append(hybrid_rr)
        reranked_hits.append(reranked_hit)
        reranked_mrr.append(reranked_rr)
        details.append({
            "id": case["id"],
            "category": case["category"],
            "tenant_id": case["tenant_id"],
            "expected_source_id": expected,
            "hybrid_source_ids": candidate_ids,
            "reranker_scores": [round(float(score), 6) for score in scores],
            "reranked_source_ids": reranked_ids,
            "hybrid_rank_at_k": hybrid_rank,
            "reranked_rank_at_k": reranked_rank,
            "reranker_latency_ms": round(score_duration_ms, 3),
        })

    hybrid_hit_rate = _mean(hybrid_hits)
    reranked_hit_rate = _mean(reranked_hits)
    hybrid_mrr_at_k = _mean(hybrid_mrr)
    reranked_mrr_at_k = _mean(reranked_mrr)
    mean_overhead = _mean(reranker_latencies)
    pr22_metrics = baseline_pr22["metrics"]
    return {
        "report_version": 2,
        "dataset_version": configuration["dataset_version"],
        "source_dataset_version": dataset["dataset_version"],
        "mode": "offline-executed-reranker-benchmark",
        "execution": {
            "embedding_backend": embedding_backend,
            "embedding_backend_version": embedding_version,
            "embedding_model": dataset["retrieval_configuration"]["embedding_model"],
            "reranker_backend": reranker_backend,
            "reranker_backend_version": reranker_version,
            **reranker_config,
            "external_llm": False,
        },
        "references": {
            "pr22": {
                "source_recall": pr22_metrics["retrieval"]["source_recall"],
                "source_precision": pr22_metrics["retrieval"]["source_precision"],
                "retrieval_mean_ms": pr22_metrics["latency_ms"]["retrieval_mean"],
                "retrieval_p95_ms": pr22_metrics["latency_ms"]["retrieval_p95"],
            },
            "pr24": baseline_pr24["overall"],
        },
        "ranking": {
            "hybrid_hit_rate_at_k": hybrid_hit_rate,
            "reranked_hit_rate_at_k": reranked_hit_rate,
            "hybrid_mrr_at_k": hybrid_mrr_at_k,
            "reranked_mrr_at_k": reranked_mrr_at_k,
            "hit_rate_gain": round(reranked_hit_rate - hybrid_hit_rate, 3),
            "mrr_gain": round(reranked_mrr_at_k - hybrid_mrr_at_k, 3),
        },
        "latency_ms": {
            "model_warmup": round(warmup_ms, 3),
            "hybrid_retrieval_total": round(retrieval_duration_ms, 3),
            "hybrid_retrieval_mean_per_case": round(average_retrieval_ms, 3),
            "reranker_mean": mean_overhead,
            "reranker_p95": _p95(reranker_latencies),
            "retrieval_plus_reranker_mean": round(average_retrieval_ms + mean_overhead, 3),
            "controlled_reranked_mean": round(average_retrieval_ms + mean_overhead, 3),
        },
        "activation_assessment": {
            "configured_default_enabled": False,
            "benchmark_supports_activation": (
                reranked_hit_rate >= hybrid_hit_rate
                and reranked_mrr_at_k > hybrid_mrr_at_k
            ),
            "rule": "Somente considerar ativacao sem perda de Hit@K e com ganho positivo de MRR@K no benchmark PT-BR.",
        },
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia o reranker real sem LLM ou banco externo.")
    parser.add_argument("--config", type=Path, default=Path("evals/reranker_eval.json"))
    parser.add_argument("--dataset", type=Path, default=Path("evals/hybrid_search_eval.json"))
    parser.add_argument("--baseline-pr22", type=Path, default=Path("evals/baseline_report.json"))
    parser.add_argument("--baseline-pr24", type=Path, default=Path("evals/hybrid_search_report.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/reranker_report.json"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "echomind_models"))),
    )
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()

    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    retrieval = dataset["retrieval_configuration"]
    embeddings = ProductionFastEmbedAdapter(
        model_name=retrieval["embedding_model"],
        dimensions=int(retrieval["embedding_dimensions"]),
        cache_dir=args.cache_dir,
        allow_model_download=args.allow_model_download,
    )
    reranker = FastEmbedCrossEncoderReranker(
        model_name=configuration["reranker_configuration"]["model"],
        cache_dir=str(args.cache_dir),
        allow_model_download=args.allow_model_download,
    )
    version = importlib.metadata.version("fastembed")
    report = evaluate_reranker(
        dataset,
        configuration,
        embeddings,
        reranker,
        baseline_pr22=json.loads(args.baseline_pr22.read_text(encoding="utf-8")),
        baseline_pr24=json.loads(args.baseline_pr24.read_text(encoding="utf-8")),
        embedding_backend="fastembed",
        embedding_version=version,
        reranker_backend="fastembed-text-cross-encoder",
        reranker_version=version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ranking": report["ranking"], "latency_ms": report["latency_ms"]}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
