"""Contratos de schema, privacidade e resiliência dos logs da PR 30."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document


def _event_records(caplog) -> list[dict[str, object]]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "echomind.observability"
    ]


def test_event_schema_is_versioned_bounded_and_contains_coherent_metrics(caplog) -> None:
    from app.structured_logging import bind_log_context, emit_event

    with caplog.at_level(logging.INFO, logger="echomind.observability"):
        with bind_log_context("tenant-operacional") as context:
            payload = emit_event(
                event="rag.retrieval",
                status="success",
                stage="completed",
                context=context,
                duration_ms=12.34567,
                counts={"vector_candidates": 4, "returned_results": 2},
                source_types={"faq": 1, "document_chunk": 1},
            )

    assert payload == _event_records(caplog)[0]
    assert caplog.records[0].levelno == logging.INFO
    assert payload["schema_version"] == 1
    assert payload["event"] == "rag.retrieval"
    assert payload["status"] == "success"
    assert payload["stage"] == "completed"
    assert payload["duration_ms"] == 12.346
    assert payload["counts"] == {"vector_candidates": 4, "returned_results": 2}
    assert payload["source_types"] == {"faq": 1, "document_chunk": 1}
    assert len(str(payload["correlation_id"])) == 32
    assert len(str(payload["tenant_ref"])) == 16


def test_sensitive_values_and_unbounded_dimensions_never_reach_serialized_event(caplog) -> None:
    from app.structured_logging import emit_event

    tenant = "tenant-bruto-super-secreto"
    question = "pergunta completa que nao pode aparecer"
    authorization = "Bearer token-ultrassecreto"
    document = "conteudo integral do documento"

    with caplog.at_level(logging.ERROR, logger="echomind.observability"):
        emit_event(
            event="rag.chat",
            status="error",
            stage="generation",
            tenant_id=tenant,
            counts={question: 7},
            source_types={document: 3},
            error_code=type(RuntimeError(f"{authorization} {question}" )).__name__,
        )

    serialized = caplog.records[0].getMessage()
    for sensitive in (tenant, question, authorization, document, "token-ultrassecreto"):
        assert sensitive not in serialized
    payload = json.loads(serialized)
    assert caplog.records[0].levelno == logging.ERROR
    assert payload["counts"] == {"other": 7}
    assert payload["source_types"] == {"other": 3}
    assert payload["error_code"] == "runtimeerror"
    assert set(payload).isdisjoint(
        {"question", "answer", "content", "document", "authorization", "token", "secret"}
    )


def test_contexts_do_not_cross_operations_for_same_or_different_tenants() -> None:
    from app.structured_logging import bind_log_context

    with bind_log_context("tenant-a") as first:
        first_snapshot = first
    with bind_log_context("tenant-a") as second:
        second_snapshot = second
    with bind_log_context("tenant-b") as third:
        third_snapshot = third

    assert first_snapshot.correlation_id != second_snapshot.correlation_id
    assert first_snapshot.tenant_ref == second_snapshot.tenant_ref
    assert third_snapshot.correlation_id not in {
        first_snapshot.correlation_id,
        second_snapshot.correlation_id,
    }
    assert third_snapshot.tenant_ref != first_snapshot.tenant_ref


def test_logger_failure_is_swallowed_without_changing_primary_flow(monkeypatch) -> None:
    from app import structured_logging

    def broken_sink(*_args, **_kwargs):
        raise OSError("sink indisponivel")

    monkeypatch.setattr(structured_logging._logger, "log", broken_sink)
    payload = structured_logging.emit_event(
        event="rag.retrieval",
        status="success",
        stage="completed",
        tenant_id="tenant-a",
        counts={"returned_results": 1},
    )

    assert payload["status"] == "success"
    assert payload["counts"] == {"returned_results": 1}


@pytest.mark.asyncio
async def test_retrieval_success_logs_counts_sources_duration_and_no_query(
    monkeypatch,
    caplog,
    quick_test_context,
) -> None:
    from app import rag_engine

    query = "consulta confidencial codigo 991"
    vector_documents = [
        (
            Document(
                page_content="conteudo confidencial recuperado",
                metadata={"source_type": "faq", "source_id": "faq-secreta", "tenant_id": "tenant-a"},
            ),
            0.1,
        )
    ]

    class Store:
        def similarity_search_with_score(self, received_query: str, *, k: int):
            assert received_query == query
            assert k >= 1
            return vector_documents

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda _tenant_id: Store())
    monkeypatch.setattr(rag_engine, "_search_lexical_documents", lambda *_args, **_kwargs: [])

    with caplog.at_level(logging.INFO, logger="echomind.observability"):
        documents, distance = await rag_engine._retrieve_docs(query, "tenant-a")

    assert documents == [vector_documents[0][0]]
    assert distance == 0.1
    event = next(item for item in _event_records(caplog) if item["event"] == "rag.retrieval")
    assert event["status"] == "success"
    assert event["duration_ms"] >= 0
    assert event["counts"]["vector_candidates"] == 1
    assert event["counts"]["returned_results"] == 1
    assert event["source_types"] == {"faq": 1}
    serialized = json.dumps(event)
    assert query not in serialized
    assert "conteudo confidencial recuperado" not in serialized
    assert "faq-secreta" not in serialized
    assert "tenant-a" not in serialized


@pytest.mark.asyncio
async def test_retrieval_failure_logs_safe_technical_context_and_reraises(
    monkeypatch,
    caplog,
    quick_test_context,
) -> None:
    from app import rag_engine

    secret = "senha-do-banco-na-mensagem"

    class BrokenStore:
        def similarity_search_with_score(self, _query: str, *, k: int):
            raise RuntimeError(secret)

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda _tenant_id: BrokenStore())
    monkeypatch.setattr(rag_engine, "_search_lexical_documents", lambda *_args, **_kwargs: [])

    with caplog.at_level(logging.ERROR, logger="echomind.observability"):
        with pytest.raises(RuntimeError, match=secret):
            await rag_engine._retrieve_docs("pergunta privada", "tenant-a")

    event = next(item for item in _event_records(caplog) if item["event"] == "rag.retrieval")
    assert event["status"] == "error"
    assert event["stage"] == "candidate-retrieval"
    assert event["error_code"] == "runtimeerror"
    assert event["duration_ms"] >= 0
    assert secret not in json.dumps(event)
    assert "pergunta privada" not in json.dumps(event)


@pytest.mark.asyncio
async def test_chat_and_retrieval_share_correlation_without_logging_content(
    monkeypatch,
    caplog,
    quick_test_context,
) -> None:
    from app import rag_engine

    question = "pergunta completa e confidencial"
    answer = "resposta completa e confidencial"
    retrieved_content = "trecho integral e confidencial"

    class Store:
        def similarity_search_with_score(self, _query: str, *, k: int):
            return [
                (
                    Document(
                        page_content=retrieved_content,
                        metadata={
                            "source_type": "faq",
                            "source_id": "faq-privada",
                            "tenant_id": "tenant-a",
                        },
                    ),
                    0.1,
                )
            ]

    class LLM:
        async def astream(self, _messages):
            yield SimpleNamespace(content=answer)

    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda _tenant_id: Store())
    monkeypatch.setattr(rag_engine, "_search_lexical_documents", lambda *_args, **_kwargs: [])
    engine = object.__new__(rag_engine.RAGEngine)
    engine.tenant_id = "tenant-a"
    engine._llm = LLM()
    engine._config = {
        "company_name": "Instituicao",
        "website": "https://example.test",
        "tone": "cordial",
        "description": None,
        "phone": None,
        "address": None,
        "business_hours": None,
    }
    engine.last_had_docs = True

    with caplog.at_level(logging.INFO, logger="echomind.observability"):
        streamed = "".join([token async for token in engine.astream_chat(question)])

    assert streamed == answer
    events = _event_records(caplog)
    retrieval = next(item for item in events if item["event"] == "rag.retrieval")
    chat = next(item for item in events if item["event"] == "rag.chat")
    assert retrieval["correlation_id"] == chat["correlation_id"]
    assert retrieval["tenant_ref"] == chat["tenant_ref"]
    serialized = json.dumps(events)
    for sensitive in (question, answer, retrieved_content, "faq-privada", "tenant-a"):
        assert sensitive not in serialized
