#!/usr/bin/env python3
"""Benchmark offline executavel da expansao Parent-Child."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable, Sequence

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langchain_core.documents import Document as RetrievedDocument
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import rag_engine
from app.database import Base, Document, DocumentChunk, DocumentChunkParent
from app.document_ingestion import ChunkedTextBlock, group_document_children
from app.document_repository import DocumentChunkData, DocumentParentData, replace_document_chunks


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


def _pr25_latency(pr25_report: dict[str, Any]) -> float:
    latency = pr25_report.get("latency_ms", {})
    for key in ("retrieval_plus_reranker_mean", "controlled_reranked_mean"):
        if key in latency:
            return float(latency[key])
    raise ValueError("Relatorio da PR 25 nao contem latencia executada compativel.")


def _create_eval_session_factory():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(
        engine,
        tables=[
            Document.__table__,
            DocumentChunkParent.__table__,
            DocumentChunk.__table__,
        ],
    )
    return engine, sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )


def _case_date(dataset: dict[str, Any]) -> date:
    raw_value = dataset.get("evaluation_date")
    if not isinstance(raw_value, str):
        raise ValueError("Eval Parent-Child exige evaluation_date em ISO-8601.")
    return date.fromisoformat(raw_value)


def evaluate_parent_child(
    dataset: dict[str, Any],
    pr25_report: dict[str, Any],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Eval Parent-Child exige uma lista nao vazia de casos.")

    evaluation_date = _case_date(dataset)
    children_per_parent = int(dataset.get("children_per_parent", 3))
    if children_per_parent <= 0:
        raise ValueError("children_per_parent deve ser positivo.")

    engine, session_factory = _create_eval_session_factory()
    session = session_factory()
    persisted_cases: list[tuple[dict[str, Any], list[DocumentChunk]]] = []
    try:
        for case in cases:
            raw_children = case.get("children")
            if not isinstance(raw_children, list) or not raw_children:
                raise ValueError(f"Caso {case.get('id')!r} nao contem children.")
            flat_children = tuple(
                ChunkedTextBlock(
                    chunk_index=index,
                    content=str(child["content"]),
                    page_start=child.get("page_start"),
                    page_end=child.get("page_end"),
                    section_title=child.get("section_title"),
                )
                for index, child in enumerate(raw_children)
            )
            grouped = group_document_children(
                flat_children,
                chunk_overlap=0,
                children_per_parent=children_per_parent,
            )
            document = Document(
                id=str(case["document_id"]),
                tenant_id=str(case["tenant_id"]),
                filename=str(case.get("filename", f"{case['id']}.txt")),
                mime_type="text/plain",
                size_bytes=sum(len(child.content.encode("utf-8")) for child in flat_children),
                sha256=hashlib.sha256(str(case["id"]).encode("utf-8")).hexdigest(),
                status="ready",
                valid_until=date.fromisoformat(case["valid_until"])
                if case.get("valid_until")
                else None,
            )
            session.add(document)
            session.flush()
            persisted = replace_document_chunks(
                session,
                tenant_id=document.tenant_id,
                document_id=document.id,
                chunks=(
                    DocumentChunkData(
                        content=child.content,
                        page_start=child.page_start,
                        page_end=child.page_end,
                        section_title=child.section_title,
                        parent_index=child.parent_index,
                    )
                    for child in grouped.children
                ),
                parents=(
                    DocumentParentData(
                        content=parent.content,
                        page_start=parent.page_start,
                        page_end=parent.page_end,
                        section_title=parent.section_title,
                    )
                    for parent in grouped.parents
                ),
            )
            persisted_cases.append((case, persisted))
        session.commit()
    finally:
        session.close()

    child_complete: list[float] = []
    parent_complete: list[float] = []
    lookup_latencies: list[float] = []
    context_growth: list[float] = []
    details: list[dict[str, Any]] = []

    for case, persisted_children in persisted_cases:
        matched_indexes = case.get("matched_child_indexes")
        if not isinstance(matched_indexes, list) or not matched_indexes:
            raise ValueError(f"Caso {case.get('id')!r} nao define matched_child_indexes.")
        try:
            matched_children = [persisted_children[int(index)] for index in matched_indexes]
        except (IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"Caso {case.get('id')!r} referencia child inexistente.") from exc
        retrieved = [
            RetrievedDocument(
                page_content=child.content,
                metadata={
                    "source_id": child.id,
                    "source_type": "document_chunk",
                    "tenant_id": child.tenant_id,
                    "document_id": child.document_id,
                    "parent_id": child.parent_id,
                    "valid_until": case.get("valid_until"),
                },
            )
            for child in matched_children
        ]
        started = clock()
        expanded = rag_engine._expand_document_parents(
            retrieved,
            tenant_id=str(case["tenant_id"]),
            today=evaluation_date,
            session_factory=session_factory,
        )
        lookup_latency = max(0.0, (clock() - started) * 1000)
        required_terms = case["required_terms"]
        child_context = "\n\n".join(item.page_content for item in retrieved)
        parent_context = "\n\n".join(item.page_content for item in expanded)
        child_score = _complete(child_context, required_terms)
        parent_score = _complete(parent_context, required_terms)

        child_complete.append(child_score)
        parent_complete.append(parent_score)
        lookup_latencies.append(lookup_latency)
        context_growth.append(len(parent_context) / max(1, len(child_context)))
        details.append(
            {
                "id": case["id"],
                "pr25_context_complete": bool(child_score),
                "parent_context_complete": bool(parent_score),
                "context_growth_ratio": round(context_growth[-1], 3),
                "child_candidates": len(retrieved),
                "expanded_results": len(expanded),
                "parent_ids": [item.metadata.get("parent_id") for item in expanded],
                "tenant_isolated": all(
                    item.metadata.get("tenant_id") == case["tenant_id"] for item in expanded
                ),
                "lookup_latency_ms": round(lookup_latency, 3),
            }
        )

    engine.dispose()
    baseline_latency = _pr25_latency(pr25_report)
    mean_lookup = _mean(lookup_latencies)
    mean_context_growth = _mean(context_growth)
    tenant_isolated = all(detail["tenant_isolated"] for detail in details)
    deduplicated = all(
        len(detail["parent_ids"]) == len(set(detail["parent_ids"])) for detail in details
    )

    return {
        "report_version": 2,
        "dataset_version": dataset.get("dataset_version", dataset.get("version")),
        "mode": "offline-executed-parent-expansion-benchmark",
        "execution": {
            "database": "sqlite-memory",
            "parent_grouping": "production-group_document_children",
            "parent_lookup": "production-_expand_document_parents",
            "external_calls": False,
            "children_per_parent": children_per_parent,
        },
        "pr25_reference": {
            "reranked_hit_rate_at_k": pr25_report["ranking"]["reranked_hit_rate_at_k"],
            "reranked_mrr_at_k": pr25_report["ranking"]["reranked_mrr_at_k"],
            "retrieval_plus_reranker_mean_ms": baseline_latency,
        },
        "quality": {
            "pr25_context_complete_rate": _mean(child_complete),
            "parent_context_complete_rate": _mean(parent_complete),
            "context_complete_gain": round(_mean(parent_complete) - _mean(child_complete), 3),
        },
        "latency_ms": {
            "pr25_retrieval_plus_reranker_mean": round(baseline_latency, 3),
            "parent_lookup_mean": mean_lookup,
            "parent_lookup_p95": _p95(lookup_latencies),
            "retrieval_reranker_parent_mean": round(baseline_latency + mean_lookup, 3),
        },
        "context": {
            "mean_growth_ratio": mean_context_growth,
            "max_mean_growth_ratio": float(
                dataset.get("max_mean_context_growth_ratio", 2.5)
            ),
        },
        "safety": {
            "tenant_isolated": tenant_isolated,
            "parents_deduplicated": deduplicated,
        },
        "activation_assessment": {
            "evidence_supports_parent_child": (
                _mean(parent_complete) > _mean(child_complete)
                and tenant_isolated
                and deduplicated
                and mean_lookup <= float(dataset.get("max_parent_lookup_mean_ms", 50.0))
                and mean_context_growth
                <= float(dataset.get("max_mean_context_growth_ratio", 2.5))
            ),
            "max_parent_lookup_mean_ms": float(
                dataset.get("max_parent_lookup_mean_ms", 50.0)
            ),
        },
        "cases": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Executa persistencia e expansao Parent-Child localmente, sem rede."
    )
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
