from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock
from threading import Event, Thread

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.document_storage import DocumentStorage
from app.document_runtime import DocumentRuntime


@pytest.fixture()
def recovery(quick_test_context, monkeypatch):
    from app import document_processing as processing, document_repository as repository
    from app.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(processing, "SessionLocal", sessions)
    indexer = MagicMock()
    monkeypatch.setattr(processing, "get_rag_indexer", lambda db, tenant: indexer)
    context = SimpleNamespace(sessions=sessions, processing=processing, repository=repository, indexer=indexer, storage=DocumentStorage())
    yield context
    engine.dispose()


def enqueue(context, *, document_id=None, status="pending", content=b"Documento institucional com conteudo original e rastreavel."):
    with context.sessions() as db:
        document = context.repository.create_document(
            db, tenant_id="tenant-a",
            data=context.repository.DocumentCreateData(filename="norma.txt", mime_type="text/plain", size_bytes=len(content), sha256=sha256(content).hexdigest()),
        )
        if document_id is not None:
            document.id = document_id
            db.flush()
        if status == "processing":
            context.repository.transition_document_status(db, tenant_id="tenant-a", document_id=document.id, target_status="processing")
        path = context.storage.save(tenant_id="tenant-a", document_id=document.id, content=content, digest=document.sha256)
        db.commit()
        return document.id, path, content


def state(context, identifier):
    with context.sessions() as db:
        document = context.repository.get_document(db, tenant_id="tenant-a", document_id=identifier)
        return document.status


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_recovery_after_restart_finishes_accepted_document_and_is_idempotent(recovery, status):
    identifier, path, content = enqueue(recovery, status=status)
    runtime = DocumentRuntime(recovery.storage)
    runtime.recover_once()
    assert state(recovery, identifier) == "ready"
    assert not path.exists()
    assert recovery.storage.read_original(tenant_id="tenant-a", document_id=identifier, digest=sha256(content).hexdigest(), size=len(content)) == content
    calls = recovery.indexer.reindex_document_chunks.call_count
    DocumentRuntime(recovery.storage).recover_once()
    assert recovery.indexer.reindex_document_chunks.call_count == calls == 1


def test_interruption_after_partial_indexing_removes_known_old_vectors_before_replacing_chunks(recovery):
    identifier, path, content = enqueue(recovery, status="processing")
    with recovery.sessions() as db:
        recovery.repository.replace_document_chunks(db, tenant_id="tenant-a", document_id=identifier, chunks=[recovery.repository.DocumentChunkData(content="chunk parcial")])
        db.commit()
    DocumentRuntime(recovery.storage).recover_once()
    assert state(recovery, identifier) == "ready"
    recovery.indexer.delete_document_chunks.assert_called_once()
    assert recovery.indexer.reindex_document_chunks.call_count == 1


def test_corrupted_original_marks_error_without_reindexing(recovery):
    identifier, path, content = enqueue(recovery)
    path.with_name("original.bin").write_bytes(b"corrompido")
    DocumentRuntime(recovery.storage).recover_once()
    assert state(recovery, identifier) == "error"
    recovery.indexer.reindex_document_chunks.assert_not_called()
    assert not path.exists()


def test_uncommitted_or_orphan_job_is_preserved_and_db_outage_is_retried(recovery, monkeypatch):
    identifier, path, content = enqueue(recovery)
    runtime = DocumentRuntime(recovery.storage)
    monkeypatch.setattr(runtime, "_database_state", MagicMock(side_effect=RuntimeError("temporary database outage")))
    runtime.recover_once()
    assert path.exists() and state(recovery, identifier) == "pending"
    DocumentRuntime(recovery.storage).recover_once()
    assert state(recovery, identifier) == "ready"
    orphan = recovery.storage.save(tenant_id="tenant-a", document_id="uncommitted", content=b"orphan", digest=sha256(b"orphan").hexdigest())
    DocumentRuntime(recovery.storage).recover_once()
    assert orphan.exists()


def test_maintenance_and_ingestion_lock_prevent_recovery_overlap(recovery):
    identifier, path, content = enqueue(recovery)
    runtime = DocumentRuntime(recovery.storage)
    with recovery.storage.lock("processing"):
        runtime.recover_once()
    assert state(recovery, identifier) == "pending"
    recovery.storage.drain()
    DocumentRuntime(recovery.storage).recover_once()
    assert state(recovery, identifier) == "pending"
    recovery.storage.resume()
    DocumentRuntime(recovery.storage).recover_once()
    assert state(recovery, identifier) == "ready"


def test_original_deletion_recovers_only_after_relational_delete_commits(recovery):
    identifier, path, content = enqueue(recovery)
    recovery.storage.write_job("tenant-a", identifier, action="delete")
    runtime = DocumentRuntime(recovery.storage)
    runtime.recover_once()
    assert path.with_name("original.bin").exists()
    with recovery.sessions() as db:
        from app.database import Document
        db.query(Document).filter(Document.id == identifier).delete()
        db.commit()
    DocumentRuntime(recovery.storage).recover_once()
    assert not path.exists() and not path.with_name("original.bin").exists()


def test_periodic_worker_recovers_jobs_automatically_and_stops(recovery, monkeypatch):
    identifier, path, content = enqueue(recovery)
    finished = Event()

    def process(**kwargs):
        result = recovery.processing.process_document(**kwargs)
        finished.set()
        return result

    monkeypatch.setenv("DOCUMENT_RECOVERY_ENABLED", "true")
    runtime = DocumentRuntime(recovery.storage, processor=process)
    try:
        runtime.start()
        assert finished.wait(5)
    finally:
        runtime.stop()
    assert state(recovery, identifier) == "ready"
    assert not runtime._thread.is_alive()


@pytest.mark.parametrize("shutdown_during_warmup", [False, True])
def test_recovery_waits_for_model_warmup_and_never_starts_after_shutdown(recovery, monkeypatch, shutdown_during_warmup):
    from app import main
    entered, release, recovered = Event(), Event(), Event()

    def warmup():
        entered.set()
        assert release.wait(5)

    runtime = DocumentRuntime(recovery.storage)
    monkeypatch.setenv("DOCUMENT_RECOVERY_ENABLED", "true")
    monkeypatch.setattr(main, "warm_up_rag_runtime", warmup)
    monkeypatch.setattr(runtime, "recover_once", recovered.set)
    loader = Thread(target=main.warm_up_then_start_documents, args=(runtime,))
    try:
        loader.start()
        assert entered.wait(5)
        assert not recovered.is_set()
        if shutdown_during_warmup:
            runtime.stop()
        release.set()
        loader.join(timeout=5)
        if shutdown_during_warmup:
            assert not recovered.is_set() and runtime._thread is None
        else:
            assert recovered.wait(5)
    finally:
        release.set()
        loader.join(timeout=5)
        runtime.stop()
