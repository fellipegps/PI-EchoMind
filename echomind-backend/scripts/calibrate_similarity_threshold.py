#!/usr/bin/env python3
"""Calibra o limiar de distancia coseno com embeddings produzidos na execucao."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Protocol, Sequence

try:  # suporta `python scripts/...` e importacao nos testes
    from .eval_rag import load_dataset
except ImportError:  # pragma: no cover - caminho da execucao direta
    from eval_rag import load_dataset

THRESHOLDS = tuple(round(value / 100, 2) for value in range(5, 51))
PREVIOUS_THRESHOLD = 0.45
MIN_SOURCE_RECALL = 0.95
MIN_SOURCE_PRECISION = 0.80
MIN_HOLDOUT_SOURCE_RECALL = 0.80
MIN_HOLDOUT_SOURCE_PRECISION = 0.75
DEFAULT_CANDIDATE_K = 10


class EmbeddingAdapter(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ProductionFastEmbedAdapter:
    """Adaptador do mesmo modelo/backend usados no runtime, sem LLM ou banco."""

    def __init__(
        self,
        *,
        model_name: str,
        dimensions: int,
        cache_dir: Path,
        allow_model_download: bool,
    ) -> None:
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType

        if not any(model["model"] == model_name for model in TextEmbedding.list_supported_models()):
            if model_name != "intfloat/multilingual-e5-small":
                raise ValueError(f"Modelo FastEmbed nao registrado: {model_name}")
            TextEmbedding.add_custom_model(
                model=model_name,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=model_name),
                dim=dimensions,
                model_file="onnx/model.onnx",
                description="Multilingual E5 small para retrieval multilingue.",
                license="mit",
            )
        try:
            self._model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(cache_dir),
                local_files_only=not allow_model_download,
            )
        except ValueError as exc:
            raise RuntimeError(
                "Modelo de embeddings ausente no cache. Execute o warm-up local ou "
                "repita com --allow-model-download de forma explicita."
            ) from exc
        self.model_name = model_name
        self.dimensions = dimensions

    def _validated(self, vector: Sequence[float]) -> list[float]:
        values = [float(value) for value in vector]
        if len(values) != self.dimensions:
            raise ValueError(
                f"Embedding gerou {len(values)} dimensoes; esperado {self.dimensions}."
            )
        return values

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._validated(vector) for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._validated(next(self._model.query_embed(text)))


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def console_json(value: Any) -> str:
    """Mantem stdout compativel inclusive com consoles Windows cp1252."""
    return json.dumps(value, ensure_ascii=True, indent=2)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _source_is_current(source: dict[str, Any], evaluation_date: date) -> bool:
    return (
        source["type"] != "document_chunk"
        or _parse_date(source["valid_until"]) >= evaluation_date
    )


def _source_embedding_text(source: dict[str, Any]) -> str:
    """Aproxima o texto indexado por tipo sem usar expectativas dos casos."""
    if source["type"] == "faq":
        return f"Pergunta: {source['retrieval_queries'][0]}\nResposta: {source['content']}"
    if source["type"] == "event":
        return f"Evento: {source['label']}\n{source['content']}"
    return "\n".join([
        f"Fonte: {source['label']}",
        f"Valido ate: {source['valid_until']}",
        "",
        source["content"],
    ])


def _cosine_distance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Vetores de embedding devem ter a mesma dimensao nao vazia.")
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        raise ValueError("Embedding nao pode ser um vetor nulo.")
    return max(0.0, min(2.0, 1.0 - dot_product / (left_norm * right_norm)))


def generate_candidates(
    dataset: dict[str, Any],
    embeddings: EmbeddingAdapter,
    *,
    candidate_k: int = DEFAULT_CANDIDATE_K,
) -> dict[str, dict[str, Any]]:
    """Gera candidatos do corpus com o embedding configurado, por tenant."""
    if candidate_k <= 0:
        raise ValueError("candidate_k deve ser positivo.")
    corpus = dataset["corpus"]
    document_vectors = embeddings.embed_documents([
        _source_embedding_text(source) for source in corpus
    ])
    if len(document_vectors) != len(corpus):
        raise ValueError("O adaptador nao retornou um embedding por fonte.")
    evaluation_date = _parse_date(dataset["evaluation_date"])
    generated: dict[str, dict[str, Any]] = {}
    for case in dataset["cases"]:
        query_vector = embeddings.embed_query(case["question"])
        ranked = []
        for source, source_vector in zip(corpus, document_vectors):
            if source["tenant_id"] != case["tenant_id"]:
                continue
            ranked.append({
                "source_id": source["id"],
                "distance": round(_cosine_distance(query_vector, source_vector), 6),
                "is_current": _source_is_current(source, evaluation_date),
            })
        ranked.sort(key=lambda item: (item["distance"], item["source_id"]))
        generated[case["id"]] = {
            "id": case["id"],
            "tenant_id": case["tenant_id"],
            "candidates": ranked[:candidate_k],
        }
    return generated


def load_split(path: Path, dataset: dict[str, Any]) -> dict[str, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Split de avaliacao invalido: {exc}") from exc
    if payload.get("dataset_version") != dataset["dataset_version"]:
        raise ValueError("Split de avaliacao nao corresponde ao dataset.")
    calibration = payload.get("calibration")
    holdout = payload.get("holdout")
    if not isinstance(calibration, list) or not isinstance(holdout, list):
        raise ValueError("Split exige listas calibration e holdout.")
    all_ids = [*calibration, *holdout]
    dataset_ids = {case["id"] for case in dataset["cases"]}
    if not calibration or not holdout or len(all_ids) != len(set(all_ids)):
        raise ValueError("Split deve ter grupos nao vazios e sem casos duplicados.")
    if set(all_ids) != dataset_ids:
        raise ValueError("Split deve conter exatamente todos os casos do dataset.")
    return {"calibration": calibration, "holdout": holdout}


def _evaluate_threshold(
    dataset: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    case_ids: Sequence[str],
    threshold: float,
) -> dict[str, Any]:
    cases_by_id = {case["id"]: case for case in dataset["cases"]}
    top_k = int(dataset["retrieval_configuration"]["top_k"])
    expected_total = found_expected = selected_total = 0
    false_positive_cases = refusal_cases = correct_refusals = 0
    validity_leak_cases = 0
    details = []
    for case_id in case_ids:
        case = cases_by_id[case_id]
        expected = set(case["expected"]["source_ids"])
        raw_selected = [
            item for item in candidates[case_id]["candidates"]
            if item["distance"] <= threshold
        ]
        validity_leak_cases += bool(any(not item["is_current"] for item in raw_selected))
        selected_items = [item for item in raw_selected if item["is_current"]][:top_k]
        selected = {item["source_id"] for item in selected_items}
        expected_total += len(expected)
        found_expected += len(expected & selected)
        selected_total += len(selected)
        if case["expected"]["should_refuse"]:
            refusal_cases += 1
            false_positive_cases += bool(selected)
            correct_refusals += not bool(selected)
        details.append({
            "id": case_id,
            "expected_source_ids": sorted(expected),
            "selected_source_ids": sorted(selected),
            "expired_candidates_filtered": sum(not item["is_current"] for item in raw_selected),
        })
    recall = found_expected / expected_total if expected_total else 1.0
    precision = found_expected / selected_total if selected_total else 1.0
    return {
        "threshold": threshold,
        "case_count": len(case_ids),
        "source_recall": round(recall, 3),
        "source_precision": round(precision, 3),
        "false_positive_rate": round(false_positive_cases / refusal_cases, 3),
        "correct_refusal": round(correct_refusals / refusal_cases, 3),
        "validity_filter_exercised_cases": validity_leak_cases,
        "cases": details,
    }


def sweep(
    dataset: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    case_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    selected_ids = case_ids or [case["id"] for case in dataset["cases"]]
    rows = []
    for threshold in THRESHOLDS:
        row = _evaluate_threshold(dataset, candidates, selected_ids, threshold)
        row.pop("cases")
        rows.append(row)
    return rows


def select_threshold(rows: list[dict[str, Any]]) -> tuple[float, str]:
    eligible = [
        row for row in rows
        if row["source_recall"] >= MIN_SOURCE_RECALL
        and row["source_precision"] >= MIN_SOURCE_PRECISION
        and row["correct_refusal"] == 1.0
    ]
    if not eligible:
        return (
            PREVIOUS_THRESHOLD,
            "Nenhum candidato preservou recall, precisao e recusa nos minimos; mantido o default anterior.",
        )
    selected = min(eligible, key=lambda row: (row["false_positive_rate"], row["threshold"]))
    return (
        selected["threshold"],
        "Menor limiar com recall >= 0,95, precisao >= 0,80, recusa correta de 100% e menor falso positivo.",
    )


def _row_for(rows: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    return next(row for row in rows if row["threshold"] == threshold)


def validate_on_holdout(
    candidate_threshold: float,
    holdout_rows: list[dict[str, Any]],
) -> tuple[float, str]:
    candidate = _row_for(holdout_rows, candidate_threshold)
    if (
        candidate["source_recall"] < MIN_HOLDOUT_SOURCE_RECALL
        or candidate["source_precision"] < MIN_HOLDOUT_SOURCE_PRECISION
        or candidate["correct_refusal"] < 1.0
    ):
        return (
            PREVIOUS_THRESHOLD,
            "Candidato rejeitado pelo holdout; mantido o default anterior de 0,45.",
        )
    return candidate_threshold, "Candidato aprovado no holdout sem perda critica."


def build_report(
    dataset: dict[str, Any],
    split: dict[str, list[str]],
    embeddings: EmbeddingAdapter,
    *,
    embedding_backend: str,
    embedding_version: str,
) -> dict[str, Any]:
    candidate_k = max(
        DEFAULT_CANDIDATE_K,
        int(dataset["retrieval_configuration"]["top_k"]) * 3,
    )
    candidates = generate_candidates(dataset, embeddings, candidate_k=candidate_k)
    calibration_rows = sweep(dataset, candidates, split["calibration"])
    holdout_rows = sweep(dataset, candidates, split["holdout"])
    calibration_candidate, calibration_rule = select_threshold(calibration_rows)
    calibration_metric = _row_for(calibration_rows, calibration_candidate)
    calibration_candidate_is_eligible = (
        calibration_metric["source_recall"] >= MIN_SOURCE_RECALL
        and calibration_metric["source_precision"] >= MIN_SOURCE_PRECISION
        and calibration_metric["correct_refusal"] == 1.0
    )
    if calibration_candidate_is_eligible:
        selected, holdout_decision = validate_on_holdout(
            calibration_candidate, holdout_rows
        )
    else:
        selected = PREVIOUS_THRESHOLD
        holdout_decision = (
            "Nenhum candidato chegou elegivel ao holdout; o default anterior "
            "tambem e reportado como insuficiente, mas foi mantido por seguranca."
        )
    return {
        "report_version": 2,
        "dataset_version": dataset["dataset_version"],
        "dataset_sha256": _canonical_hash(dataset),
        "split_sha256": _canonical_hash(split),
        "mode": "offline-production-embedding",
        "embedding_execution": {
            "backend": embedding_backend,
            "backend_version": embedding_version,
            "model": dataset["retrieval_configuration"]["embedding_model"],
            "dimensions": dataset["retrieval_configuration"]["embedding_dimensions"],
            "external_llm": False,
        },
        "fixed_retrieval_configuration": {
            **dataset["retrieval_configuration"],
            "candidate_k": candidate_k,
        },
        "split": split,
        "calibration_thresholds": calibration_rows,
        "holdout_thresholds": holdout_rows,
        "selection": {
            "previous_threshold": PREVIOUS_THRESHOLD,
            "calibration_candidate": calibration_candidate,
            "selected_threshold": selected,
            "calibration_rule": calibration_rule,
            "holdout_decision": holdout_decision,
            "selected_calibration_metrics": _evaluate_threshold(
                dataset, candidates, split["calibration"], selected
            ),
            "selected_holdout_metrics": _evaluate_threshold(
                dataset, candidates, split["holdout"], selected
            ),
        },
        "generated_candidates": list(candidates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra SIMILARITY_THRESHOLD sem banco ou LLM.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/rag_baseline_dataset.json"))
    parser.add_argument("--split", type=Path, default=Path("evals/similarity_threshold_split.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/threshold_calibration_report.json"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "echomind_models"))),
    )
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()
    dataset = load_dataset(args.dataset)
    retrieval_config = dataset["retrieval_configuration"]
    embeddings = ProductionFastEmbedAdapter(
        model_name=retrieval_config["embedding_model"],
        dimensions=int(retrieval_config["embedding_dimensions"]),
        cache_dir=args.cache_dir,
        allow_model_download=args.allow_model_download,
    )
    report = build_report(
        dataset,
        load_split(args.split, dataset),
        embeddings,
        embedding_backend="fastembed",
        embedding_version=importlib.metadata.version("fastembed"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(console_json(report["selection"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
