#!/usr/bin/env python3
"""Sweep offline determinístico do limiar de distância coseno do RAG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # suporta `python scripts/...` e importação nos testes
    from .eval_rag import load_dataset
except ImportError:  # pragma: no cover - caminho da execução direta
    from eval_rag import load_dataset

THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.50)
MIN_SOURCE_RECALL = 0.95


def load_candidates(path: Path, dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Fixture de candidatos inválida: {exc}") from exc
    if payload.get("dataset_version") != dataset["dataset_version"] or not isinstance(payload.get("cases"), list):
        raise ValueError("Fixture de candidatos não corresponde ao dataset.")
    corpus_tenants = {item["id"]: item["tenant_id"] for item in dataset["corpus"]}
    dataset_cases = {case["id"]: case for case in dataset["cases"]}
    candidates = {item.get("id"): item for item in payload["cases"] if isinstance(item, dict)}
    if set(candidates) != set(dataset_cases):
        raise ValueError("Fixture de candidatos deve conter exatamente os casos do dataset.")
    for case_id, item in candidates.items():
        if item.get("tenant_id") != dataset_cases[case_id]["tenant_id"]:
            raise ValueError(f"Caso {case_id} possui tenant divergente.")
        for candidate in item.get("candidates", []):
            source_id, distance = candidate.get("source_id"), candidate.get("distance")
            if corpus_tenants.get(source_id) != item["tenant_id"]:
                raise ValueError(f"Caso {case_id} referencia candidato de outro tenant.")
            if not isinstance(distance, (int, float)) or distance < 0:
                raise ValueError(f"Caso {case_id} possui distância inválida.")
    return candidates


def sweep(dataset: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> list[dict[str, float]]:
    rows = []
    for threshold in THRESHOLDS:
        expected_total = found_expected = selected_total = false_positive_cases = refusal_cases = correct_refusals = 0
        for case in dataset["cases"]:
            expected = set(case["expected"]["source_ids"])
            selected = {
                item["source_id"] for item in candidates[case["id"]]["candidates"]
                if item["is_current"] and item["distance"] <= threshold
            }
            expected_total += len(expected)
            found_expected += len(expected & selected)
            selected_total += len(selected)
            if case["expected"]["should_refuse"]:
                refusal_cases += 1
                false_positive_cases += bool(selected)
                correct_refusals += not bool(selected)
        recall = found_expected / expected_total if expected_total else 1.0
        precision = found_expected / selected_total if selected_total else 1.0
        rows.append({
            "threshold": threshold,
            "source_recall": round(recall, 3),
            "source_precision": round(precision, 3),
            "false_positive_rate": round(false_positive_cases / refusal_cases, 3),
            "correct_refusal": round(correct_refusals / refusal_cases, 3),
        })
    return rows


def select_threshold(rows: list[dict[str, float]]) -> tuple[float, str]:
    eligible = [row for row in rows if row["source_recall"] >= MIN_SOURCE_RECALL and row["correct_refusal"] == 1.0]
    if not eligible:
        return 0.45, "Nenhum candidato preservou recall mínimo e recusa correta; mantido o default atual."
    selected = min(eligible, key=lambda row: (row["false_positive_rate"], row["threshold"]))
    return selected["threshold"], "Menor limiar com recall de fontes ≥ 0,95, recusa correta de 100% e menor falso positivo."


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra SIMILARITY_THRESHOLD sem rede ou LLM.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/rag_baseline_dataset.json"))
    parser.add_argument("--candidates", type=Path, default=Path("evals/similarity_threshold_candidates.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/threshold_calibration_report.json"))
    args = parser.parse_args()
    dataset = load_dataset(args.dataset)
    rows = sweep(dataset, load_candidates(args.candidates, dataset))
    selected, decision = select_threshold(rows)
    report = {"report_version": 1, "dataset_version": dataset["dataset_version"], "fixed_retrieval_configuration": dataset["retrieval_configuration"], "thresholds": rows, "selection": {"previous_threshold": 0.45, "selected_threshold": selected, "rule": decision}}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
