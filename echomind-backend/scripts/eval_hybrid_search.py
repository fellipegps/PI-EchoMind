#!/usr/bin/env python3
"""Comparação offline, determinística e versionada da busca híbrida."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def evaluate_hybrid(dataset: dict[str, Any]) -> dict[str, Any]:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval híbrido exige uma lista não vazia de casos.")
    by_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"vector": [], "hybrid": []})
    details = []
    for case in cases:
        expected = case["expected_source_id"]
        vector = set(case["vector_source_ids"])
        lexical = set(case["lexical_source_ids"])
        hybrid = vector | lexical
        vector_hit = float(expected in vector)
        hybrid_hit = float(expected in hybrid)
        by_category[case["category"]]["vector"].append(vector_hit)
        by_category[case["category"]]["hybrid"].append(hybrid_hit)
        details.append({"id": case["id"], "category": case["category"], "vector_hit": bool(vector_hit), "hybrid_hit": bool(hybrid_hit)})
    category_metrics = {
        category: {name + "_recall": round(sum(values) / len(values), 3) for name, values in metrics.items()}
        for category, metrics in sorted(by_category.items())
    }
    return {
        "report_version": 1,
        "dataset_version": dataset.get("dataset_version"),
        "mode": "offline-synthetic-comparison",
        "metrics_by_category": category_metrics,
        "overall": {
            "vector_recall": round(sum(item["vector_hit"] for item in details) / len(details), 3),
            "hybrid_recall": round(sum(item["hybrid_hit"] for item in details) / len(details), 3),
        },
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara recall vetorial e híbrido sem rede.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/hybrid_search_eval.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/hybrid_search_report.json"))
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = evaluate_hybrid(dataset)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
