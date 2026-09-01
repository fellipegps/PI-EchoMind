#!/usr/bin/env python3
"""Eval offline da completude contextual antes/depois de Parent-Child."""

from __future__ import annotations

import argparse
import json
import statistics
import unicodedata
from pathlib import Path
from typing import Any, Sequence


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())


def _complete(context: str, required_terms: Sequence[str]) -> float:
    normalized_context = _normalized(context)
    return float(all(_normalized(term) in normalized_context for term in required_terms))


def _mean(values: Sequence[float]) -> float:
    return round(statistics.fmean(values), 3)


def _p95(values: Sequence[float]) -> float:
    ordered = sorted(values)
    position = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return round(ordered[position], 3)


def evaluate_parent_child(dataset: dict[str, Any], pr25_report: dict[str, Any]) -> dict[str, Any]:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval Parent-Child exige uma lista nao vazia de casos.")

    child_complete: list[float] = []
    parent_complete: list[float] = []
    pr25_latencies: list[float] = []
    parent_latencies: list[float] = []
    context_growth: list[float] = []
    details: list[dict[str, Any]] = []

    for case in cases:
        required_terms = case["required_terms"]
        child_context = case["child_context"]
        parent_context = case["parent_context"]
        baseline_latency = float(case["pr25_latency_ms"])
        lookup_latency = float(case["parent_lookup_latency_ms"])
        child_score = _complete(child_context, required_terms)
        parent_score = _complete(parent_context, required_terms)

        child_complete.append(child_score)
        parent_complete.append(parent_score)
        pr25_latencies.append(baseline_latency)
        parent_latencies.append(baseline_latency + lookup_latency)
        context_growth.append(len(parent_context) / max(1, len(child_context)))
        details.append(
            {
                "id": case["id"],
                "pr25_context_complete": bool(child_score),
                "parent_context_complete": bool(parent_score),
                "context_growth_ratio": round(context_growth[-1], 3),
            }
        )

    return {
        "version": 1,
        "mode": "offline-synthetic-parent-child-comparison",
        "pr25_reference": {
            "reranked_hit_rate_at_k": pr25_report["ranking"]["reranked_hit_rate_at_k"],
            "reranked_mrr_at_k": pr25_report["ranking"]["reranked_mrr_at_k"],
            "controlled_reranked_mean_ms": pr25_report["latency_ms"]["controlled_reranked_mean"],
        },
        "quality": {
            "pr25_context_complete_rate": _mean(child_complete),
            "parent_context_complete_rate": _mean(parent_complete),
            "context_complete_gain": round(_mean(parent_complete) - _mean(child_complete), 3),
        },
        "latency_ms": {
            "controlled_pr25_mean": _mean(pr25_latencies),
            "controlled_parent_child_mean": _mean(parent_latencies),
            "controlled_parent_child_p95": _p95(parent_latencies),
            "parent_lookup_overhead_mean": round(_mean(parent_latencies) - _mean(pr25_latencies), 3),
        },
        "context": {"mean_growth_ratio": _mean(context_growth)},
        "cases": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara contexto child-only e Parent-Child sem rede.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/parent_child_eval.json"))
    parser.add_argument("--pr25-report", type=Path, default=Path("evals/reranker_report.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/parent_child_report.json"))
    args = parser.parse_args()

    report = evaluate_parent_child(
        json.loads(args.dataset.read_text(encoding="utf-8")),
        json.loads(args.pr25_report.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("quality", "latency_ms", "context")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
