"""Persistencia PostgreSQL real das agregacoes operacionais da PR 31."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session


pytestmark = pytest.mark.integration


def test_postgresql_upsert_and_query_remain_tenant_scoped(postgres_engine) -> None:
    from app.database import RagMetricDaily
    from app.rag_metrics import get_rag_metrics, record_metric_event

    today = date.today()
    tenant_a = "pr31-metrics-a"
    tenant_b = "pr31-metrics-b"

    with Session(postgres_engine) as db:
        db.execute(
            delete(RagMetricDaily).where(
                RagMetricDaily.tenant_id.in_([tenant_a, tenant_b])
            )
        )
        db.commit()
        try:
            for retrieved_results in (2, 4):
                assert record_metric_event(
                    db,
                    tenant_id=tenant_a,
                    metric_date=today,
                    payload={
                        "event": "rag.chat",
                        "status": "success",
                        "stage": "generation",
                        "counts": {"retrieved_results": retrieved_results},
                    },
                )
            assert record_metric_event(
                db,
                tenant_id=tenant_b,
                metric_date=today,
                payload={
                    "event": "rag.chat",
                    "status": "success",
                    "stage": "generation",
                    "counts": {"retrieved_results": 99},
                },
            )
            db.commit()

            metrics_a = get_rag_metrics(db, tenant_id=tenant_a, days=1, today=today)
            metrics_b = get_rag_metrics(db, tenant_id=tenant_b, days=1, today=today)
            assert metrics_a["query_count"] == 2
            assert metrics_a["average_retrieved_results"] == 3.0
            assert metrics_b["query_count"] == 1
            assert metrics_b["average_retrieved_results"] == 99.0
        finally:
            db.execute(
                delete(RagMetricDaily).where(
                    RagMetricDaily.tenant_id.in_([tenant_a, tenant_b])
                )
            )
            db.commit()
