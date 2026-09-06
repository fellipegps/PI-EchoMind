from __future__ import annotations

import json
import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


def _event_records(caplog) -> list[dict[str, object]]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "echomind.observability"
    ]


def test_structured_event_has_stable_schema_safe_counts_and_level(caplog):
    from app.observability import emit_observability_event, new_correlation_id

    correlation_id = new_correlation_id()
    with caplog.at_level(logging.INFO, logger="echomind.observability"):
        payload = emit_observability_event(
            "rag.retrieval.completed",
            status="success",
            stage="retrieval",
            tenant_id="tenant-operacional",
            correlation_id=correlation_id,
            duration_ms=12.34567,
            counts={
                "vector_candidates": 4,
                "lexical_candidates": 2,
                "retrieved_documents": 3,
                "campo_livre": 999,
            },
            source_types=["faq", "document_chunk", "faq", "desconhecido"],
        )

    assert payload is not None
    assert payload == _event_records(caplog)[-1]
    assert payload["schema_version"] == 1
    assert payload["event"] == "rag.retrieval.completed"
    assert payload["level"] == "info"
    assert payload["status"] == "success"
    assert payload["stage"] == "retrieval"
    assert payload["correlation_id"] == correlation_id
    assert payload["tenant_ref"] != "tenant-operacional"
    assert payload["duration_ms"] == 12.346
    assert payload["counts"] == {
        "lexical_candidates": 2,
        "retrieved_documents": 3,
        "vector_candidates": 4,
    }
    assert payload["source_types"] == ["document_chunk", "faq"]


def test_error_event_redacts_exception_message_tenant_and_unapproved_fields(caplog):
    from app.observability import emit_observability_event

    secret = "Bearer token-secreto password=senha-super-secreta"
    question = "Qual e o conteudo confidencial completo?"
    with caplog.at_level(logging.ERROR, logger="echomind.observability"):
        payload = emit_observability_event(
            "ingestion.failed",
            status="error",
            stage="extraction",
            tenant_id="tenant-secreto",
            duration_ms=-10,
            counts={
                "chunks": -3,
                f"Authorization {secret}": 1,
            },
            source_types=[question],
            error=RuntimeError(f"{secret}; documento={question}"),
            level="error",
        )

    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload is not None
    assert payload["duration_ms"] == 0.0
    assert payload["counts"] == {"chunks": 0}
    assert payload["source_types"] == []
    assert payload["error_type"] == "RuntimeError"
    assert "tenant-secreto" not in serialized
    assert secret not in serialized
    assert question not in serialized
    assert "Authorization" not in serialized


def test_logger_failure_does_not_change_chat_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app import observability

    def fail_logger(*args, **kwargs):
        raise RuntimeError("logger indisponivel")

    monkeypatch.setattr(observability.logger, "log", fail_logger)
    response = client.post(
        "/chat",
        json={"message": "Pergunta segura de teste", "tenant_id": "test-admin"},
    )

    assert response.status_code == 200
    assert response.text == "Resposta simulada para: Pergunta segura de teste "


def test_each_request_has_an_isolated_internal_correlation_id(client: TestClient):
    first = client.get("/health")
    second = client.get("/health")

    first_id = first.headers["X-Correlation-ID"]
    second_id = second.headers["X-Correlation-ID"]
    assert UUID(first_id)
    assert UUID(second_id)
    assert first_id != second_id


def test_chat_event_uses_response_correlation_without_logging_question(
    client: TestClient,
    caplog,
):
    question = "Pergunta completa privada para correlacao"
    with caplog.at_level(logging.INFO, logger="echomind.observability"):
        response = client.post(
            "/chat",
            json={"message": question, "tenant_id": "test-admin"},
        )

    completed = next(
        event
        for event in _event_records(caplog)
        if event["event"] == "chat.completed"
    )
    assert response.status_code == 200
    assert completed["correlation_id"] == response.headers["X-Correlation-ID"]
    assert completed["counts"] == {"answered": 1, "cache_hits": 0}
    assert question not in caplog.text
    assert "test-admin" not in caplog.text


@pytest.mark.asyncio
async def test_retrieval_success_logs_counts_without_question_content(
    quick_test_context,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
):
    from langchain_core.documents import Document
    from app import rag_engine
    from app.observability import bind_correlation_id

    sensitive_question = "Pergunta completa que nao pode aparecer no log"
    document = Document(
        page_content="Documento completo que nao pode aparecer no log",
        metadata={
            "source_id": "faq-1",
            "source_type": "faq",
            "tenant_id": "tenant-a",
        },
    )

    class VectorStore:
        def similarity_search_with_score(self, question, k):
            return [(document, 0.1)]

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: VectorStore())
    monkeypatch.setattr(
        rag_engine,
        "_search_lexical_documents",
        lambda *args, **kwargs: [],
    )

    with (
        bind_correlation_id() as correlation_id,
        caplog.at_level(logging.INFO, logger="echomind.observability"),
    ):
        documents, distance = await rag_engine._retrieve_docs(
            sensitive_question,
            "tenant-a",
        )

    event = _event_records(caplog)[-1]
    assert documents == [document]
    assert distance == 0.1
    assert event["event"] == "rag.retrieval.completed"
    assert event["correlation_id"] == correlation_id
    assert event["counts"] == {
        "lexical_candidates": 0,
        "retrieved_documents": 1,
        "vector_candidates": 1,
    }
    assert event["source_types"] == ["faq"]
    assert sensitive_question not in caplog.text
    assert document.page_content not in caplog.text


@pytest.mark.asyncio
async def test_retrieval_failure_logs_only_safe_error_type(
    quick_test_context,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
):
    from app import rag_engine

    secret = "password=nao-registrar"

    class FailingVectorStore:
        def similarity_search_with_score(self, question, k):
            raise RuntimeError(secret)

    monkeypatch.setattr(
        rag_engine,
        "_get_vector_store",
        lambda tenant_id: FailingVectorStore(),
    )
    monkeypatch.setattr(
        rag_engine,
        "_search_lexical_documents",
        lambda *args, **kwargs: [],
    )

    with (
        caplog.at_level(logging.ERROR, logger="echomind.observability"),
        pytest.raises(RuntimeError, match="nao-registrar"),
    ):
        await rag_engine._retrieve_docs("pergunta sigilosa", "tenant-a")

    event = _event_records(caplog)[-1]
    assert event["event"] == "rag.retrieval.failed"
    assert event["status"] == "error"
    assert event["error_type"] == "RuntimeError"
    assert secret not in caplog.text
    assert "pergunta sigilosa" not in caplog.text
