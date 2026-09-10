#!/usr/bin/env python3
"""Executa uma baseline offline e deterministica do fluxo RAG.

O corpus, as perguntas e as expectativas sao sinteticos. Recuperacao e
geracao usam adaptadores locais deliberadamente simples, permitindo exercitar
o fluxo completo sem PGVector, modelo de embeddings, LLM ou rede.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

RUNNER_VERSION = "2.0"
REQUIRED_CASE_FIELDS = {
    "id", "tenant_id", "fixture_corpus", "question", "expected",
}
REQUIRED_SOURCE_FIELDS = {
    "id", "tenant_id", "type", "label", "content", "retrieval_queries",
}
SUPPORTED_SOURCE_TYPES = {"faq", "event", "document_chunk"}
REFUSAL_ANSWER = "Não tenho essa informação. Consulte a instituição."
REFUSAL_MARKERS = (
    "nao tenho essa informacao", "nao encontrei informacao",
    "nao possuo essa informacao", "consulte a instituicao",
)
Clock = Callable[[], int]


@dataclass(frozen=True)
class RetrievedSource:
    source: dict[str, Any]
    similarity: float


@dataclass(frozen=True)
class PipelineObservation:
    source_ids: list[str]
    answer: str
    retrieval_latency_ms: float
    generation_latency_ms: float
    retrieval_scores: list[dict[str, Any]]


def _normalized_token_list(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", normalized)


def _normalized_tokens(value: str) -> set[str]:
    return set(_normalized_token_list(value))


def _normalized_text(value: str) -> str:
    return " ".join(_normalized_token_list(value))


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
    index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return round(ordered[index], 3)


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} deve usar o formato ISO YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} deve usar o formato ISO YYYY-MM-DD.") from exc


def load_dataset(path: Path) -> dict[str, Any]:
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Dataset invalido: {exc}") from exc

    required_dataset = {
        "dataset_version", "evaluation_date", "retrieval_configuration",
        "evaluation_adapter", "corpus", "cases",
    }
    if not isinstance(dataset, dict) or not required_dataset <= set(dataset):
        raise ValueError("Dataset exige versao, configuracoes, corpus, casos e data de avaliacao.")
    if not isinstance(dataset["corpus"], list) or not isinstance(dataset["cases"], list):
        raise ValueError("Corpus e cases devem ser listas.")
    _parse_date(dataset["evaluation_date"], "evaluation_date")
    cases = dataset["cases"]
    if not 20 <= len(cases) <= 30:
        raise ValueError("Dataset inicial deve conter entre 20 e 30 casos.")

    adapter = dataset["evaluation_adapter"]
    if not isinstance(adapter, dict):
        raise ValueError("evaluation_adapter deve ser um objeto.")
    if not isinstance(adapter.get("similarity_threshold"), (int, float)):
        raise ValueError("evaluation_adapter exige similarity_threshold numerico.")
    if not 0 <= float(adapter["similarity_threshold"]) <= 1:
        raise ValueError("similarity_threshold do adaptador deve estar entre zero e um.")
    if not isinstance(adapter.get("top_k"), int) or adapter["top_k"] <= 0:
        raise ValueError("evaluation_adapter exige top_k inteiro positivo.")

    source_ids: set[str] = set()
    source_tenants: dict[str, str] = {}
    for source in dataset["corpus"]:
        if not isinstance(source, dict) or not REQUIRED_SOURCE_FIELDS <= set(source):
            raise ValueError("Cada fonte exige id, tenant, tipo, rotulo, conteudo e consultas de recuperacao.")
        if any(not isinstance(source[field], str) or not source[field].strip()
               for field in ("id", "tenant_id", "type", "label", "content")):
            raise ValueError("Campos textuais da fonte nao podem estar vazios.")
        if source["type"] not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(f"Tipo de fonte nao suportado: {source['type']}")
        if (not isinstance(source["retrieval_queries"], list)
                or not source["retrieval_queries"]
                or any(not isinstance(query, str) or not query.strip()
                       for query in source["retrieval_queries"])):
            raise ValueError(f"Fonte {source['id']} exige retrieval_queries textuais.")
        if source["type"] == "document_chunk":
            _parse_date(source.get("valid_until"), f"valid_until de {source['id']}")
        if source["id"] in source_ids:
            raise ValueError(f"Fonte duplicada: {source['id']}")
        source_ids.add(source["id"])
        source_tenants[source["id"]] = source["tenant_id"]

    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not REQUIRED_CASE_FIELDS <= set(case):
            raise ValueError("Caso sem campos obrigatorios de avaliacao.")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError(f"Caso duplicado ou invalido: {case_id!r}")
        case_ids.add(case_id)
        if not isinstance(case["tenant_id"], str) or not isinstance(case["question"], str):
            raise ValueError(f"Caso {case_id} exige tenant e pergunta textuais.")
        expected = case["expected"]
        required_expected = {
            "should_refuse", "expected_answer", "source_ids",
            "citation_labels", "human_review",
        }
        if not isinstance(expected, dict) or not required_expected <= set(expected):
            raise ValueError(f"Caso {case_id} possui expectativa incompleta.")
        if (not isinstance(expected["should_refuse"], bool)
                or not isinstance(expected["expected_answer"], str)
                or not isinstance(expected["citation_labels"], list)
                or not isinstance(expected["human_review"], str)):
            raise ValueError(f"Caso {case_id} possui tipos de expectativa invalidos.")
        if not isinstance(expected["source_ids"], list) or not set(expected["source_ids"]) <= source_ids:
            raise ValueError(f"Caso {case_id} referencia fonte inexistente.")
        if any(source_tenants[source_id] != case["tenant_id"] for source_id in expected["source_ids"]):
            raise ValueError(f"Caso {case_id} referencia fonte de outro tenant.")
        if bool(expected["should_refuse"]) != (not expected["source_ids"]):
            raise ValueError(f"Caso {case_id} possui expectativa de recusa inconsistente.")
    return dataset


def _cosine_similarity(left: str, right: str) -> float:
    left_vector = Counter(_normalized_token_list(left))
    right_vector = Counter(_normalized_token_list(right))
    if not left_vector or not right_vector:
        return 0.0
    dot_product = sum(count * right_vector[token] for token, count in left_vector.items())
    left_norm = math.sqrt(sum(count * count for count in left_vector.values()))
    right_norm = math.sqrt(sum(count * count for count in right_vector.values()))
    return dot_product / (left_norm * right_norm)


def _has_conflicting_numbers(question: str, source: dict[str, Any]) -> bool:
    question_numbers = {token for token in _normalized_tokens(question) if token.isdigit()}
    if not question_numbers:
        return False
    source_text = " ".join([source["label"], *source["retrieval_queries"], source["content"]])
    source_numbers = {token for token in _normalized_tokens(source_text) if token.isdigit()}
    return bool(source_numbers and question_numbers.isdisjoint(source_numbers))


def _source_is_valid(source: dict[str, Any], evaluation_date: date) -> bool:
    return (
        source["type"] != "document_chunk"
        or _parse_date(source["valid_until"], f"valid_until de {source['id']}") >= evaluation_date
    )


def retrieve(dataset: dict[str, Any], tenant_id: str, question: str) -> list[RetrievedSource]:
    """Recupera fontes locais respeitando tenant, validade, limiar e ordem estavel."""
    evaluation_date = _parse_date(dataset["evaluation_date"], "evaluation_date")
    adapter = dataset["evaluation_adapter"]
    threshold = float(adapter["similarity_threshold"])
    candidates: list[RetrievedSource] = []
    for source in dataset["corpus"]:
        if source["tenant_id"] != tenant_id or not _source_is_valid(source, evaluation_date):
            continue
        if _has_conflicting_numbers(question, source):
            continue
        similarity = max(
            _cosine_similarity(question, supported_query)
            for supported_query in source["retrieval_queries"]
        )
        if similarity >= threshold:
            candidates.append(RetrievedSource(source=source, similarity=similarity))
    candidates.sort(key=lambda item: (-item.similarity, item.source["id"]))
    return candidates[: adapter["top_k"]]


def generate(question: str, retrieved: list[RetrievedSource]) -> str:
    """Gera resposta extrativa local a partir da melhor fonte recuperada."""
    if not retrieved:
        return REFUSAL_ANSWER
    source = retrieved[0].source
    segments = [segment.strip() for segment in source["content"].splitlines() if segment.strip()]
    answer = max(
        enumerate(segments),
        key=lambda item: (_cosine_similarity(question, item[1]), -item[0]),
    )[1].rstrip(".")
    if source["type"] == "document_chunk":
        return f"{answer}, conforme {source['label']}."
    return f"{answer}."


def _elapsed_ms(start_ns: int, end_ns: int) -> float:
    return round(max(0, end_ns - start_ns) / 1_000_000, 3)


def run_pipeline(
    dataset: dict[str, Any],
    case: dict[str, Any],
    *,
    clock: Clock = time.perf_counter_ns,
) -> PipelineObservation:
    """Executa recuperacao e geracao sem consultar campos de expectativa."""
    retrieval_start = clock()
    retrieved = retrieve(dataset, case["tenant_id"], case["question"])
    retrieval_latency = _elapsed_ms(retrieval_start, clock())
    generation_start = clock()
    answer = generate(case["question"], retrieved)
    generation_latency = _elapsed_ms(generation_start, clock())
    return PipelineObservation(
        source_ids=[item.source["id"] for item in retrieved],
        answer=answer,
        retrieval_latency_ms=retrieval_latency,
        generation_latency_ms=generation_latency,
        retrieval_scores=[
            {"source_id": item.source["id"], "similarity": round(item.similarity, 6)}
            for item in retrieved
        ],
    )


def _mean(values: list[float]) -> float:
    return round(fmean(values), 3) if values else 0.0


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate(dataset: dict[str, Any], *, clock: Clock = time.perf_counter_ns) -> dict[str, Any]:
    """Executa o pipeline e calcula metricas por etapa e por caso."""
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
        expected = case["expected"]
        observed = run_pipeline(dataset, case, clock=clock)
        expected_sources = set(expected["source_ids"])
        found_sources = set(observed.source_ids)
        matched_sources = expected_sources & found_sources
        recall = len(matched_sources) / len(expected_sources) if expected_sources else 1.0
        precision = len(matched_sources) / len(found_sources) if found_sources else (1.0 if not expected_sources else 0.0)
        answer = observed.answer
        refused = _is_refusal(answer)
        is_refusal_case = bool(expected["should_refuse"])
        answer_similarity = token_f1(expected["expected_answer"], answer)
        required_terms = _normalized_tokens(expected["expected_answer"])
        answer_terms = _normalized_tokens(answer)
        answer_correct = refused if is_refusal_case else not refused and required_terms <= answer_terms
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
        retrieval_latencies.append(observed.retrieval_latency_ms)
        generation_latencies.append(observed.generation_latency_ms)
        case_results.append({
            "id": case["id"],
            "tenant_id": case["tenant_id"],
            "fixture_corpus": case["fixture_corpus"],
            "tags": case.get("tags", []),
            "retrieval": {
                "recall": round(recall, 3),
                "precision": round(precision, 3),
                "expected_source_ids": sorted(expected_sources),
                "found_source_ids": sorted(found_sources),
                "scores": observed.retrieval_scores,
            },
            "generation": {
                "answer": answer,
                "semantic_token_f1": round(answer_similarity, 3),
                "correct_by_rule": answer_correct,
                "refusal_correct": refused == is_refusal_case if is_refusal_case else None,
            },
            "source": {
                "citation_expected": bool(expected["citation_labels"]),
                "citation_present": citation_present,
            },
            "latency_ms": {
                "retrieval": observed.retrieval_latency_ms,
                "generation": observed.generation_latency_ms,
            },
            "human_review": expected["human_review"],
            "failure_reasons": [
                reason for reason, failed in (
                    ("retrieval", recall < 1 or precision < 1),
                    ("answer", not answer_correct),
                    ("citation", not citation_present),
                ) if failed
            ],
        })

    return {
        "report_version": 2,
        "runner_version": RUNNER_VERSION,
        "dataset_version": dataset.get("dataset_version"),
        "dataset_sha256": _canonical_hash(dataset),
        "corpus_sha256": _canonical_hash(dataset["corpus"]),
        "mode": "offline-executable-deterministic-pipeline",
        "evaluation_date": dataset["evaluation_date"],
        "retrieval_configuration": dataset["retrieval_configuration"],
        "evaluation_adapter": dataset["evaluation_adapter"],
        "case_count": len(case_results),
        "metrics": {
            "retrieval": {
                "source_recall": _mean(retrieval_recall),
                "source_precision": _mean(retrieval_precision),
            },
            "generation": {
                "semantic_token_f1": _mean(similarity),
                "correctness_by_rule": _mean(correctness),
                "correct_refusal": _mean(refusals),
            },
            "source": {"citation_presence": _mean(citations)},
            "latency_ms": {
                "retrieval_mean": _mean(retrieval_latencies),
                "retrieval_p95": percentile_95(retrieval_latencies),
                "generation_mean": _mean(generation_latencies),
                "generation_p95": percentile_95(generation_latencies),
            },
        },
        "cases": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa a baseline sintetica do RAG sem rede.")
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
