"""Sweep determinístico da PR 23, sem PGVector, embeddings ou LLM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.calibrate_similarity_threshold import (
    THRESHOLDS,
    load_candidates,
    select_threshold,
    sweep,
)
from scripts.eval_rag import load_dataset


EVALS = Path(__file__).parents[2] / "evals"


def test_sweep_includes_declared_bounds_and_preserves_fixed_variables() -> None:
    dataset = load_dataset(EVALS / "rag_baseline_dataset.json")
    rows = sweep(dataset, load_candidates(EVALS / "similarity_threshold_candidates.json", dataset))

    assert [row["threshold"] for row in rows] == list(THRESHOLDS)
    assert rows[0] == {"threshold": 0.30, "source_recall": 0.615, "source_precision": 1.0, "false_positive_rate": 0.0, "correct_refusal": 1.0}
    assert rows[1] == {"threshold": 0.35, "source_recall": 1.0, "source_precision": 1.0, "false_positive_rate": 0.0, "correct_refusal": 1.0}
    assert rows[3] == {"threshold": 0.45, "source_recall": 1.0, "source_precision": 0.65, "false_positive_rate": 1.0, "correct_refusal": 0.0}


def test_selection_prefers_0_35_without_regressing_critical_cases() -> None:
    dataset = load_dataset(EVALS / "rag_baseline_dataset.json")
    rows = sweep(dataset, load_candidates(EVALS / "similarity_threshold_candidates.json", dataset))
    selected, rule = select_threshold(rows)

    assert selected == 0.35
    assert "recall" in rule
    selected_row = next(row for row in rows if row["threshold"] == selected)
    assert selected_row["source_recall"] >= 0.95
    assert selected_row["correct_refusal"] == 1.0


def test_candidate_fixture_rejects_cross_tenant_source(tmp_path: Path) -> None:
    dataset = load_dataset(EVALS / "rag_baseline_dataset.json")
    payload = json.loads((EVALS / "similarity_threshold_candidates.json").read_text(encoding="utf-8"))
    payload["cases"][0]["candidates"][0]["source_id"] = "beta-faq-atendimento"
    invalid = tmp_path / "cross-tenant.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="outro tenant"):
        load_candidates(invalid, dataset)
