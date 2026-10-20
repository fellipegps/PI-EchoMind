"""Restore one missing original from decrypted stdin, without changing DB/chunks.

Run inside the production backend as its ordinary UID. Default is a dry run.
The input must arrive via a private pipe after authenticated encrypted transfer.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid


def restore(payload: dict, *, apply=False):
    from sqlalchemy import text
    from app.database import engine
    from app.document_storage import DocumentStorage, _sync_directory

    document_id = payload["document_id"]
    if payload.get("version") != 1 or str(uuid.UUID(document_id)) != document_id:
        raise ValueError("Invalid restore identity.")
    content = base64.b64decode(payload["original_b64"], validate=True)
    digest = hashlib.sha256(content).hexdigest()
    if len(content) > 10 * 1024 * 1024 or digest != payload["sha256"]:
        raise ValueError("Original integrity mismatch.")
    storage = DocumentStorage()
    # Same admission lock used by uploads/deletions, plus the DB row lock.
    # No job marker is created and no reindexing or database mutation runs.
    with storage.admission(), engine.begin() as connection:
        row = connection.execute(text(
            "SELECT tenant_id,sha256,size_bytes,status FROM public.documents "
            "WHERE id=:id FOR UPDATE"
        ), {"id": document_id}).mappings().one()
        if row["status"] != "ready" or row["sha256"] != digest or row["size_bytes"] != len(content):
            raise ValueError("Original does not match the current ready document.")
        directory = storage.directory(row["tenant_id"], document_id)
        original = directory / "original.bin"
        if (directory / "job.json").exists() or original.is_symlink():
            raise ValueError("Pending job or unsafe original path.")
        if original.exists():
            storage.read_original(tenant_id=row["tenant_id"], document_id=document_id,
                                  digest=digest, size=len(content))
            return {"original_already_valid": True, "restored": False}
        if not apply:
            return {"ready_to_restore": True, "bytes": len(content), "database_unchanged": True}
        directory.parent.mkdir(mode=0o700, exist_ok=True)
        directory.mkdir(mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".restore-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            # Atomic no-clobber: preserve any concurrently installed original.
            os.link(temporary, original)
            _sync_directory(directory)
            _sync_directory(directory.parent)
            _sync_directory(storage.root)
        finally:
            Path(temporary).unlink(missing_ok=True)
        storage.read_original(tenant_id=row["tenant_id"], document_id=document_id,
                              digest=digest, size=len(content))
    return {"restored": True, "bytes": len(content), "database_unchanged": True,
            "reindex_scheduled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Restore envelope too large.")
        print(json.dumps(restore(json.loads(raw), apply=args.apply)))
    except Exception:
        print("Original restoration aborted; existing data preserved, private diagnostics suppressed.")
        raise SystemExit(1) from None
