#!/usr/bin/env python3
"""Runner offline e deterministico para a baseline de avaliacao do RAG.

Nao inicializa embeddings, PGVector ou LLM. O runner avalia observacoes
versionadas; uma captura futura do runtime deve ser convertida para o mesmo
formato antes de ser comparada com esta baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path
from statistics import fmean
from typing import Any

RUNNER_VERSION = "1.0"
REQUIRED_CASE_FIELDS = {
    "id", "tenant_id", "fixture_corpus", "question", "expected", "observed",
}
REFUSAL_MARKERS = (
    "nao tenho essa informacao", "nao encontrei informacao",
    "nao possuo essa informacao", "consulte a instituicao",
)


def _normalized_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]+", normalized))


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _is_refusal(answer: str) -> bool:
    normalized = _normalized_text(answer)
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def token_f1(expected: str, actual: str) -> float:
    """Similaridade lexical explicita; nao substitui a revisao humana."""
    expected_tokens, actual_tokens = _normalized_tokens(expected), _normalized_tokens(actual)
    if not expected_tokens or not actual_tokens:
        return 0.0
    overlap = len(expected_tokens & actual_tokens)
    precision, recall = overlap / len(actual_tokens), overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)]


def load_dataset(path: Path) -> dict[str, Any]:
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Dataset invalido: {exc}") from exc

    if not isinstance(dataset, dict) or not {"dataset_version", "corpus", "cases"} <= set(dataset):
        raise ValueError("Dataset exige dataset_version, corpus e cases.")
    if not isinstance(dataset["corpus"], list) or not isinstance(dataset.get("cases"), list):
        raise ValueError("Dataset deve ser um objeto com a lista 'cases'.")
    cases = dataset["cases"]
    if not 20 <= len(cases) <= 30:
        raise ValueError("Dataset inicial deve conter entre 20 e 30 casos.")

    source_ids: set[str] = set()
    source_tenants: dict[str, str] = {}
    for source in dataset["corpus"]:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not isinstance(source.get("tenant_id"), str):
            raise ValueError("Cada fonte do corpus exige id e tenant_id textuais.")
        if source["id"] in source_ids:
            raise ValueError(f"Fonte duplicada: {source['id']}")
        source_ids.add(source["id"])
        source_tenants[source["id"]] = source["tenant_id"]

    case_ids = set()
    for case in cases:
        if not isinstance(case, dict) or not REQUIRED_CASE_FIELDS <= set(case):
            raise ValueError("Caso sem campos obrigatorios de avaliacao.")
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id in case_ids:
            raise ValueError(f"Caso duplicado ou invalido: {case_id!r}")
        case_ids.add(case_id)
        expected, observed = case["expected"], case["observed"]
        if not isinstance(expected, dict) or not isinstance(observed, dict):
            raise ValueError(f"Caso {case_id} exige expected e observed como objetos.")
        required_expected = {"should_refuse", "expected_answer", "source_ids", "citation_labels", "human_review"}
        if not required_expected <= set(expected):
            raise ValueError(f"Caso {case_id} possui expectativa incompleta.")
        if not {"source_ids", "answer", "retrieval_latency_ms", "generation_latency_ms"} <= set(observed):
            raise ValueError(f"Caso {case_id} possui observacao incompleta.")
        if not isinstance(expected["source_ids"], list) or not set(expected["source_ids"]) <= set(source_tenants):
            raise ValueError(f"Caso {case_id} referencia fonte inexistente.")
        if any(source_tenants[source_id] != case["tenant_id"] for source_id in expected["source_ids"]):
            raise ValueError(f"Caso {case_id} referencia fonte de outro tenant.")
        if any(not isinstance(observed[key], (int, float)) or observed[key] < 0
               for key in ("retrieval_latency_ms", "generation_latency_ms")):
            raise ValueError(f"Caso {case_id} possui latencia invalida.")
    return dataset


def _mean(values: list[float]) -> float:
    return round(fmean(values), 3) if values else 0.0


def evaluate(dataset: dict[str, Any]) -> dict[str, Any]:
    """Calcula metricas por etapa e mantem o detalhe rastreavel por caso."""
    case_results: list[dict[str, Any]] = []
    retrieval_recall: list[float] = []
    retrieval_precision: list[float] = []
    correctness: list[float] = []
    similarity: list[float] = []
    refusals: list[float] = []
    citations: list[float] = []
    retrieval_latencies: list[float] = []
    generation_latencies: list[float] = []

    for case in dataset["cases"]:
        expected, observed = case["expected"], case["observed"]
        expected_sources = set(expected["source_ids"])
        found_sources = set(observed["source_ids"])
        matched_sources = expected_sources & found_sources
        recall = len(matched_sources) / len(expected_sources) if expected_sources else 1.0
        precision = len(matched_sources) / len(found_sources) if found_sources else (1.0 if not expected_sources else 0.0)
        answer = observed["answer"]
        refused = _is_refusal(answer)
        is_refusal_case = bool(expected["should_refuse"])
        answer_similarity = token_f1(expected["expected_answer"], answer)
        required_terms = _normalized_tokens(expected["expected_answer"])
        answer_terms = _normalized_tokens(answer)
        if is_refusal_case:
            answer_correct = refused
        else:
            answer_correct = not refused and required_terms <= answer_terms
        citation_present = (
            any(label.casefold() in answer.casefold() for label in expected["citation_labels"])
            if expected["citation_labels"] else True
        )

        retrieval_recall.append(recall)
        retrieval_precision.append(precision)
        correctness.append(float(answer_correct))
        similarity.append(answer_similarity)
        if is_refusal_case:
            refusals.append(float(refused))
        if expected["citation_labels"]:
            citations.append(float(citation_present))
        retrieval_latencies.append(float(observed["retrieval_latency_ms"]))
        generation_latencies.append(float(observed["generation_latency_ms"]))
        case_results.append({
            "id": case["id"], "tags": case.get("tags", []),
            "retrieval": {"recall": round(recall, 3), "precision": round(precision, 3), "expected_source_ids": sorted(expected_sources), "found_source_ids": sorted(found_sources)},
            "generation": {"semantic_token_f1": round(answer_similarity, 3), "correct_by_rule": answer_correct, "refusal_correct": refused == is_refusal_case if is_refusal_case else None},
            "source": {"citation_expected": bool(expected["citation_labels"]), "citation_present": citation_present},
            "latency_ms": {"retrieval": observed["retrieval_latency_ms"], "generation": observed["generation_latency_ms"]},
            "human_review": expected["human_review"],
            "failure_reasons": [reason for reason, failed in (("retrieval", recall < 1), ("answer", not answer_correct), ("citation", not citation_present)) if failed],
        })

    return {
        "report_version": 1,
        "runner_version": RUNNER_VERSION,
        "dataset_version": dataset.get("dataset_version"),
        "mode": "offline-synthetic-observations",
        "retrieval_configuration": dataset.get("retrieval_configuration", {}),
        "case_count": len(case_results),
        "metrics": {
            "retrieval": {"source_recall": _mean(retrieval_recall), "source_precision": _mean(retrieval_precision)},
            "generation": {"semantic_token_f1": _mean(similarity), "correctness_by_rule": _mean(correctness), "correct_refusal": _mean(refusals)},
            "source": {"citation_presence": _mean(citations)},
            "latency_ms": {"retrieval_mean": _mean(retrieval_latencies), "retrieval_p95": percentile_95(retrieval_latencies), "generation_mean": _mean(generation_latencies), "generation_p95": percentile_95(generation_latencies)},
        },
        "cases": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia observacoes sinteticas do RAG sem rede.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/rag_baseline_dataset.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/baseline_report.json"))
    args = parser.parse_args()
    report = evaluate(load_dataset(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
