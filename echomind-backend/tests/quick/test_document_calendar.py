"""Calendário documental institucional, independente do fuso do servidor."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document


@pytest.fixture()
def frozen_clock(quick_test_context, monkeypatch):
    from app import rag_engine, schemas

    clock = SimpleNamespace(instant=None, reads=0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            clock.reads += 1
            return clock.instant.astimezone(tz)

    class UtcServerDate(date):
        @classmethod
        def today(cls):
            return clock.instant.date()

    monkeypatch.setattr(schemas, "datetime", FrozenDatetime)
    # Reproduz um host em UTC mesmo quando os testes rodam em São Paulo.
    monkeypatch.setattr(rag_engine, "date", UtcServerDate)
    return clock


@pytest.mark.parametrize("utc_hour,utc_minute,utc_second", [(0, 0, 0), (2, 59, 59), (3, 0, 0)])
@pytest.mark.parametrize("fallback", [None, "lexical", "parent"])
async def test_same_local_day_for_vector_lexical_and_parent_fallbacks(
    db, persist_retrieval_sources, monkeypatch, frozen_clock,
    utc_hour, utc_minute, utc_second, fallback,
):
    from app import rag_engine, schemas
    from app.database import DocumentChunk, DocumentChunkParent, Document as StoredDocument

    frozen_clock.instant = datetime(2026, 9, 2, utc_hour, utc_minute, utc_second, tzinfo=timezone.utc)
    local_day = date(2026, 9, 1 if utc_hour < 3 else 2)
    assert schemas.sao_paulo_today() == local_day
    frozen_clock.reads = 0
    sources = [
        Document(page_content=f"Regra {key}.", metadata={
            "source_id": key, "source_type": "document_chunk", "tenant_id": "calendar-a",
            "valid_until": validity.isoformat() if validity else None,
        })
        for key, validity in (
            ("yesterday", local_day - timedelta(days=1)),
            ("today", local_day), ("future", local_day + timedelta(days=1)), ("unlimited", None),
        )
    ]
    persist_retrieval_sources(sources)
    for source in sources:
        document_id = source.metadata["document_id"]
        parent_id = f"parent-{source.metadata['source_id']}"
        db.add(DocumentChunkParent(
            id=parent_id, document_id=document_id, tenant_id="calendar-a", parent_index=0,
            content=f"Contexto completo {source.metadata['source_id']}.",
        ))
        db.flush()
        db.get(DocumentChunk, source.metadata["source_id"]).parent_id = parent_id
        db.get(StoredDocument, document_id).published_at = date(2026, 1, 1)
        source.metadata["parent_id"] = parent_id
    db.flush()

    class Session:
        def query(self, *entities):
            if fallback == "parent" and entities[0] is StoredDocument:
                raise RuntimeError("parent lookup indisponível")
            return db.query(*entities)

        def close(self):
            pass

    class VectorStore:
        def similarity_search_with_score(self, _question, *, k):
            return [(source, 0.1) for source in sources][:k]

    observed_dates = []

    def lexical(_question, tenant_id, *, today, limit):
        assert tenant_id == "calendar-a"
        observed_dates.append(today)
        # A consulta termina depois da meia-noite: não deve reler o relógio.
        frozen_clock.instant += timedelta(days=1)
        if fallback == "lexical":
            raise RuntimeError("lexical indisponível")
        return sources[:limit]

    monkeypatch.setattr(rag_engine, "SessionLocal", Session)
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda _tenant: VectorStore())
    monkeypatch.setattr(rag_engine, "_search_lexical_documents", lexical)
    monkeypatch.setattr(rag_engine, "TOP_K_DOCS", 4)
    monkeypatch.setattr(rag_engine, "RERANKER_ENABLED", False)
    documents, _distance = await rag_engine._retrieve_docs("regra", "calendar-a")

    assert observed_dates == [local_day]
    assert frozen_clock.reads == 1
    expected = {"today", "future", "unlimited"}
    if fallback == "parent":
        assert {doc.metadata["source_id"] for doc in documents} == expected
    else:
        assert {doc.metadata["matched_child_id"] for doc in documents} == expected
        assert all(doc.metadata["source_type"] == "document_parent" for doc in documents)
        assert all(doc.metadata["published_at"] == "2026-01-01" for doc in documents)


async def test_explicit_date_overrides_clock(persist_retrieval_sources, monkeypatch, frozen_clock):
    from app import rag_engine

    frozen_clock.instant = datetime(2026, 9, 2, 1, tzinfo=timezone.utc)
    source = Document(page_content="Regra histórica.", metadata={
        "source_id": "historic", "source_type": "document_chunk", "tenant_id": "calendar-a",
        "valid_until": "2020-01-01",
    })
    persist_retrieval_sources([source])
    store = SimpleNamespace(similarity_search_with_score=lambda *args, **kwargs: [(source, 0.1)])
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda _tenant: store)
    documents, _distance = await rag_engine._retrieve_docs("regra", "calendar-a", today=date(2020, 1, 1))
    assert documents == [source]
    assert frozen_clock.reads == 0


@pytest.mark.parametrize("utc_hour", [0, 2, 3])
async def test_prompt_and_retrieval_share_day_even_across_midnight(monkeypatch, frozen_clock, utc_hour):
    from app import rag_engine

    frozen_clock.instant = datetime(2026, 9, 2, utc_hour, tzinfo=timezone.utc)
    local_day = date(2026, 9, 1 if utc_hour < 3 else 2)
    captured = {}

    async def retrieve(_question, _tenant, **kwargs):
        captured["date"] = kwargs.get("today")
        frozen_clock.instant += timedelta(days=1)
        return [], None

    class LLM:
        async def astream(self, messages):
            captured["prompt"] = messages[0].content
            yield SimpleNamespace(content="Resposta institucional.")

    engine = object.__new__(rag_engine.RAGEngine)
    engine.tenant_id = "calendar-a"
    engine._llm = LLM()
    engine._config = {"company_name": "Teste", "website": "https://teste.local", "tone": "cordial"}
    monkeypatch.setattr(rag_engine, "_retrieve_docs", retrieve)
    assert "".join([token async for token in engine.astream_chat("regra")]) == "Resposta institucional."
    assert captured["date"] == local_day
    assert f"Data de hoje: {local_day.day} de setembro de 2026" in captured["prompt"]
    assert frozen_clock.reads == 1
