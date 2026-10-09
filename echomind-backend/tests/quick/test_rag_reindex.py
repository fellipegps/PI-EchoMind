"""Testes unitarios do embedding 384d e da reindexacao por tenant."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from fastembed import TextEmbedding


@pytest.fixture()
def rag_modules(quick_test_context):
    """Importa app/script somente depois que a suite rapida configurou SQLite."""
    from app import rag_engine
    from app.database import CompanyEvent, Config, Document, DocumentChunk, Faq
    from scripts import reindex_all

    return SimpleNamespace(
        rag_engine=rag_engine,
        reindex_all=reindex_all,
        CompanyEvent=CompanyEvent,
        Config=Config,
        Document=Document,
        DocumentChunk=DocumentChunk,
        Faq=Faq,
    )


def test_default_embedding_model_and_dimension(monkeypatch, rag_modules) -> None:
    rag_engine = rag_modules.rag_engine
    assert rag_engine.DEFAULT_EMBED_MODEL == "intfloat/multilingual-e5-small"
    assert rag_engine.DEFAULT_EMBEDDING_DIM == 384
    assert rag_engine.EMBEDDING_DIM == 384
    assert rag_engine.SIMILARITY_THRESHOLD == 0.45

    monkeypatch.setattr(rag_engine, "EMBED_MODEL", rag_engine.DEFAULT_EMBED_MODEL)
    rag_engine._register_default_embedding_model()
    registered = next(
        model
        for model in TextEmbedding.list_supported_models()
        if model["model"] == rag_engine.DEFAULT_EMBED_MODEL
    )
    assert registered["dim"] == 384


def test_embedding_loader_uses_multilingual_default_without_network(
    monkeypatch,
    rag_modules,
) -> None:
    rag_engine = rag_modules.rag_engine
    registration = MagicMock()
    fake_embeddings = MagicMock(return_value="embeddings")
    monkeypatch.setattr(rag_engine, "EMBED_MODEL", rag_engine.DEFAULT_EMBED_MODEL)
    monkeypatch.setattr(rag_engine, "_register_default_embedding_model", registration)
    monkeypatch.setattr(rag_engine, "FastEmbedEmbeddings", fake_embeddings)
    rag_engine._get_embeddings.cache_clear()

    try:
        assert rag_engine._get_embeddings() == "embeddings"
    finally:
        rag_engine._get_embeddings.cache_clear()

    registration.assert_called_once_with()
    fake_embeddings.assert_called_once_with(
        model_name="intfloat/multilingual-e5-small",
        cache_dir=rag_engine._MODEL_CACHE,
    )


def test_list_tenant_ids_includes_only_indexable_sources(db, rag_modules) -> None:
    CompanyEvent = rag_modules.CompanyEvent
    Config = rag_modules.Config
    Faq = rag_modules.Faq
    Document = rag_modules.Document
    reindex_all = rag_modules.reindex_all
    db.add_all(
        [
            Faq(tenant_id="tenant-b", question="Pergunta B?", answer="Resposta B."),
            Faq(tenant_id="tenant-a", question="Pergunta A?", answer="Resposta A."),
            CompanyEvent(
                tenant_id="tenant-only-event",
                title="Evento fora do RAG",
                event_date="2099-09-01",
                event_end_date="2099-09-01",
                event_type="palestra",
            ),
            Config(
                tenant_id="tenant-sem-conteudo",
                public_slug="sem-conteudo-0f5fb54ff884a3ab",
                company_name="Sem conteudo",
            ),
            Document(
                id="doc-ready",
                tenant_id="tenant-c",
                filename="ready.txt",
                mime_type="text/plain",
                size_bytes=10,
                sha256="a" * 64,
                status="ready",
            ),
            Document(
                id="doc-pending",
                tenant_id="tenant-so-pending",
                filename="pending.txt",
                mime_type="text/plain",
                size_bytes=10,
                sha256="b" * 64,
                status="pending",
            ),
        ]
    )
    db.flush()

    assert reindex_all.list_tenant_ids(db) == ["tenant-a", "tenant-b", "tenant-c"]


def test_clear_collection_is_restricted_to_selected_tenant(monkeypatch, rag_modules) -> None:
    rag_engine = rag_modules.rag_engine
    stores = {"tenant-a": MagicMock(), "tenant-b": MagicMock()}
    monkeypatch.setattr(
        rag_engine,
        "_get_vector_store",
        lambda tenant_id: stores[tenant_id],
    )

    rag_engine.clear_tenant_collection("tenant-b")

    stores["tenant-b"].delete_collection.assert_called_once_with()
    stores["tenant-b"].create_collection.assert_called_once_with()
    stores["tenant-a"].delete_collection.assert_not_called()
    stores["tenant-a"].create_collection.assert_not_called()


def test_reindex_tenant_indexes_only_ready_documents_and_persisted_chunks(
    db,
    monkeypatch,
    rag_modules,
) -> None:
    CompanyEvent = rag_modules.CompanyEvent
    Faq = rag_modules.Faq
    Document = rag_modules.Document
    DocumentChunk = rag_modules.DocumentChunk
    reindex_all = rag_modules.reindex_all
    faq_a = Faq(tenant_id="tenant-a", question="Pergunta A?", answer="Resposta A.")
    faq_b = Faq(tenant_id="tenant-b", question="Pergunta B?", answer="Resposta B.")
    event_a = CompanyEvent(
        tenant_id="tenant-a",
        title="Evento fora do RAG",
        event_date="2099-09-02",
        event_end_date="2099-09-02",
        event_type="workshop",
    )
    ready_a = Document(
        id="doc-ready-a",
        tenant_id="tenant-a",
        filename="ready-a.txt",
        mime_type="text/plain",
        size_bytes=20,
        sha256="c" * 64,
        status="ready",
        chunk_count=2,
    )
    ignored_documents = [
        Document(
            id=f"doc-{status}-a",
            tenant_id="tenant-a",
            filename=f"{status}.txt",
            mime_type="text/plain",
            size_bytes=20,
            sha256=character * 64,
            status=status,
            chunk_count=1,
        )
        for status, character in (
            ("pending", "d"),
            ("processing", "e"),
            ("error", "f"),
        )
    ]
    ready_b = Document(
        id="doc-ready-b",
        tenant_id="tenant-b",
        filename="ready-b.txt",
        mime_type="text/plain",
        size_bytes=20,
        sha256="1" * 64,
        status="ready",
        chunk_count=1,
    )
    ready_chunks = [
        DocumentChunk(
            id="chunk-ready-a-2",
            tenant_id="tenant-a",
            document_id=ready_a.id,
            chunk_index=1,
            content="Segundo chunk pronto.",
        ),
        DocumentChunk(
            id="chunk-ready-a-1",
            tenant_id="tenant-a",
            document_id=ready_a.id,
            chunk_index=0,
            content="Primeiro chunk pronto.",
        ),
    ]
    ignored_chunks = [
        DocumentChunk(
            id=f"chunk-{document.status}-a",
            tenant_id="tenant-a",
            document_id=document.id,
            chunk_index=0,
            content=f"Chunk {document.status} ignorado.",
        )
        for document in ignored_documents
    ]
    chunk_b = DocumentChunk(
        id="chunk-ready-b",
        tenant_id="tenant-b",
        document_id=ready_b.id,
        chunk_index=0,
        content="Chunk de outro tenant.",
    )
    db.add_all(
        [
            faq_a,
            faq_b,
            event_a,
            ready_a,
            *ignored_documents,
            ready_b,
            *ready_chunks,
            *ignored_chunks,
            chunk_b,
        ]
    )
    db.flush()

    fake_rag = MagicMock()
    cleared_tenants: list[str] = []
    monkeypatch.setattr(reindex_all, "get_rag_indexer", lambda db, tenant_id: fake_rag)
    monkeypatch.setattr(reindex_all, "clear_tenant_collection", cleared_tenants.append)

    result = reindex_all.reindex_tenant(db, "tenant-a")

    assert result == reindex_all.ReindexResult(
        "tenant-a",
        faq_count=1,
        document_count=1,
        document_chunk_count=2,
    )
    assert cleared_tenants == ["tenant-a"]
    fake_rag.index_faq.assert_called_once_with(faq_a)
    fake_rag.index_event.assert_not_called()
    assert fake_rag.index_document_chunk.call_args_list == [
        call(ready_a, ready_chunks[1]),
        call(ready_a, ready_chunks[0]),
    ]


def test_reindex_tenant_validates_chunk_count_before_clearing(
    db,
    monkeypatch,
    rag_modules,
) -> None:
    reindex_all = rag_modules.reindex_all
    document = rag_modules.Document(
        id="doc-inconsistente",
        tenant_id="tenant-a",
        filename="inconsistente.txt",
        mime_type="text/plain",
        size_bytes=20,
        sha256="2" * 64,
        status="ready",
        chunk_count=2,
    )
    chunk = rag_modules.DocumentChunk(
        id="chunk-unico",
        tenant_id="tenant-a",
        document_id=document.id,
        chunk_index=0,
        content="Apenas um chunk persistido.",
    )
    db.add_all([document, chunk])
    db.flush()

    clear_collection = MagicMock()
    get_indexer = MagicMock()
    monkeypatch.setattr(reindex_all, "clear_tenant_collection", clear_collection)
    monkeypatch.setattr(reindex_all, "get_rag_indexer", get_indexer)

    with pytest.raises(RuntimeError, match="Contagem de chunks inconsistente"):
        reindex_all.reindex_tenant(db, "tenant-a")

    clear_collection.assert_not_called()
    get_indexer.assert_not_called()


def test_reindex_tenant_second_execution_produces_same_deterministic_set(
    db,
    monkeypatch,
    rag_modules,
) -> None:
    rag_engine = rag_modules.rag_engine
    reindex_all = rag_modules.reindex_all
    faq = rag_modules.Faq(
        id="faq-idempotente",
        tenant_id="tenant-a",
        question="Pergunta idempotente?",
        answer="Resposta idempotente.",
    )
    document = rag_modules.Document(
        id="doc-idempotente",
        tenant_id="tenant-a",
        filename="idempotente.txt",
        mime_type="text/plain",
        size_bytes=20,
        sha256="3" * 64,
        status="ready",
        chunk_count=1,
    )
    chunk = rag_modules.DocumentChunk(
        id="chunk-idempotente",
        tenant_id="tenant-a",
        document_id=document.id,
        chunk_index=0,
        content="Chunk idempotente.",
    )
    db.add_all([faq, document, chunk])
    db.flush()

    collections = {
        "tenant-a": set(),
        "tenant-b": {"vetor-b-preservado"},
    }

    class FakeRag:
        tenant_id = "tenant-a"

        def index_faq(self, source):
            collections[self.tenant_id].add(
                rag_engine._make_vector_id(source.id, "faq", self.tenant_id)
            )

        def index_document_chunk(self, _document, source):
            collections[self.tenant_id].add(
                rag_engine._make_vector_id(source.id, "document_chunk", self.tenant_id)
            )

    cleared_tenants: list[str] = []

    def clear_collection(tenant_id: str):
        cleared_tenants.append(tenant_id)
        collections[tenant_id].clear()

    monkeypatch.setattr(reindex_all, "get_rag_indexer", lambda db, tenant_id: FakeRag())
    monkeypatch.setattr(reindex_all, "clear_tenant_collection", clear_collection)

    first_result = reindex_all.reindex_tenant(db, "tenant-a")
    first_set = set(collections["tenant-a"])
    second_result = reindex_all.reindex_tenant(db, "tenant-a")

    assert first_result == second_result
    assert collections["tenant-a"] == first_set
    assert len(first_set) == 2
    assert collections["tenant-b"] == {"vetor-b-preservado"}
    assert cleared_tenants == ["tenant-a", "tenant-a"]


def test_reindex_all_processes_each_tenant_in_order(monkeypatch, rag_modules) -> None:
    reindex_all = rag_modules.reindex_all
    processed: list[str] = []
    monkeypatch.setattr(
        reindex_all,
        "list_tenant_ids",
        lambda db, **kwargs: ["tenant-a", "tenant-b"],
    )

    def fake_reindex_tenant(db, tenant_id: str) -> reindex_all.ReindexResult:
        processed.append(tenant_id)
        return reindex_all.ReindexResult(tenant_id, faq_count=1)

    monkeypatch.setattr(reindex_all, "reindex_tenant", fake_reindex_tenant)

    results = reindex_all.reindex_all(MagicMock())

    assert processed == ["tenant-a", "tenant-b"]
    assert [result.tenant_id for result in results] == processed


def test_reindex_all_stops_before_touching_tenants_after_failure(
    monkeypatch,
    rag_modules,
) -> None:
    reindex_all = rag_modules.reindex_all
    processed: list[str] = []
    monkeypatch.setattr(
        reindex_all,
        "list_tenant_ids",
        lambda db, **kwargs: ["tenant-a", "tenant-b", "tenant-c"],
    )

    def failing_reindex(db, tenant_id: str) -> reindex_all.ReindexResult:
        processed.append(tenant_id)
        if tenant_id == "tenant-b":
            raise RuntimeError("falha visivel")
        return reindex_all.ReindexResult(tenant_id, faq_count=1)

    monkeypatch.setattr(reindex_all, "reindex_tenant", failing_reindex)

    db = MagicMock()
    with pytest.raises(reindex_all.TenantReindexError, match="tenant-b") as exc_info:
        reindex_all.reindex_all(db)

    assert processed == ["tenant-a", "tenant-b"]
    assert exc_info.value.tenant_id == "tenant-b"
    assert exc_info.value.completed_tenant_ids == ("tenant-a",)
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert db.expunge_all.call_count == 2


def test_script_requires_manual_confirmation(monkeypatch, rag_modules) -> None:
    reindex_all = rag_modules.reindex_all
    session_factory = MagicMock()
    monkeypatch.setattr(
        reindex_all,
        "parse_args",
        lambda: SimpleNamespace(confirm=False),
    )
    monkeypatch.setattr(reindex_all, "SessionLocal", session_factory)

    with pytest.raises(SystemExit, match="Use --confirm"):
        reindex_all.main()

    session_factory.assert_not_called()


def test_script_rejects_old_embedding_before_opening_session(
    monkeypatch,
    rag_modules,
) -> None:
    reindex_all = rag_modules.reindex_all
    session_factory = MagicMock()
    monkeypatch.setattr(
        reindex_all,
        "parse_args",
        lambda: SimpleNamespace(confirm=True),
    )
    monkeypatch.setattr(reindex_all, "EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(reindex_all, "SessionLocal", session_factory)

    with pytest.raises(SystemExit, match="EMBED_MODEL deve ser"):
        reindex_all.main()

    session_factory.assert_not_called()


def test_new_collection_records_original_tenant_and_owner(monkeypatch, rag_modules):
    rag = rag_modules.rag_engine
    constructor = MagicMock()
    monkeypatch.setattr(rag, "PGVector", constructor)
    monkeypatch.setattr(rag, "_get_embeddings", lambda: "local-embeddings")
    monkeypatch.setattr(rag, "_enable_langchain_rls_if_possible", lambda: None)
    rag._get_vector_store.cache_clear()
    try:
        rag._get_vector_store("tenant-with/hyphens")
    finally:
        rag._get_vector_store.cache_clear()
    assert constructor.call_args.kwargs["collection_name"] == "knowledge_tenant_with_hyphens"
    assert constructor.call_args.kwargs["collection_metadata"] == {
        "managed_by": "echomind", "schema_version": 1, "tenant_id": "tenant-with/hyphens",
    }


@pytest.mark.parametrize(
    ("case", "expected_status"),
    [
        ("marked", "managed"), ("legacy", "managed"), ("legacy-event", "managed"),
        ("empty-unmarked", "review"), ("mixed-tenants", "review"),
        ("invalid-id", "review"), ("unknown-source", "review"),
        ("conflicting-marker", "review"), ("invalid-marker", "review"),
        ("foreign-owner", "foreign"), ("foreign-name", "foreign"),
    ],
)
def test_collection_identity_requires_proof_without_inverting_name(rag_modules, case, expected_status):
    rag, script = rag_modules.rag_engine, rag_modules.reindex_all
    tenant = "original-tenant"
    source = "event" if case == "legacy-event" else "faq"
    item = {"tenant_id": tenant, "source_type": source, "source_id": "source-a"}
    vector_id = rag._make_vector_id("source-a", source, tenant)
    vectors = [(vector_id, item)]
    metadata = rag._tenant_collection_metadata(tenant) if case in {
        "marked", "conflicting-marker", "invalid-marker",
    } else None
    name = rag._tenant_collection_name(tenant)
    if case == "marked":
        vectors = []
    elif case == "empty-unmarked":
        vectors = []
    elif case == "mixed-tenants":
        other = "original_tenant"
        vectors.append((rag._make_vector_id("source-b", "faq", other), {
            "tenant_id": other, "source_type": "faq", "source_id": "source-b",
        }))
    elif case == "invalid-id":
        vectors[0] = ("random-id", item)
    elif case == "unknown-source":
        vectors[0] = (rag._make_vector_id("source-a", "foreign", tenant), {**item, "source_type": "foreign"})
    elif case == "conflicting-marker":
        metadata["tenant_id"] = "original_tenant"
    elif case == "invalid-marker":
        metadata["schema_version"] = True
    elif case == "foreign-owner":
        metadata = {"managed_by": "another-application"}
    elif case == "foreign-name":
        name = "another-application"
    info = script.identify_collection("collection-uuid", name, metadata, vectors)
    assert info.status == expected_status
    assert info.tenant_id == (tenant if expected_status == "managed" else None)


def test_plan_blocks_colliding_source_tenants_without_creating_collections(db, rag_modules):
    script, Faq = rag_modules.reindex_all, rag_modules.Faq
    db.add_all([
        Faq(tenant_id="original-tenant", question="A?", answer="A."),
        Faq(tenant_id="original_tenant", question="B?", answer="B."),
    ])
    db.flush()
    plan = script.build_reindex_plan(db)
    assert plan.actions == ()
    assert plan.blocked_tenants == ("original-tenant", "original_tenant")
    assert plan.requires_review


def test_dry_run_never_clears_indexes_or_rewrites(monkeypatch, rag_modules, caplog):
    script = rag_modules.reindex_all
    database = MagicMock()
    plan = script.ReindexPlan((script.ReindexAction("original-tenant", "knowledge_original_tenant", "uuid", 7),), (), ())
    monkeypatch.setattr(script, "parse_args", lambda: SimpleNamespace(confirm=False, dry_run=True))
    monkeypatch.setattr(script, "validate_configuration", lambda: None)
    monkeypatch.setattr(script, "SessionLocal", lambda: database)
    monkeypatch.setattr(script, "build_reindex_plan", lambda _: plan)
    clear, reindex, rewrite = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(script, "clear_tenant_collection", clear)
    monkeypatch.setattr(script, "reindex_tenant", reindex)
    monkeypatch.setattr(script, "rewrite_parent_child_and_reindex", rewrite)
    with caplog.at_level("INFO"):
        script.main()
    assert "remover 7 vetor(es)" in caplog.text
    assert "original-tenant" in caplog.text
    clear.assert_not_called()
    reindex.assert_not_called()
    rewrite.assert_not_called()
    database.commit.assert_not_called()
    database.close.assert_called_once()


def test_review_is_reported_with_nonzero_exit_and_no_cleanup(monkeypatch, rag_modules, caplog):
    script = rag_modules.reindex_all
    info = script.CollectionInfo("uuid-review", "knowledge_ambiguous", None, 3, "review", "Tenant nao comprovado.")
    plan = script.ReindexPlan((), (info,), ())
    database, clear = MagicMock(), MagicMock()
    monkeypatch.setattr(script, "parse_args", lambda: SimpleNamespace(confirm=False, dry_run=True))
    monkeypatch.setattr(script, "validate_configuration", lambda: None)
    monkeypatch.setattr(script, "SessionLocal", lambda: database)
    monkeypatch.setattr(script, "build_reindex_plan", lambda _: plan)
    monkeypatch.setattr(script, "clear_tenant_collection", clear)
    with pytest.raises(SystemExit) as caught:
        script.main()
    assert caught.value.code == 2
    assert "REVISAO OPERACIONAL" in caplog.text
    assert "uuid-review" in caplog.text
    clear.assert_not_called()


def test_apply_revalidates_collection_uuid_before_destruction(monkeypatch, rag_modules):
    script = rag_modules.reindex_all
    info = script.CollectionInfo("replacement-uuid", "knowledge_tenant", "tenant", 1, "managed", "marker")
    monkeypatch.setattr(script, "read_collection_inventory", lambda *args, **kwargs: [info])
    plan = script.ReindexPlan((script.ReindexAction("tenant", "knowledge_tenant", "approved-uuid", 1),), (), ())
    reindex = MagicMock()
    monkeypatch.setattr(script, "reindex_tenant", reindex)
    with pytest.raises(script.TenantReindexError) as caught:
        script.reindex_all(MagicMock(), plan=plan)
    assert "mudou desde a previa" in str(caught.value.__cause__)
    reindex.assert_not_called()


def test_faq_reindex_keeps_deterministic_vector_id(
    monkeypatch,
    rag_modules,
) -> None:
    rag_engine = rag_modules.rag_engine
    store = MagicMock()
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: store)
    indexer = object.__new__(rag_engine.RAGEngine)
    indexer.tenant_id = "tenant-a"

    faq = SimpleNamespace(id="faq-1", question="Pergunta?", answer="Resposta.")
    indexer.reindex_faq(faq)

    faq_id = rag_engine._make_vector_id("faq-1", "faq", "tenant-a")
    assert store.delete.call_args_list[0].kwargs == {"ids": [faq_id]}
    assert store.add_documents.call_args_list[0].kwargs == {"ids": [faq_id]}


def test_upsert_without_extra_metadata_preserves_existing_contract(
    monkeypatch,
    rag_modules,
) -> None:
    rag_engine = rag_modules.rag_engine
    store = MagicMock()
    requested_tenants: list[str] = []

    def get_store(tenant_id: str):
        requested_tenants.append(tenant_id)
        return store

    monkeypatch.setattr(rag_engine, "_get_vector_store", get_store)
    indexer = object.__new__(rag_engine.RAGEngine)
    indexer.tenant_id = "tenant-a"

    indexer._upsert_document("faq-1", "faq", "Conteudo")

    vector_id = rag_engine._make_vector_id("faq-1", "faq", "tenant-a")
    document = store.add_documents.call_args.args[0][0]
    assert requested_tenants == ["tenant-a"]
    assert store.add_documents.call_args.kwargs == {"ids": [vector_id]}
    assert document.page_content == "Conteudo"
    assert document.metadata == {
        "source_id": "faq-1",
        "source_type": "faq",
        "tenant_id": "tenant-a",
    }


def test_upsert_merges_valid_extra_metadata(monkeypatch, rag_modules) -> None:
    rag_engine = rag_modules.rag_engine
    store = MagicMock()
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: store)
    indexer = object.__new__(rag_engine.RAGEngine)
    indexer.tenant_id = "tenant-a"

    indexer._upsert_document(
        "source-1",
        "custom",
        "Conteudo",
        extra_metadata={
            "title": "Regulamento",
            "page": 3,
            "published": False,
            "priority": 0,
            "tags": ("institucional", "publico"),
        },
    )

    document = store.add_documents.call_args.args[0][0]
    assert document.metadata == {
        "title": "Regulamento",
        "page": 3,
        "published": False,
        "priority": 0,
        "tags": ["institucional", "publico"],
        "source_id": "source-1",
        "source_type": "custom",
        "tenant_id": "tenant-a",
    }


def test_repeated_upsert_keeps_same_deterministic_id(monkeypatch, rag_modules) -> None:
    rag_engine = rag_modules.rag_engine
    store = MagicMock()
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: store)
    indexer = object.__new__(rag_engine.RAGEngine)
    indexer.tenant_id = "tenant-a"

    for _ in range(2):
        indexer._upsert_document(
            "source-1",
            "custom",
            "Conteudo",
            extra_metadata={"title": "Regulamento"},
        )

    expected_id = rag_engine._make_vector_id("source-1", "custom", "tenant-a")
    assert [call.kwargs for call in store.add_documents.call_args_list] == [
        {"ids": [expected_id]},
        {"ids": [expected_id]},
    ]


def test_upsert_ignores_protected_empty_and_non_serializable_metadata(
    monkeypatch,
    rag_modules,
) -> None:
    rag_engine = rag_modules.rag_engine
    store = MagicMock()
    monkeypatch.setattr(rag_engine, "_get_vector_store", lambda tenant_id: store)
    indexer = object.__new__(rag_engine.RAGEngine)
    indexer.tenant_id = "tenant-a"

    indexer._upsert_document(
        "source-1",
        "custom",
        "Conteudo",
        extra_metadata={
            "source_id": "injetado",
            "source_type": "injetado",
            "tenant_id": "tenant-b",
            "none": None,
            "blank": "  ",
            "empty_list": [],
            "empty_dict": {},
            "object": object(),
            "not_a_number": float("nan"),
            "valid": "preservado",
        },
    )

    document = store.add_documents.call_args.args[0][0]
    assert document.metadata == {
        "valid": "preservado",
        "source_id": "source-1",
        "source_type": "custom",
        "tenant_id": "tenant-a",
    }
