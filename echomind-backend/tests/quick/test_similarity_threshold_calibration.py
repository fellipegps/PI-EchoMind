"""Calibracao do threshold com candidatos produzidos por embeddings injetaveis."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from scripts.calibrate_similarity_threshold import (
    PREVIOUS_THRESHOLD,
    THRESHOLDS,
    build_report,
    console_json,
    generate_candidates,
    load_split,
    select_threshold,
    sweep,
    validate_on_holdout,
)
from scripts.eval_rag import load_dataset


EVALS = Path(__file__).parents[2] / "evals"


class ExpectedSourceFakeEmbeddings:
    """Fake local: associa perguntas respondiveis a uma fonte sem usar rede."""

    def __init__(self, dataset: dict) -> None:
        self._source_index = {
            source["id"]: index for index, source in enumerate(dataset["corpus"])
        }
        self._question_source = {
            case["question"]: (
                case["expected"]["source_ids"][0]
                if case["expected"]["source_ids"] else None
            )
            for case in dataset["cases"]
        }
        self._dimension = len(self._source_index) + 1

    def _vector(self, index: int) -> list[float]:
        vector = [0.0] * self._dimension
        vector[index] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == len(self._source_index)
        return [self._vector(index) for index in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        source_id = self._question_source[text]
        index = self._source_index[source_id] if source_id else self._dimension - 1
        return self._vector(index)


def _dataset_and_split() -> tuple[dict, dict[str, list[str]]]:
    dataset = load_dataset(EVALS / "rag_baseline_dataset.json")
    split = load_split(EVALS / "similarity_threshold_split.json", dataset)
    return dataset, split


def test_split_is_complete_disjoint_and_stratified() -> None:
    dataset, split = _dataset_and_split()
    cases = {case["id"]: case for case in dataset["cases"]}

    assert len(split["calibration"]) == 14
    assert len(split["holdout"]) == 6
    assert set(split["calibration"]).isdisjoint(split["holdout"])
    assert set(split["calibration"] + split["holdout"]) == set(cases)
    for group in split.values():
        assert {cases[case_id]["tenant_id"] for case_id in group} == {
            "tenant-alfa", "tenant-beta",
        }
        assert {cases[case_id]["expected"]["should_refuse"] for case_id in group} == {
            False, True,
        }


def test_generated_candidates_are_tenant_scoped_and_include_validity() -> None:
    dataset, _split = _dataset_and_split()
    candidates = generate_candidates(dataset, ExpectedSourceFakeEmbeddings(dataset))
    corpus = {source["id"]: source for source in dataset["corpus"]}

    assert set(candidates) == {case["id"] for case in dataset["cases"]}
    for item in candidates.values():
        assert all(
            corpus[candidate["source_id"]]["tenant_id"] == item["tenant_id"]
            for candidate in item["candidates"]
        )
    expired = candidates["alfa-09"]["candidates"]
    assert next(item for item in expired if item["source_id"] == "alfa-doc-expirado")["is_current"] is False


def test_sweep_uses_generated_distances_and_includes_declared_bounds() -> None:
    dataset, split = _dataset_and_split()
    candidates = generate_candidates(dataset, ExpectedSourceFakeEmbeddings(dataset))
    rows = sweep(dataset, candidates, split["calibration"])

    assert [row["threshold"] for row in rows] == list(THRESHOLDS)
    assert rows[0]["source_recall"] == 1.0
    assert rows[0]["source_precision"] == 1.0
    assert rows[0]["correct_refusal"] == 1.0


def test_selection_uses_calibration_and_holdout_can_reject_candidate() -> None:
    rows = [
        {
            "threshold": threshold,
            "source_recall": 1.0 if threshold >= 0.35 else 0.8,
            "source_precision": 1.0,
            "correct_refusal": 1.0,
            "false_positive_rate": 0.0,
        }
        for threshold in THRESHOLDS
    ]
    candidate, rule = select_threshold(rows)

    assert candidate == 0.35
    assert "recall" in rule
    selected, decision = validate_on_holdout(
        candidate,
        [{
            "threshold": 0.35,
            "source_recall": 0.75,
            "source_precision": 1.0,
            "correct_refusal": 1.0,
        }],
    )
    assert selected == PREVIOUS_THRESHOLD
    assert "rejeitado" in decision


def test_selection_keeps_previous_threshold_without_eligible_candidate() -> None:
    rows = [
        {
            "threshold": threshold,
            "source_recall": 0.9,
            "source_precision": 1.0,
            "correct_refusal": 1.0,
            "false_positive_rate": 0.0,
        }
        for threshold in THRESHOLDS
    ]

    selected, decision = select_threshold(rows)

    assert selected == PREVIOUS_THRESHOLD
    assert "mantido" in decision


def test_runner_with_fake_embeddings_is_deterministic_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, split = _dataset_and_split()

    def reject_network(*_args, **_kwargs):
        raise AssertionError("A calibracao tentou acessar a rede.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket, "socket", reject_network)
    first = build_report(
        dataset,
        split,
        ExpectedSourceFakeEmbeddings(dataset),
        embedding_backend="fake",
        embedding_version="test",
    )
    second = build_report(
        dataset,
        split,
        ExpectedSourceFakeEmbeddings(dataset),
        embedding_backend="fake",
        embedding_version="test",
    )

    assert first == second
    assert first["selection"]["selected_threshold"] == THRESHOLDS[0]
    assert len(first["generated_candidates"]) == 20
    assert console_json(first).encode("cp1252")


def test_split_rejects_duplicate_case(tmp_path: Path) -> None:
    dataset, _split = _dataset_and_split()
    payload = json.loads((EVALS / "similarity_threshold_split.json").read_text(encoding="utf-8"))
    payload["holdout"][0] = payload["calibration"][0]
    invalid = tmp_path / "duplicate-split.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exatamente|duplicados"):
        load_split(invalid, dataset)


def test_versioned_report_uses_production_embedding_outputs() -> None:
    report = json.loads((EVALS / "threshold_calibration_report.json").read_text(encoding="utf-8"))

    assert report["mode"] == "offline-production-embedding"
    assert report["embedding_execution"]["model"] == "intfloat/multilingual-e5-small"
    assert report["embedding_execution"]["dimensions"] == 384
    assert report["selection"]["selected_threshold"] == PREVIOUS_THRESHOLD
    assert len(report["generated_candidates"]) == 20
    assert all(
        isinstance(candidate["distance"], float)
        for case in report["generated_candidates"]
        for candidate in case["candidates"]
    )


def test_runtime_default_and_documented_configuration_are_consistent() -> None:
    backend_root = EVALS.parent
    repository_root = backend_root.parent

    assert "SIMILARITY_THRESHOLD=0.45" in (
        backend_root / ".env.example"
    ).read_text(encoding="utf-8")
    assert "SIMILARITY_THRESHOLD=0.45" in (
        repository_root / "README.md"
    ).read_text(encoding="utf-8")
