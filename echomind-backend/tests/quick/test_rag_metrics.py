"""Agregacao, privacidade, retencao e API das metricas RAG da PR 31."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _record(db, tenant_id: str, metric_date: date, **payload) -> None:
    from app.rag_metrics import record_metric_event

    assert record_metric_event(
        db,
        tenant_id=tenant_id,
        metric_date=metric_date,
        payload=payload,
    )


def test_known_aggregations_by_period_status_latency_and_source(db) -> None:
    from app.rag_metrics import get_rag_metrics

    today = date(2026, 9, 7)
    day = today - timedelta(days=1)
    tenant = "tenant-a"
    _record(
        db,
        tenant,
        day,
        event="rag.chat",
        status="success",
        stage="generation",
        counts={"retrieved_results": 3},
    )
    _record(
        db,
        tenant,
        day,
        event="rag.chat",
        status="error",
        stage="generation",
        counts={"retrieved_results": 1},
    )
    _record(
        db,
        tenant,
        day,
        event="rag.retrieval",
        status="success",
        stage="completed",
        duration_ms=10.0,
        source_types={"faq": 1, "document_parent": 2},
    )
    _record(
        db,
        tenant,
        day,
        event="rag.retrieval",
        status="error",
        stage="candidate-retrieval",
        duration_ms=20.0,
    )
    _record(
        db,
        tenant,
        day,
        event="rag.ingestion",
        status="success",
        stage="completed",
        duration_ms=100.0,
    )
    _record(
        db,
        tenant,
        day,
        event="rag.ingestion",
        status="error",
        stage="indexing",
        duration_ms=300.0,
    )
    _record(
        db,
        tenant,
        day,
        event="rag.unanswered",
        status="success",
        stage="created",
    )
    db.commit()

    metrics = get_rag_metrics(db, tenant_id=tenant, days=7, today=today)

    assert metrics["has_data"] is True
    assert metrics["query_count"] == 2
    assert metrics["query_error_count"] == 1
    assert metrics["failure_count"] == 3
    assert metrics["average_retrieved_results"] == 2.0
    assert metrics["unanswered_rate"] == 50.0
    assert metrics["retrieval"] == {
        "total": 2,
        "success": 1,
        "error": 1,
        "average_latency_ms": 15.0,
    }
    assert metrics["ingestion"] == {
        "total": 2,
        "success": 1,
        "error": 1,
        "average_latency_ms": 200.0,
    }
    assert metrics["source_types"] == {
        "faq": 1,
        "event": 0,
        "document_chunk": 0,
        "document_parent": 2,
        "other": 0,
    }
    assert metrics["daily"] == [
        {"date": day, "queries": 2, "failures": 3, "unanswered": 1}
    ]


def test_aggregation_is_tenant_scoped_and_contains_no_free_text(db) -> None:
    from app.database import RagMetricDaily
    from app.rag_metrics import get_rag_metrics, record_metric_event

    today = date(2026, 9, 7)
    secret = "pergunta-documento-secreto"
    accepted = record_metric_event(
        db,
        tenant_id="tenant-a",
        metric_date=today,
        payload={
            "event": "rag.chat",
            "status": "success",
            "stage": "generation",
            "question": secret,
            "counts": {"retrieved_results": 1, secret: 999},
        },
    )
    _record(
        db,
        "tenant-b",
        today,
        event="rag.chat",
        status="success",
        stage="generation",
        counts={"retrieved_results": 50},
    )
    db.commit()

    assert accepted is True
    tenant_a = get_rag_metrics(db, tenant_id="tenant-a", days=1, today=today)
    tenant_b = get_rag_metrics(db, tenant_id="tenant-b", days=1, today=today)
    assert tenant_a["query_count"] == 1
    assert tenant_a["average_retrieved_results"] == 1.0
    assert tenant_b["average_retrieved_results"] == 50.0
    assert set(RagMetricDaily.__table__.columns.keys()).isdisjoint(
        {"question", "answer", "content", "document", "token", "secret"}
    )
    assert secret not in repr(tenant_a)


def test_retention_keeps_exactly_ninety_calendar_days(db) -> None:
    from app.database import RagMetricDaily
    from app.rag_metrics import purge_expired_metrics

    today = date(2026, 9, 7)
    for age in (0, 89, 90):
        _record(
            db,
            "tenant-retention",
            today - timedelta(days=age),
            event="rag.chat",
            status="success",
            stage="generation",
        )
    db.commit()

    _record(
        db,
        "tenant-preserved",
        today - timedelta(days=120),
        event="rag.chat",
        status="success",
        stage="generation",
    )
    db.commit()

    assert purge_expired_metrics(
        db,
        tenant_id="tenant-retention",
        today=today,
    ) == 1
    db.commit()
    retention_dates = {
        row.metric_date
        for row in db.query(RagMetricDaily).filter(
            RagMetricDaily.tenant_id == "tenant-retention"
        )
    }
    assert retention_dates == {today, today - timedelta(days=89)}
    assert db.get(
        RagMetricDaily,
        {
            "tenant_id": "tenant-preserved",
            "metric_date": today - timedelta(days=120),
        },
    ) is not None


def test_structured_event_forwards_private_tenant_only_to_metric_sink(monkeypatch) -> None:
    from app import structured_logging

    captured: list[tuple[str, object]] = []
    monkeypatch.setattr(
        structured_logging,
        "_metric_sink",
        lambda tenant_id, payload: captured.append((tenant_id, payload)),
    )

    payload = structured_logging.emit_event(
        event="rag.chat",
        status="success",
        stage="generation",
        tenant_id="tenant-raw-private",
        counts={"retrieved_results": 2},
    )

    assert captured == [("tenant-raw-private", payload)]
    assert "tenant-raw-private" not in repr(payload)
    assert "tenant_id" not in payload


def test_metric_sink_failure_never_changes_primary_event(monkeypatch) -> None:
    from app import structured_logging

    def broken_metric_sink(_tenant_id, _payload) -> None:
        raise RuntimeError("banco de metricas indisponivel")

    monkeypatch.setattr(structured_logging, "_metric_sink", broken_metric_sink)
    payload = structured_logging.emit_event(
        event="rag.chat",
        status="success",
        stage="generation",
        tenant_id="tenant-safe",
        counts={"retrieved_results": 2},
    )

    assert payload["status"] == "success"
    assert payload["counts"] == {"retrieved_results": 2}


def test_rag_metrics_endpoint_is_authenticated_and_tenant_scoped(
    client: TestClient,
    db,
    quick_test_context,
) -> None:
    today = date.today()
    _record(
        db,
        "test-admin",
        today,
        event="rag.chat",
        status="success",
        stage="generation",
        counts={"retrieved_results": 2},
    )
    _record(
        db,
        "foreign-tenant",
        today,
        event="rag.chat",
        status="success",
        stage="generation",
        counts={"retrieved_results": 99},
    )
    db.commit()

    response = client.get("/dashboard/rag-metrics?days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["query_count"] == 1
    assert body["average_retrieved_results"] == 2.0
    assert "tenant_id" not in body
    assert "foreign-tenant" not in response.text

    app = quick_test_context.app
    dependency = quick_test_context.get_current_user
    override = app.dependency_overrides.pop(dependency)
    try:
        unauthenticated = client.get("/dashboard/rag-metrics")
    finally:
        app.dependency_overrides[dependency] = override
    assert unauthenticated.status_code == 403


def test_rag_metrics_endpoint_limits_period(client: TestClient) -> None:
    assert client.get("/dashboard/rag-metrics?days=0").status_code == 422
    assert client.get("/dashboard/rag-metrics?days=91").status_code == 422
