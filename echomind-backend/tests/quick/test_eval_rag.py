"""Contratos da baseline RAG executavel, sintetica e sem rede."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import pytest

from scripts.eval_rag import evaluate, load_dataset, retrieve, run_pipeline, token_f1


DATASET = Path(__file__).parents[2] / "evals" / "rag_baseline_dataset.json"


def _fixed_clock(step_ns: int = 1_000_000):
    current = -step_ns

    def clock() -> int:
        nonlocal current
        current += step_ns
        return current

    return clock


def test_dataset_schema_is_valid_and_has_expected_coverage() -> None:
    dataset = load_dataset(DATASET)

    assert len(dataset["cases"]) == 20
    assert all("observed" not in case for case in dataset["cases"])
    assert all(source["content"] for source in dataset["corpus"])
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
    del payload["cases"][0]["question"]
    invalid = tmp_path / "missing-field.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="campos obrigatorios"):
        load_dataset(invalid)


def test_scorer_has_known_results() -> None:
    assert token_f1("prazo cinco dias", "prazo cinco dias") == 1.0
    assert token_f1("prazo cinco dias", "outro assunto") == 0.0


def test_pipeline_output_is_not_read_from_expected_fields() -> None:
    dataset = load_dataset(DATASET)
    case = copy.deepcopy(dataset["cases"][0])
    original = run_pipeline(dataset, case, clock=_fixed_clock())
    case["expected"]["expected_answer"] = "resposta adulterada"
    case["expected"]["source_ids"] = []
    case["expected"]["should_refuse"] = True

    after_expectation_change = run_pipeline(dataset, case, clock=_fixed_clock())

    assert after_expectation_change.answer == original.answer
    assert after_expectation_change.source_ids == original.source_ids


def test_retrieval_preserves_tenant_and_document_validity() -> None:
    dataset = load_dataset(DATASET)

    cross_tenant = retrieve(dataset, "tenant-alfa", "Qual o horário de atendimento?")
    expired = retrieve(dataset, "tenant-alfa", "O edital de bolsa de 2024 ainda vale?")

    assert cross_tenant == []
    assert expired == []


def test_runner_is_deterministic_with_controlled_clock_and_does_not_use_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = load_dataset(DATASET)

    def reject_network(*_args, **_kwargs):
        raise AssertionError("A baseline offline tentou acessar a rede.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket, "socket", reject_network)
    first = evaluate(dataset, clock=_fixed_clock())
    second = evaluate(dataset, clock=_fixed_clock())

    assert first == second
    assert first["mode"] == "offline-executable-deterministic-pipeline"
    assert first["report_version"] == 2
    assert len(first["dataset_sha256"]) == 64
    assert len(first["corpus_sha256"]) == 64
    assert first["case_count"] == 20
    assert first["metrics"]["retrieval"] == {
        "source_recall": 1.0,
        "source_precision": 1.0,
    }
    assert first["metrics"]["generation"]["correct_refusal"] == 1.0
    assert first["metrics"]["source"]["citation_presence"] == 1.0
    assert first["metrics"]["latency_ms"] == {
        "retrieval_mean": 1.0,
        "retrieval_p95": 1.0,
        "generation_mean": 1.0,
        "generation_p95": 1.0,
    }
    assert {case["tenant_id"] for case in first["cases"]} == {"tenant-alfa", "tenant-beta"}
    assert all(case["generation"]["answer"] for case in first["cases"])
    assert all(case["failure_reasons"] == [] for case in first["cases"])
