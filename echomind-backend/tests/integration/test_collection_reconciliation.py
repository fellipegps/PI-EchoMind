"""Reconcilia colecoes reais sem inferir tenant de nomes sanitizados."""

from types import SimpleNamespace
from uuid import uuid4
from hashlib import sha256

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


pytestmark = pytest.mark.integration


@pytest.fixture()
def collection_runtime(monkeypatch, postgres_engine, deterministic_fake_embeddings):
    from app import rag_engine

    monkeypatch.setattr(rag_engine, "_get_embeddings", lambda: deterministic_fake_embeddings)
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()
    stores = []
    tenants = []

    def indexer(tenant):
        tenants.append(tenant)
        instance = object.__new__(rag_engine.RAGEngine)
        instance.tenant_id = tenant
        store = rag_engine._get_vector_store(tenant)
        stores.append(store)
        return instance, store

    try:
        yield SimpleNamespace(
            engine=postgres_engine, embeddings=deterministic_fake_embeddings,
            rag=rag_engine, indexer=indexer, stores=stores,
        )
    finally:
        from app.database import Faq, Document

        for store in stores:
            store.delete_collection()
        with Session(postgres_engine) as session:
            session.query(Faq).filter(Faq.tenant_id.in_(tenants)).delete(synchronize_session=False)
            session.query(Document).filter(Document.tenant_id.in_(tenants)).delete(synchronize_session=False)
            session.commit()
        rag_engine._get_vector_store.cache_clear()
        rag_engine._enable_langchain_rls_if_possible.cache_clear()


def _orphan(runtime, tenant):
    indexer, store = runtime.indexer(tenant)
    indexer.index_faq(SimpleNamespace(
        id=str(uuid4()), tenant_id=tenant, question="FAQ removida?",
        answer="Vetor sintetico orfao.", show_in_chatbot=False,
    ))
    return store


def test_general_reindex_discovers_tenant_with_only_legacy_orphan_vectors(collection_runtime):
    from scripts import reindex_all

    runtime = collection_runtime
    tenant = "legacy-orphan-" + uuid4().hex
    store = _orphan(runtime, tenant)
    with runtime.engine.begin() as connection:
        connection.execute(text("UPDATE langchain_pg_collection SET cmetadata = NULL WHERE name = :name"), {"name": store.collection_name})
    with Session(runtime.engine) as session:
        assert tenant in reindex_all.list_tenant_ids(session)
        results = reindex_all.reindex_all(session)
        assert tenant in {result.tenant_id for result in results}
    assert store.similarity_search("orfao", k=10) == []


