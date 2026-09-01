"""Contratos da baseline RAG: offline, sintética e sem dependência do runtime."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval_rag import evaluate, load_dataset, token_f1


DATASET = Path(__file__).parents[2] / "evals" / "rag_baseline_dataset.json"


def test_dataset_schema_is_valid_and_has_expected_coverage() -> None:
    dataset = load_dataset(DATASET)

    assert len(dataset["cases"]) == 20
    tags = {tag for case in dataset["cases"] for tag in case["tags"]}
    assert {"data", "numero", "requisito", "excecao", "recusa", "vigente", "vencido", "fonte"} <= tags
    assert {case["tenant_id"] for case in dataset["cases"]} == {"tenant-alfa", "tenant-beta"}


def test_dataset_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["cases"][1]["id"] = payload["cases"][0]["id"]
    invalid = tmp_path / "duplicate.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicado"):
        load_dataset(invalid)


def test_dataset_rejects_missing_required_case_field(tmp_path: Path) -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    del payload["cases"][0]["observed"]
    invalid = tmp_path / "missing-field.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="campos obrigatorios"):
        load_dataset(invalid)


def test_scorer_has_known_results() -> None:
    assert token_f1("prazo cinco dias", "prazo cinco dias") == 1.0
    assert token_f1("prazo cinco dias", "outro assunto") == 0.0


def test_runner_reports_separate_metrics_and_case_failures() -> None:
    report = evaluate(load_dataset(DATASET))

    assert report["mode"] == "offline-synthetic-observations"
    assert report["case_count"] == 20
    assert report["metrics"]["retrieval"]["source_recall"] == 1.0
    assert report["metrics"]["generation"]["correct_refusal"] == 1.0
    assert report["metrics"]["source"]["citation_presence"] == 1.0
    assert all(case["failure_reasons"] == [] for case in report["cases"])
