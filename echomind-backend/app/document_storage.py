"""Durable originals and job markers on a private, single-host volume."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
from typing import BinaryIO, Iterator

from filelock import FileLock, Timeout


class DocumentStorageError(Exception):
    """Storage is unavailable or the original does not match its metadata."""


class DocumentMaintenanceError(DocumentStorageError):
    """Document writes are paused for maintenance."""


def _sync_directory(directory: Path) -> None:
    if os.name == "posix":
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


class DocumentStorage:
    def __init__(self, root: Path | str | None = None):
        configured = root or os.getenv("DOCUMENT_STORAGE_DIR")
        self.root = Path(configured or Path.home() / ".local/share/echomind/documents").resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def lock(self, name: str, timeout: float = 0) -> FileLock:
        if name not in {"admission", "processing"}:
            raise ValueError("Unknown document lock.")
        return FileLock(str(self.root / f".{name}.lock"), timeout=timeout, mode=0o600)

    @property
    def draining(self) -> bool:
        return (self.root / ".draining").exists()

    @contextmanager
    def admission(self) -> Iterator[None]:
        try:
            with self.lock("admission", timeout=10):
                if self.draining:
                    raise DocumentMaintenanceError("Document writes paused.")
                yield
        except Timeout as exc:
            raise DocumentMaintenanceError("Document admission busy.") from exc

    def directory(self, tenant_id: str, document_id: str) -> Path:
        if not tenant_id or not document_id:
            raise DocumentStorageError("Missing document identity.")
        directory = self.root
        for identifier in (tenant_id, document_id):
            # 128-bit namespace keys keep development paths usable on Windows.
            # File integrity still uses the full SHA-256 from the database.
            directory = directory / sha256(identifier.encode()).hexdigest()[:32]
            if directory.is_symlink():
                raise DocumentStorageError("Invalid storage directory.")
        return directory

    def write_job(self, tenant_id: str, document_id: str, **metadata) -> Path:
        directory = self.directory(tenant_id, document_id)
        directory.parent.mkdir(exist_ok=True, mode=0o700)
        directory.mkdir(exist_ok=True, mode=0o700)
        _sync_directory(self.root)
        _sync_directory(directory.parent)
        job = {"version": 1, "tenant_id": tenant_id, "document_id": document_id, **metadata}
        path = directory / "job.json"
        _atomic_write(path, json.dumps(job).encode())
        return path

    def save(self, *, tenant_id: str, document_id: str, content: bytes, digest: str) -> Path:
        if sha256(content).hexdigest() != digest:
            raise DocumentStorageError("Original hash mismatch.")
        if shutil.disk_usage(self.root).free < len(content) + 64 * 1024 * 1024:
            raise DocumentStorageError("Insufficient document storage.")
        directory = self.directory(tenant_id, document_id)
        directory.parent.mkdir(exist_ok=True, mode=0o700)
        directory.mkdir(exist_ok=True, mode=0o700)
        _sync_directory(self.root)
        _sync_directory(directory.parent)
        _atomic_write(directory / "original.bin", content)
        return self.write_job(
            tenant_id, document_id, action="ingest", sha256=digest, size_bytes=len(content),
        )

    def jobs(self) -> Iterator[Path]:
        yield from self.root.glob("*/*/job.json")

    def read_job(self, path: Path) -> dict:
        if path.parent.is_symlink() or path.parent.parent.is_symlink() or path.is_symlink() or path.stat().st_size > 16_384:
            raise DocumentStorageError("Invalid job marker.")
        job = json.loads(path.read_text(encoding="utf-8"))
        if (
            job.get("version") != 1
            or job.get("action") not in {"ingest", "delete"}
            or self.directory(job["tenant_id"], job["document_id"]) / "job.json" != path
        ):
            raise DocumentStorageError("Invalid job identity.")
        return job

    def read_original(self, *, tenant_id: str, document_id: str, digest: str, size: int) -> bytes:
        path = self.directory(tenant_id, document_id) / "original.bin"
        if path.is_symlink() or path.stat().st_size != size:
            raise DocumentStorageError("Original size mismatch.")
        with path.open("rb") as source:
            content = source.read(size + 1)
        if len(content) != size or sha256(content).hexdigest() != digest:
            raise DocumentStorageError("Original integrity failure.")
        return content

    def acknowledge(self, job_path: Path) -> None:
        job_path.unlink(missing_ok=True)
        _sync_directory(job_path.parent)

    def delete(self, tenant_id: str, document_id: str) -> None:
        directory = self.directory(tenant_id, document_id)
        if not directory.exists():
            return  # Documents uploaded before durable storage have no original.
        for name in ("original.bin", "job.json"):
            (directory / name).unlink(missing_ok=True)
        _sync_directory(directory)

    def drain(self, timeout: float = 300) -> None:
        with self.lock("admission", timeout=timeout):
            _atomic_write(self.root / ".draining", b"maintenance")
        # New workers check the persisted flag after acquiring this lock.
        # A timeout leaves maintenance enabled; the operator can retry or resume.
        with self.lock("processing", timeout=timeout):
            pass

    def resume(self) -> None:
        with self.lock("admission", timeout=10):
            (self.root / ".draining").unlink(missing_ok=True)
            _sync_directory(self.root)

    def status(self) -> dict:
        try:
            with self.lock("processing"):
                active = False
        except Timeout:
            active = True
        return {"draining": self.draining, "active": active, "queued_jobs": sum(1 for _ in self.jobs())}

    @contextmanager
    def maintenance(self) -> Iterator[None]:
        with self.lock("admission", timeout=10), self.lock("processing", timeout=10):
            if not self.draining:
                raise DocumentMaintenanceError("Drain before backup or restore.")
            yield

    def backup(self, output: BinaryIO) -> None:
        with self.maintenance(), tarfile.open(fileobj=output, mode="w|") as archive:
            for path in self.root.glob("*/*/*"):
                if path.parent.is_symlink() or path.parent.parent.is_symlink():
                    raise DocumentStorageError("Invalid backup directory.")
                if path.name in {"original.bin", "job.json"}:
                    if path.is_symlink() or not path.is_file():
                        raise DocumentStorageError("Invalid backup file.")
                    archive.add(path, arcname=path.relative_to(self.root).as_posix(), recursive=False)

    def restore(self, source: BinaryIO) -> None:
        with self.maintenance():
            if any(self.root.glob("*/*/original.bin")) or any(self.jobs()):
                raise DocumentStorageError("Restore requires an empty document volume.")
            seen = set()
            with tarfile.open(fileobj=source, mode="r|") as archive:
                for member in archive:
                    # No extractall, symlinks, absolute paths, links or arbitrary names.
                    if (
                        not member.isfile()
                        or not re.fullmatch(r"[0-9a-f]{32}/[0-9a-f]{32}/(original\.bin|job\.json)", member.name)
                        or member.name in seen
                        or member.size < 0 or member.size > 100 * 1024 * 1024
                    ):
                        raise DocumentStorageError("Invalid backup member.")
                    seen.add(member.name)
                    path = self.root / member.name
                    if path.parent.is_symlink() or path.parent.parent.is_symlink():
                        raise DocumentStorageError("Invalid restore directory.")
                    path.parent.parent.mkdir(exist_ok=True, mode=0o700)
                    path.parent.mkdir(exist_ok=True, mode=0o700)
                    stream = archive.extractfile(member)
                    content = stream.read(member.size + 1)
                    if len(content) != member.size:
                        raise DocumentStorageError("Incomplete backup member.")
                    _atomic_write(path, content)
                    _sync_directory(path.parent.parent)
            _sync_directory(self.root)
