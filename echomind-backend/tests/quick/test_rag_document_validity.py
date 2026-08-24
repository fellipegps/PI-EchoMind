"""Validade documental pos-retrieval com overfetch deterministico."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from langchain_core.documents import Document


@pytest.fixture()
def rag_engine_module(quick_test_context):
    from app import rag_engine

    return rag_engine


class _FakeVectorStore:
    def __init__(self, results):
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def similarity_search_with_score(self, question: str, *, k: int):
        self.calls.append((question, k))
        return self.results[:k]


def _retrieved(
    source_id: str,
    *,
    source_type: str = "document_chunk",
    tenant_id: str = "tenant-a",
    valid_until=None,
) -> Document:
    metadata = {
        "source_id": source_id,
        "source_type": source_type,
        "tenant_id": tenant_id,
        "filename": f"{source_id}.txt",
    }
    if valid_until is not None:
        metadata["valid_until"] = valid_until
    return Document(page_content=f"Conteudo de {source_id}.", metadata=metadata)


async def _retrieve(
    monkeypatch,
    rag_engine_module,
    results,
    *,
    tenant_id: str = "tenant-a",
    today: date = date(2026, 8, 24),
):
    store = _FakeVectorStore(results)
    requested_tenants: list[str] = []

    def get_store(requested_tenant: str):
        requested_tenants.append(requested_tenant)
        return store

    monkeypatch.setattr(rag_engine_module, "_get_vector_store", get_store)
    docs, nearest_distance = await rag_engine_module._retrieve_docs(
        "consulta de validade",
        tenant_id,
        today=today,
    )
    return docs, nearest_distance, store, requested_tenants


@pytest.mark.parametrize(("top_k", "candidate_k"), ((3, 10), (4, 12)))
def test_candidate_k_uses_controlled_overfetch(
    monkeypatch,
    rag_engine_module,
    top_k: int,
    candidate_k: int,
) -> None:
    monkeypatch.setattr(rag_engine_module, "TOP_K_DOCS", top_k)

    assert rag_engine_module._retrieval_candidate_k() == candidate_k


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("valid_until", "expected_ids"),
    (
        ("2026-08-23", []),
        ("2026-08-24", ["hoje"]),
        ("2026-08-25", ["futuro"]),
        (None, ["sem-validade"]),
        (date(2026, 8, 24), ["hoje"]),
        (datetime(2026, 8, 25, 23, 0, tzinfo=timezone.utc), ["futuro"]),
    ),
)
async def test_document_validity_uses_injected_local_calendar_date(
    monkeypatch,
    rag_engine_module,
    valid_until,
    expected_ids,
) -> None:
    source_id = expected_ids[0] if expected_ids else "ontem"
    docs, nearest_distance, _store, _tenants = await _retrieve(
        monkeypatch,
        rag_engine_module,
        [(_retrieved(source_id, valid_until=valid_until), 0.12)],
    )

    assert [doc.metadata["source_id"] for doc in docs] == expected_ids
    assert nearest_distance == (0.12 if expected_ids else None)


@pytest.mark.asyncio
async def test_overfetch_filters_expired_then_restores_ranking_and_top_k(
    monkeypatch,
    rag_engine_module,
) -> None:
    monkeypatch.setattr(rag_engine_module, "TOP_K_DOCS", 3)
    results = [
        (_retrieved("expirado-1", valid_until="2026-08-20"), 0.01),
        (_retrieved("expirado-2", valid_until="2026-08-21"), 0.02),
        (_retrieved("expirado-3", valid_until="2026-08-22"), 0.03),
        (_retrieved("terceiro", valid_until="2026-09-01"), 0.30),
        (_retrieved("primeiro"), 0.10),
        (_retrieved("quarto", valid_until="2027-01-01"), 0.40),
        (_retrieved("segundo", valid_until="2026-08-24"), 0.20),
        (_retrieved("fora-threshold"), 0.46),
    ]

    docs, nearest_distance, store, _tenants = await _retrieve(
        monkeypatch,
        rag_engine_module,
        results,
    )

    assert store.calls == [("consulta de validade", 10)]
    assert [doc.metadata["source_id"] for doc in docs] == [
        "primeiro",
        "segundo",
        "terceiro",
    ]
    assert nearest_distance == 0.10
    assert rag_engine_module.SIMILARITY_THRESHOLD == 0.45


@pytest.mark.asyncio
async def test_faq_and_event_ignore_document_validity_filter(
    monkeypatch,
    rag_engine_module,
) -> None:
    results = [
        (_retrieved("doc-expirado", valid_until="2020-01-01"), 0.05),
        (
            _retrieved(
                "faq-1",
                source_type="faq",
                valid_until="2020-01-01",
            ),
            0.10,
        ),
        (
            _retrieved(
                "evento-1",
                source_type="event",
                valid_until="data-corrompida",
            ),
            0.20,
        ),
    ]

    docs, nearest_distance, _store, _tenants = await _retrieve(
        monkeypatch,
        rag_engine_module,
        results,
    )

    assert [doc.metadata["source_type"] for doc in docs] == ["faq", "event"]
    assert [doc.metadata["source_id"] for doc in docs] == ["faq-1", "evento-1"]
    assert nearest_distance == 0.10


@pytest.mark.asyncio
async def test_invalid_nonempty_validity_is_logged_and_excluded(
    monkeypatch,
    rag_engine_module,
    caplog,
) -> None:
    results = [
        (_retrieved("corrompido", valid_until="31/12/2026"), 0.05),
        (_retrieved("vigente"), 0.10),
    ]

    with caplog.at_level("WARNING", logger="echomind.rag"):
        docs, nearest_distance, _store, _tenants = await _retrieve(
            monkeypatch,
            rag_engine_module,
            results,
        )

    assert [doc.metadata["source_id"] for doc in docs] == ["vigente"]
    assert nearest_distance == 0.10
    assert "valid_until invalido" in caplog.text
    assert "source_id=corrompido" in caplog.text


@pytest.mark.asyncio
async def test_retrieval_keeps_tenant_collection_and_source_metadata(
    monkeypatch,
    rag_engine_module,
) -> None:
    stores = {
        tenant_id: _FakeVectorStore(
            [(_retrieved(f"fonte-{tenant_id}", tenant_id=tenant_id), distance)]
        )
        for tenant_id, distance in (("tenant-a", 0.11), ("tenant-b", 0.22))
    }
    requested_tenants: list[str] = []

    def get_store(tenant_id: str):
        requested_tenants.append(tenant_id)
        return stores[tenant_id]

    monkeypatch.setattr(rag_engine_module, "_get_vector_store", get_store)

    docs_a, distance_a = await rag_engine_module._retrieve_docs(
        "consulta",
        "tenant-a",
        today=date(2026, 8, 24),
    )
    docs_b, distance_b = await rag_engine_module._retrieve_docs(
        "consulta",
        "tenant-b",
        today=date(2026, 8, 24),
    )

    assert requested_tenants == ["tenant-a", "tenant-b"]
    assert [doc.metadata["tenant_id"] for doc in docs_a] == ["tenant-a"]
    assert [doc.metadata["tenant_id"] for doc in docs_b] == ["tenant-b"]
    assert [doc.metadata["source_id"] for doc in docs_a] == ["fonte-tenant-a"]
    assert [doc.metadata["source_id"] for doc in docs_b] == ["fonte-tenant-b"]
    assert (distance_a, distance_b) == (0.11, 0.22)