@pytest.fixture()
def reconciliation_case(collection_runtime):
    from langchain_community.vectorstores.pgvector import PGVector
    from langchain_core.documents import Document as VectorDocument
    from app.database import Faq
    from app.document_repository import DocumentCreateData, DocumentChunkData, create_document, replace_document_chunks

    runtime = collection_runtime
    suffix = uuid4().hex
    orphan, valid = "a-orphan-" + suffix, "b-valid-" + suffix
    orphan_store = _orphan(runtime, orphan)
    with runtime.engine.begin() as connection:
        connection.execute(text("UPDATE langchain_pg_collection SET cmetadata = NULL WHERE name = :name"), {"name": orphan_store.collection_name})
    indexer, valid_store = runtime.indexer(valid)
    expected_ids, preserved = [], []
    with Session(runtime.engine) as session:
        faq = Faq(tenant_id=valid, question="FAQ persistida?", answer="Resposta valida.")
        session.add(faq)
        session.flush()
        expected_ids.append(runtime.rag._make_vector_id(faq.id, "faq", valid))
        documents = []
        for status in ("ready", "pending", "processing", "error"):
            document = create_document(session, tenant_id=valid, data=DocumentCreateData(
                filename=status + ".txt", mime_type="text/plain", size_bytes=64,
                sha256=sha256((valid + status).encode()).hexdigest(),
            ))
            document.status = status
            chunks = replace_document_chunks(
                session, tenant_id=valid, document_id=document.id,
                chunks=[DocumentChunkData(content=f"Trecho {status} {i}.") for i in range(2)],
            )
            documents.append((document, chunks))
            preserved.append((document.id, status, tuple(chunk.id for chunk in chunks)))
            if status == "ready":
                expected_ids.extend(runtime.rag._make_vector_id(chunk.id, "document_chunk", valid) for chunk in chunks)
        session.commit()
        indexer.index_faq(faq)
        for document, chunks in documents:
            indexer.reindex_document_chunks(document, chunks)
        indexer._upsert_document("removed-event", "event", "Evento legado fora do RAG atual.")

    ambiguous_a = "c-ambiguous-" + suffix
    ambiguous_b = ambiguous_a.replace("-", "_")
    ambiguous_store = _orphan(runtime, ambiguous_a)
    _orphan(runtime, ambiguous_b)
    with runtime.engine.begin() as connection:
        connection.execute(text("UPDATE langchain_pg_collection SET cmetadata = NULL WHERE name = :name"), {"name": ambiguous_store.collection_name})

    foreign_tenant = "foreign-" + suffix
    foreign_store = PGVector(
        connection_string=runtime.rag.DATABASE_URL,
        embedding_function=runtime.embeddings,
        collection_name=runtime.rag._tenant_collection_name(foreign_tenant),
        collection_metadata={"managed_by": "another-application"},
        use_jsonb=True,
    )
    runtime.stores.append(foreign_store)
    foreign_store.add_documents([VectorDocument(page_content="Dado alheio preservado.", metadata={
        "tenant_id": foreign_tenant, "source_type": "faq", "source_id": "foreign-id",
    })], ids=[runtime.rag._make_vector_id("foreign-id", "faq", foreign_tenant)])

    names = list({store.collection_name for store in runtime.stores})

    def snapshot():
        with runtime.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT c.uuid, c.name, c.cmetadata AS owner, e.custom_id, e.cmetadata,
                       e.document, md5(e.embedding::text) AS embedding_hash
                FROM langchain_pg_collection c
                LEFT JOIN langchain_pg_embedding e ON e.collection_id = c.uuid
                WHERE c.name = ANY(:names) ORDER BY c.name, e.custom_id
            """), {"names": names}).mappings().all()
            return [dict(row) for row in rows]

    return SimpleNamespace(
        runtime=runtime, orphan=orphan, valid=valid, orphan_store=orphan_store,
        valid_store=valid_store, ambiguous_store=ambiguous_store,
        foreign_store=foreign_store, snapshot=snapshot,
        expected_ids=sorted(expected_ids), preserved=preserved,
    )


def _assert_rebuilt(case):
    from app.document_repository import get_document, list_document_chunks

    assert case.orphan_store.similarity_search("orfao", k=20) == []
    rows = [row for row in case.snapshot() if row["name"] == case.valid_store.collection_name]
    assert sorted(row["custom_id"] for row in rows) == case.expected_ids
    assert {row["cmetadata"]["source_type"] for row in rows} == {"faq", "document_chunk"}
    assert all(row["owner"] == case.runtime.rag._tenant_collection_metadata(case.valid) for row in rows)
    with Session(case.runtime.engine) as session:
        for identifier, status, chunk_ids in case.preserved:
            assert get_document(session, tenant_id=case.valid, document_id=identifier).status == status
            assert tuple(chunk.id for chunk in list_document_chunks(
                session, tenant_id=case.valid, document_id=identifier,
            )) == chunk_ids


def _protected_rows(case):
    return [row for row in case.snapshot() if row["name"] in {
        case.ambiguous_store.collection_name, case.foreign_store.collection_name,
    }]


def test_dry_run_is_read_only_and_reports_ambiguous_and_foreign_collections(reconciliation_case, monkeypatch, caplog):
    from scripts import reindex_all

    case = reconciliation_case
    before = case.snapshot()
    monkeypatch.setattr(reindex_all, "parse_args", lambda: SimpleNamespace(confirm=False, dry_run=True))
    monkeypatch.setattr(reindex_all, "SessionLocal", lambda: Session(case.runtime.engine))
    def forbidden(*args, **kwargs):
        raise AssertionError("A previa nao pode criar ou remover vetores.")
    monkeypatch.setattr(reindex_all, "clear_tenant_collection", forbidden)
    monkeypatch.setattr(reindex_all, "get_rag_indexer", forbidden)
    with caplog.at_level("INFO"), pytest.raises(SystemExit) as caught:
        reindex_all.main()
    assert caught.value.code == 2
    assert "PREVIA" in caplog.text
    assert case.orphan in caplog.text
    assert "REVISAO OPERACIONAL" in caplog.text
    assert "PRESERVAR ALHEIA" in caplog.text
    assert case.snapshot() == before


def test_general_reindex_reconciles_only_proven_collections_idempotently(reconciliation_case):
    from scripts import reindex_all

    case = reconciliation_case
    protected = _protected_rows(case)
    with Session(case.runtime.engine) as session:
        plan = reindex_all.build_reindex_plan(session)
        assert set(plan.tenant_ids) == {case.orphan, case.valid}
        assert plan.requires_review
        first = reindex_all.reindex_all(session, plan=plan)
        _assert_rebuilt(case)
        first_vectors = [
            (row["custom_id"], row["cmetadata"], row["document"], row["embedding_hash"])
            for row in case.snapshot() if row["name"] == case.valid_store.collection_name
        ]
        second = reindex_all.reindex_all(session)
    assert first == second
    _assert_rebuilt(case)
    assert _protected_rows(case) == protected
    assert [
        (row["custom_id"], row["cmetadata"], row["document"], row["embedding_hash"])
        for row in case.snapshot() if row["name"] == case.valid_store.collection_name
    ] == first_vectors
    orphan_rows = [row for row in case.snapshot() if row["name"] == case.orphan_store.collection_name]
    assert orphan_rows[0]["owner"] == case.runtime.rag._tenant_collection_metadata(case.orphan)


def test_failed_rebuild_stops_and_can_resume_without_touching_unproven_collections(reconciliation_case, monkeypatch):
    from scripts import reindex_all

    case = reconciliation_case
    protected = _protected_rows(case)
    original = case.runtime.rag.RAGEngine.index_document_chunk
    def fail_after_one(self, document, chunk):
        original(self, document, chunk)
        if self.tenant_id == case.valid:
            raise RuntimeError("Falha apos gravacao parcial de vetor.")
    monkeypatch.setattr(case.runtime.rag.RAGEngine, "index_document_chunk", fail_after_one)
    with Session(case.runtime.engine) as session:
        with pytest.raises(reindex_all.TenantReindexError) as caught:
            reindex_all.reindex_all(session)
        assert caught.value.tenant_id == case.valid
        assert caught.value.completed_tenant_ids == (case.orphan,)
        assert "vazia ou parcial" in str(caught.value)
        assert len(case.valid_store.similarity_search("trecho", k=20)) == 2
        assert _protected_rows(case) == protected
        monkeypatch.setattr(case.runtime.rag.RAGEngine, "index_document_chunk", original)
        reindex_all.reindex_all(session)
    _assert_rebuilt(case)
    assert _protected_rows(case) == protected


def test_changed_ownership_after_preview_blocks_apply_before_cleanup(collection_runtime):
    from scripts import reindex_all

    runtime = collection_runtime
    tenant = "changed-owner-" + uuid4().hex
    store = _orphan(runtime, tenant)
    with Session(runtime.engine) as session:
        plan = reindex_all.build_reindex_plan(session)
        with runtime.engine.begin() as connection:
            connection.execute(text("""
                UPDATE langchain_pg_collection
                SET cmetadata = '{"managed_by":"another-application"}'::json
                WHERE name = :name
            """), {"name": store.collection_name})
        with pytest.raises(reindex_all.TenantReindexError):
            reindex_all.reindex_all(session, plan=plan)
    assert len(store.similarity_search("orfao", k=10)) == 1
