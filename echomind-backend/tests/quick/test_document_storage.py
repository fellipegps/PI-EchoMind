from hashlib import sha256
import io
from pathlib import Path
import tarfile
from threading import Event, Thread
from unittest.mock import MagicMock

import pytest
from filelock import Timeout

from app.document_storage import DocumentStorage, DocumentStorageError, DocumentMaintenanceError


def saved(storage, tenant="tenant-a", document="document-a", content=b"Original institucional."):
    path = storage.save(tenant_id=tenant, document_id=document, content=content, digest=sha256(content).hexdigest())
    return path, content


def original(storage, content, tenant="tenant-a", document="document-a"):
    return storage.read_original(tenant_id=tenant, document_id=document, digest=sha256(content).hexdigest(), size=len(content))


def test_original_is_durable_isolated_and_independent_of_client_paths(tmp_path):
    storage = DocumentStorage(tmp_path)
    path, content = saved(storage, tenant="../../tenant", document="../document")
    reconstructed = DocumentStorage(tmp_path)
    assert original(reconstructed, content, "../../tenant", "../document") == content
    assert path.is_relative_to(tmp_path)
    assert reconstructed.read_job(path)["action"] == "ingest"
    assert all(len(part) == 32 for part in path.relative_to(tmp_path).parts[:2])
    with pytest.raises(FileNotFoundError):
        original(reconstructed, content, "other-tenant", "../document")


def test_bad_hash_and_full_disk_do_not_create_accepted_jobs(tmp_path, monkeypatch):
    storage = DocumentStorage(tmp_path)
    with pytest.raises(DocumentStorageError):
        storage.save(tenant_id="tenant-a", document_id="document-a", content=b"a", digest="bad")
    monkeypatch.setattr("app.document_storage.shutil.disk_usage", lambda path: type("Usage", (), {"free": 1})())
    with pytest.raises(DocumentStorageError):
        saved(storage)
    assert list(storage.jobs()) == []


@pytest.mark.parametrize("replacement", [b"x", b"X" * len(b"Original institucional.")])
def test_corruption_is_detected_without_processing(tmp_path, replacement):
    storage = DocumentStorage(tmp_path)
    path, content = saved(storage)
    path.with_name("original.bin").write_bytes(replacement)
    with pytest.raises(DocumentStorageError):
        original(storage, content)


def test_maintenance_is_durable_and_blocks_writes_until_resume(tmp_path):
    storage = DocumentStorage(tmp_path)
    storage.drain(timeout=1)
    replacement = DocumentStorage(tmp_path)
    assert replacement.status()["draining"] is True
    with pytest.raises(DocumentMaintenanceError):
        with replacement.admission():
            pytest.fail("Maintenance must reject admission.")
    replacement.resume()
    with storage.admission():
        saved(storage)


def test_drain_waits_for_current_processing_and_blocks_new_work(tmp_path):
    storage = DocumentStorage(tmp_path)
    waiting = Event()
    finished = Event()
    errors = []

    def drain():
        waiting.set()
        try:
            storage.drain(timeout=3)
            finished.set()
        except Exception as exc:
            errors.append(exc)

    with storage.lock("processing"):
        thread = Thread(target=drain)
        thread.start()
        waiting.wait(1)
        assert not finished.wait(0.1)
        with pytest.raises(Timeout):
            DocumentStorage(tmp_path).lock("processing").acquire()
    thread.join(timeout=3)
    assert not errors
    assert finished.is_set() and storage.draining


def test_backup_restore_retains_original_and_pending_job(tmp_path):
    source = DocumentStorage(tmp_path / "source")
    path, content = saved(source)
    archive = io.BytesIO()
    with pytest.raises(DocumentMaintenanceError):
        source.backup(archive)
    source.drain()
    source.backup(archive)
    target = DocumentStorage(tmp_path / "restored")
    target.drain()
    archive.seek(0)
    target.restore(archive)
    assert original(target, content) == content
    assert target.read_job(next(target.jobs())) == source.read_job(path)
    assert target.draining  # Restore never enables processing before the DB is checked.
    archive.seek(0)
    with pytest.raises(DocumentStorageError):
        target.restore(archive)


@pytest.mark.parametrize("name,type_", [("../../outside", tarfile.REGTYPE), ("a" * 32 + "/" + "b" * 32 + "/original.bin", tarfile.SYMTYPE)])
def test_restore_rejects_path_traversal_and_links(tmp_path, name, type_):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as output:
        member = tarfile.TarInfo(name)
        member.type = type_
        member.size = 0
        output.addfile(member, io.BytesIO())
    archive.seek(0)
    storage = DocumentStorage(tmp_path / "restored")
    storage.drain()
    with pytest.raises(DocumentStorageError):
        storage.restore(archive)
    assert not (tmp_path / "outside").exists()


def test_api_does_not_accept_upload_when_original_cannot_be_saved(client, monkeypatch):
    from app import main
    processor = MagicMock()
    monkeypatch.setattr(main, "process_document", processor)
    monkeypatch.setattr(DocumentStorage, "save", MagicMock(side_effect=OSError("private path and internal detail")))
    response = client.post("/documents/upload", files={"file": ("norma.txt", b"texto", "text/plain")})
    assert response.status_code == 503
    assert "private" not in response.text
    processor.assert_not_called()
    assert client.get("/documents").json()["total"] == 0


def test_api_original_exists_before_processor_and_maintenance_blocks_document_writes(client, monkeypatch):
    from app import main
    storage = DocumentStorage()
    captured = {}

    def process(**kwargs):
        captured.update(kwargs)
        assert original(storage, kwargs["content"], kwargs["tenant_id"], kwargs["document_id"]) == kwargs["content"]

    monkeypatch.setattr(main, "process_document", process)
    response = client.post("/documents/upload", files={"file": ("norma.txt", b"texto duravel", "text/plain")})
    assert response.status_code == 202
    storage.drain()
    assert client.post("/documents/upload", files={"file": ("outra.txt", b"outro", "text/plain")}).status_code == 503
    assert client.delete("/documents/" + response.json()["id"]).status_code == 503
    assert captured["content"] == b"texto duravel"


def test_api_deletion_removes_original_after_successful_database_commit(client, db):
    from app import document_repository as repository
    content = b"original a excluir"
    document = repository.create_document(db, tenant_id="test-admin", data=repository.DocumentCreateData(
        filename="norma.txt", mime_type="text/plain", size_bytes=len(content), sha256=sha256(content).hexdigest(),
    ))
    identifier = document.id
    for status in ("processing", "ready"):
        repository.transition_document_status(db, tenant_id="test-admin", document_id=identifier, target_status=status)
    storage = DocumentStorage()
    path, _ = saved(storage, tenant="test-admin", document=identifier, content=content)
    db.commit()
    assert client.delete(f"/documents/{identifier}").status_code == 204
    assert not path.exists() and not path.with_name("original.bin").exists()


def test_database_commit_failure_preserves_original_and_job_for_reconciliation(client, db, monkeypatch):
    monkeypatch.setattr(db, "commit", MagicMock(side_effect=RuntimeError("ambiguous DB commit")))
    response = client.post("/documents/upload", files={"file": ("norma.txt", b"original protegido", "text/plain")})
    assert response.status_code == 500
    storage = DocumentStorage()
    path = next(storage.jobs())
    job = storage.read_job(path)
    assert storage.read_original(tenant_id=job["tenant_id"], document_id=job["document_id"], digest=job["sha256"], size=job["size_bytes"]) == b"original protegido"
