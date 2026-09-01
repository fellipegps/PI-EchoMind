#!/usr/bin/env python3
"""Eval offline e deterministico da ordem híbrida antes/depois do reranker."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 3)


def _p95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], 3)


def _rank_metrics(expected: str, ranked: Sequence[str], top_k: int) -> tuple[float, float]:
    top = list(ranked[:top_k])
    if expected not in top:
        return 0.0, 0.0
    rank = top.index(expected) + 1
    return 1.0, 1.0 / rank


def evaluate_reranker(
    dataset: dict[str, Any],
    *,
    baseline_pr22: dict[str, Any],
    baseline_pr24: dict[str, Any],
) -> dict[str, Any]:
    cases = dataset.get("cases")
    top_k = dataset.get("top_k")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval do reranker exige uma lista não vazia de casos.")
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("Eval do reranker exige top_k inteiro positivo.")

    details: list[dict[str, Any]] = []
    hybrid_hits: list[float] = []
    hybrid_mrr: list[float] = []
    reranked_hits: list[float] = []
    reranked_mrr: list[float] = []
    hybrid_latencies: list[float] = []
    overhead_latencies: list[float] = []
    total_latencies: list[float] = []

    for case in cases:
        ranked = case["hybrid_ranked_source_ids"]
        scores = case["reranker_scores"]
        if len(ranked) != len(scores):
            raise ValueError(f"Caso {case['id']} possui candidatos e scores incompatíveis.")
        reranked = [
            source_id
            for _index, source_id in sorted(
                enumerate(ranked),
                key=lambda item: (-float(scores[item[0]]), item[0]),
            )
        ]
        hybrid_hit, hybrid_rr = _rank_metrics(case["expected_source_id"], ranked, top_k)
        reranked_hit, reranked_rr = _rank_metrics(case["expected_source_id"], reranked, top_k)
        hybrid_latency = float(case["hybrid_latency_ms"])
        overhead = float(case["reranker_latency_ms"])
        hybrid_hits.append(hybrid_hit)
        hybrid_mrr.append(hybrid_rr)
        reranked_hits.append(reranked_hit)
        reranked_mrr.append(reranked_rr)
        hybrid_latencies.append(hybrid_latency)
        overhead_latencies.append(overhead)
        total_latencies.append(hybrid_latency + overhead)
        details.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_source_id": case["expected_source_id"],
                "hybrid_rank": ranked.index(case["expected_source_id"]) + 1,
                "reranked_rank": reranked.index(case["expected_source_id"]) + 1,
            }
        )

    pr22_metrics = baseline_pr22["metrics"]
    pr24_metrics = baseline_pr24["overall"]
    return {
        "report_version": 1,
        "dataset_version": dataset.get("dataset_version"),
        "mode": "offline-synthetic-reranker-comparison",
        "references": {
            "pr22": {
                "source_recall": pr22_metrics["retrieval"]["source_recall"],
                "source_precision": pr22_metrics["retrieval"]["source_precision"],
                "retrieval_mean_ms": pr22_metrics["latency_ms"]["retrieval_mean"],
                "retrieval_p95_ms": pr22_metrics["latency_ms"]["retrieval_p95"],
            },
            "pr24": pr24_metrics,
        },
        "ranking": {
            "hybrid_hit_rate_at_k": _mean(hybrid_hits),
            "reranked_hit_rate_at_k": _mean(reranked_hits),
            "hybrid_mrr_at_k": _mean(hybrid_mrr),
            "reranked_mrr_at_k": _mean(reranked_mrr),
            "hit_rate_gain": round(_mean(reranked_hits) - _mean(hybrid_hits), 3),
            "mrr_gain": round(_mean(reranked_mrr) - _mean(hybrid_mrr), 3),
        },
        "latency_ms": {
            "controlled_hybrid_mean": _mean(hybrid_latencies),
            "controlled_hybrid_p95": _p95(hybrid_latencies),
            "controlled_reranked_mean": _mean(total_latencies),
            "controlled_reranked_p95": _p95(total_latencies),
            "reranker_overhead_mean": _mean(overhead_latencies),
            "reranker_overhead_p95": _p95(overhead_latencies),
        },
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara ranking híbrido e reranking sem rede.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/reranker_eval.json"))
    parser.add_argument("--baseline-pr22", type=Path, default=Path("evals/baseline_report.json"))
    parser.add_argument("--baseline-pr24", type=Path, default=Path("evals/hybrid_search_report.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/reranker_report.json"))
    args = parser.parse_args()
    report = evaluate_reranker(
        json.loads(args.dataset.read_text(encoding="utf-8")),
        baseline_pr22=json.loads(args.baseline_pr22.read_text(encoding="utf-8")),
        baseline_pr24=json.loads(args.baseline_pr24.read_text(encoding="utf-8")),
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ranking": report["ranking"], "latency_ms": report["latency_ms"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
