"""Restore a pinned private archive into an isolated temporary directory only.

Run inside the existing backend with the archive on stdin. Never starts recovery,
loads embeddings, modifies the live document volume or writes to the database.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import tempfile

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def rehearse_archive(data: bytes, expected: list[dict], *, temporary_parent=None) -> dict:
    from app.document_storage import DocumentStorage

    if not data or len(data) > MAX_ARCHIVE_BYTES or not expected:
        raise ValueError('Require a bounded archive and a nonempty reference inventory.')
    keys = {(str(row['tenant_id']), str(row['id'])) for row in expected}
    if len(keys) != len(expected):
        raise ValueError('Duplicate inventory identity.')
    with tempfile.TemporaryDirectory(prefix='echomind-restore-check-', dir=temporary_parent) as directory:
        restored_root = Path(directory) / 'documents'
        restored = DocumentStorage(restored_root)
        restored.drain(timeout=5)
        restored.restore(BytesIO(data))
        expected_paths = set()
        for row in expected:
            path = restored.directory(row['tenant_id'], row['id']) / 'original.bin'
            restored.read_original(tenant_id=row['tenant_id'], document_id=row['id'],
                                   digest=row['sha256'], size=row['size_bytes'])
            expected_paths.add(path)
        if set(restored.root.glob('*/*/original.bin')) != expected_paths or any(restored.jobs()):
            raise ValueError('Restored inventory differs from the ready-document reference.')
        files = len(expected_paths)
    return {'restored_originals': files, 'all_hashes_and_sizes_match': True,
            'temporary_directory_removed': not Path(directory).exists(),
            'scope': 'Application document archive, not EBS snapshot or external database recovery'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.sha256):
        parser.error('Require a SHA-256 pinned through the authenticated control channel.')
    data = sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != args.sha256:
        raise ValueError('Archive size or digest mismatch.')

    from sqlalchemy import text
    from app.database import engine
    from app.document_storage import DocumentStorage
    live = DocumentStorage()
    if live.draining or any(live.jobs()):
        raise ValueError('Wait for an idle document runtime.')
    with engine.connect() as connection, connection.begin():
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text("SET LOCAL statement_timeout = '10s'"))
        expected = [dict(row) for row in connection.execute(text(
            "SELECT id,tenant_id,sha256,size_bytes FROM public.documents WHERE status='ready'"
        )).mappings()]
    for row in expected:
        live.read_original(tenant_id=row['tenant_id'], document_id=row['id'],
                           digest=row['sha256'], size=row['size_bytes'])
    report = rehearse_archive(data, expected)
    # Check the live originals again, without pausing or restoring the live volume.
    for row in expected:
        live.read_original(tenant_id=row['tenant_id'], document_id=row['id'],
                           digest=row['sha256'], size=row['size_bytes'])
    print(json.dumps({**report, 'archive_bytes':len(data), 'archive_sha256':args.sha256,
        'live_originals_valid_before_and_after':True, 'database_writes':False,
        'live_volume_restored':False, 'additional_embedding_model_loaded':False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Isolated document restore verification failed; private diagnostics suppressed.')
        raise SystemExit(1) from None
