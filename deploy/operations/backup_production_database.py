"""Private consistent public-schema backup + restore rehearsal; never migrates production.

Uses existing local configuration only inside this process. On Docker Desktop,
a loopback-only TCP relay carries end-to-end PostgreSQL TLS to an IPv6 endpoint.
Raw data, credentials, connection errors and the restore manifest stay ignored
by Git under .database-backups. No private values are printed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import socket
import socketserver
import subprocess
import threading
import time
import uuid

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]


def table_counts(connection):
    tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars().all()
    quote = connection.dialect.identifier_preparer.quote_identifier
    return {table: connection.execute(text(f'SELECT count(*) FROM public.{quote(table)}')).scalar_one() for table in tables}


def run(args, *, env=None, stdin=None, stdout=None, stderr=None, timeout=600):
    result = subprocess.run(args, env=env, stdin=stdin, stdout=stdout or subprocess.DEVNULL,
                            stderr=stderr or subprocess.DEVNULL, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Private database operation failed; inspect restricted logs locally.')


def backup(project):
    folder = ROOT / '.database-backups'
    if not folder.is_dir() or folder.is_symlink():
        raise RuntimeError('Prepare the ignored private backup directory and restricted ACL first.')
    if os.name == 'posix' and folder.stat().st_mode & 0o077:
        raise RuntimeError('Require owner-only backup directory permissions.')
    os.umask(0o077)
    values = dotenv_values(ROOT / 'echomind-backend/.env')
    url = make_url(values['DATABASE_URL'])
    if (values.get('SUPABASE_URL', '').rstrip('/') != f'https://{project}.supabase.co'
            or url.host != f'db.{project}.supabase.co'):
        raise RuntimeError('Local configuration does not match the explicitly selected project/direct endpoint.')
    url = url.set(query=dict(url.query) | {'sslmode': 'require'})
    engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 10})
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = folder / f'public-{stamp}.dump'
    log_path = folder / f'private-{stamp}.log'
    restore_name = 'echomind-restore-' + uuid.uuid4().hex[:12]
    created = False
    server = None
    local_engine = None
    try:
        with engine.connect() as source, source.begin():
            source.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            source.execute(text("SET LOCAL statement_timeout = '60s'"))
            revision = source.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one()
            counts = table_counts(source)
            snapshot = source.execute(text('SELECT pg_export_snapshot()')).scalar_one()

            class Relay(socketserver.BaseRequestHandler):
                def handle(self):
                    try:
                        with socket.create_connection((url.host, url.port or 5432), timeout=10) as upstream:
                            sockets = [self.request, upstream]
                            while True:
                                readable, _, _ = select.select(sockets, [], [], 120)
                                if not readable:
                                    return
                                for sender in readable:
                                    data = sender.recv(65536)
                                    if not data:
                                        return
                                    receiver = upstream if sender is self.request else self.request
                                    receiver.sendall(data)
                    except OSError:
                        pass

            class Server(socketserver.ThreadingTCPServer):
                daemon_threads = True

            server = Server(('127.0.0.1', 0), Relay)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            environment = dict(os.environ, PGHOST='host.docker.internal', PGPORT=str(server.server_address[1]),
                               PGUSER=url.username, PGPASSWORD=url.password, PGDATABASE=url.database,
                               PGSSLMODE='require', PGCONNECT_TIMEOUT='10')
            args = ['docker', 'run', '--rm', '--pull', 'never']
            for key in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSSLMODE', 'PGCONNECT_TIMEOUT'):
                args.extend(['--env', key])
            args.extend(['pgvector/pgvector:0.8.6-pg17', 'pg_dump', '--format=custom', '--schema=public',
                         '--no-owner', '--no-acl', '--snapshot', snapshot])
            with archive.open('xb') as target, log_path.open('xb') as log:
                run(args, env=environment, stdout=target, stderr=log)
            # The exported snapshot remains valid until pg_dump has completed.
        server.shutdown()
        server.server_close()
        server = None
        if archive.stat().st_size == 0:
            raise RuntimeError('Empty dump.')
        print('Consistent private public-schema backup completed.', flush=True)

        password = secrets.token_urlsafe(24)
        environment = dict(os.environ, POSTGRES_PASSWORD=password)
        run(['docker', 'run', '--detach', '--rm', '--pull', 'never', '--name', restore_name,
             '--publish', '127.0.0.1::5432', '--env', 'POSTGRES_PASSWORD', '--env', 'POSTGRES_DB=echomind_restorecheck',
             'pgvector/pgvector:0.8.6-pg17'], env=environment)
        created = True
        for _ in range(40):
            result = subprocess.run(['docker', 'exec', restore_name, 'pg_isready', '-q', '-U', 'postgres'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                break
            time.sleep(0.5)
        result = subprocess.run(['docker', 'port', restore_name, '5432/tcp'], capture_output=True, check=True)
        port = int(result.stdout.decode().strip().rsplit(':', 1)[1])
        local_engine = create_engine(f'postgresql://postgres:{password}@127.0.0.1:{port}/echomind_restorecheck', poolclass=NullPool)
        with local_engine.begin() as connection:
            connection.execute(text('CREATE EXTENSION vector WITH SCHEMA public'))
            connection.execute(text('CREATE EXTENSION "uuid-ossp" WITH SCHEMA public'))
            for role in ('anon', 'authenticated', 'service_role'):
                connection.execute(text(f'CREATE ROLE {role} NOLOGIN'))
        with archive.open('rb') as dump, log_path.open('ab') as log:
            run(['docker', 'exec', '-i', restore_name, 'pg_restore', '-U', 'postgres', '--dbname=echomind_restorecheck',
                 '--schema=public', '--no-owner', '--no-acl', '--single-transaction', '--exit-on-error'], stdin=dump, stderr=log)
        with local_engine.connect() as connection:
            restored_counts = table_counts(connection)
            restored_revision = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one()
            if restored_counts != counts or restored_revision != revision:
                raise RuntimeError('Restored row counts/revision differ from the exported snapshot.')
            unprotected = connection.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity")).scalar_one()
            if unprotected:
                raise RuntimeError('Restored schema contains unprotected public tables.')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = {'created_at': stamp, 'project': project, 'revision': revision, 'sha256': digest,
                    'bytes': archive.stat().st_size, 'table_counts': counts, 'restored_counts_match': True,
                    'restored_rls_validated': True, 'scope': 'public schema only; not Auth/Storage/roles/configuration'}
        archive.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'backup_restore_validated': True, 'revision': revision, 'public_tables': len(counts),
                          'legacy_table_empty': counts.get('campus_locations') == 0, 'backup_file': archive.name}), flush=True)
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if local_engine:
            local_engine.dispose()
        if created:
            subprocess.run(['docker', 'stop', restore_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-project', required=True)
    args = parser.parse_args()
    try:
        backup(args.expected_project)
    except Exception:
        print('Backup/restore verification failed. Private files/logs retained; production was not migrated.')
        raise SystemExit(1) from None
