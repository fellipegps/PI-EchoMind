"""Serialize ingestion and recover durable jobs without loading models eagerly."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread

from filelock import Timeout

from .document_storage import DocumentStorage, DocumentStorageError


def _report_error(exc: Exception) -> None:
    from .structured_logging import emit_event, safe_error_code
    emit_event(
        event="rag.document-recovery", status="error", stage="recovery",
        error_code=safe_error_code(exc),
    )


class DocumentRuntime:
    def __init__(self, storage: DocumentStorage | None = None, processor=None):
        self.storage = storage or DocumentStorage()
        self.processor = processor
        self._stop = Event()
        self._thread: Thread | None = None

    def run_job(self, job_path: Path, *, recover: bool = False) -> None:
        try:
            with self.storage.lock("processing"):
                if self._stop.is_set() or self.storage.draining or not job_path.exists():
                    return
                job = self.storage.read_job(job_path)
                if recover or job["action"] == "delete":
                    state = self._database_state(job)
                    if state is None:
                        if job["action"] == "delete":
                            self.storage.delete(job["tenant_id"], job["document_id"])
                        return  # Commit may still be in flight; keep orphan originals.
                    if job["action"] == "delete":
                        return  # Relational deletion has not committed yet.
                    if state["status"] in {"ready", "error"}:
                        self.storage.acknowledge(job_path)
                        return
                    if state["sha256"] != job["sha256"] or state["size_bytes"] != job["size_bytes"]:
                        self._mark_missing_original(job)
                        self.storage.acknowledge(job_path)
                        _report_error(DocumentStorageError("Database and original disagree."))
                        return
                else:
                    state = {"status": "pending"}
                try:
                    content = self.storage.read_original(
                        tenant_id=job["tenant_id"], document_id=job["document_id"],
                        digest=job["sha256"], size=job["size_bytes"],
                    )
                except (OSError, DocumentStorageError) as exc:
                    self._mark_missing_original(job)
                    self.storage.acknowledge(job_path)
                    _report_error(exc)
                    return
                from .document_processing import process_document
                processor = self.processor or process_document
                options = {"resume_interrupted": True} if state["status"] == "processing" else {}
                result = processor(
                    document_id=job["document_id"], tenant_id=job["tenant_id"],
                    content=content, **options,
                )
                if getattr(result, "status", None) in {"ready", "error"}:
                    self.storage.acknowledge(job_path)
        except Timeout:
            pass  # Another task owns the single ingestion slot; periodic recovery retries.
        except Exception as exc:
            _report_error(exc)  # Keep the job for transient failures, including DB outages.

    @staticmethod
    def _database_state(job: dict) -> dict | None:
        from .document_processing import SessionLocal
        from .document_repository import get_document
        with SessionLocal() as db:
            document = get_document(db, tenant_id=job["tenant_id"], document_id=job["document_id"])
            if document is None:
                return None
            return {"status": document.status, "sha256": document.sha256, "size_bytes": document.size_bytes}

    @staticmethod
    def _mark_missing_original(job: dict) -> None:
        from .document_processing import SessionLocal
        from .document_repository import get_document, transition_document_status
        with SessionLocal() as db:
            document = get_document(db, tenant_id=job["tenant_id"], document_id=job["document_id"])
            if document is None or document.status in {"ready", "error"}:
                return
            if document.status == "pending":
                transition_document_status(db, tenant_id=job["tenant_id"], document_id=job["document_id"], target_status="processing")
            transition_document_status(
                db, tenant_id=job["tenant_id"], document_id=job["document_id"], target_status="error",
                error_message="Arquivo original indisponível ou corrompido. Envie o documento novamente.",
            )
            db.commit()

    def recover_once(self) -> None:
        for path in self.storage.jobs():
            if self._stop.is_set() or self.storage.draining:
                break
            self.run_job(path, recover=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.recover_once()
            except Exception as exc:
                _report_error(exc)
            self._stop.wait(5)

    def start(self) -> None:
        if self._stop.is_set() or (self._thread is not None and self._thread.is_alive()):
            return
        if os.getenv("DOCUMENT_RECOVERY_ENABLED", "true").lower() in {"false", "0", "no"}:
            return
        self._thread = Thread(target=self._run, name="echomind-document-recovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=300)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private document maintenance; run through docker exec.")
    parser.add_argument("action", choices=("status", "drain", "resume", "backup", "restore"))
    parser.add_argument("--timeout", type=float, default=300)
    arguments = parser.parse_args()
    storage = DocumentStorage()
    if arguments.action == "drain":
        storage.drain(timeout=arguments.timeout)
    elif arguments.action == "resume":
        storage.resume()
    elif arguments.action == "backup":
        storage.backup(sys.stdout.buffer)
        return
    elif arguments.action == "restore":
        storage.restore(sys.stdin.buffer)
    print(json.dumps(storage.status()))


if __name__ == "__main__":
    main()
