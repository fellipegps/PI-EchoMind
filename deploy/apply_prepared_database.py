"""Apply only reviewed 0022 -> 0023 after a verified private backup/restore.

Checks and the empty legacy table's removal share one PostgreSQL transaction.
Never prints credentials or provider exception text. No other revision is applied.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parent.parent


def apply(backup_manifest: Path, project: str):
    path = backup_manifest.resolve()
    if path.parent != ROOT / '.database-backups':
        raise RuntimeError('Expected a private backup manifest inside the prepared directory.')
    manifest = json.loads(path.read_text())
    dump = path.with_suffix('.dump')
    age = datetime.now(timezone.utc) - datetime.strptime(manifest['created_at'], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    if (manifest.get('project') != project or manifest.get('revision') != '0022'
            or manifest.get('restored_counts_match') is not True or manifest.get('restored_rls_validated') is not True
            or manifest['table_counts'].get('campus_locations') != 0 or age.total_seconds() > 7200
            or hashlib.sha256(dump.read_bytes()).hexdigest() != manifest['sha256']):
        raise RuntimeError('Require a recent, intact, restored backup of revision 0022 with an empty legacy table.')
    values = dotenv_values(ROOT / 'echomind-backend/.env')
    url = make_url(values['DATABASE_URL'])
    if (values.get('SUPABASE_URL', '').rstrip('/') != f'https://{project}.supabase.co'
            or url.host != f'db.{project}.supabase.co'):
        raise RuntimeError('Configuration does not match the selected project.')
    url = url.set(query=dict(url.query) | {'sslmode': 'require'})
    os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
    os.environ['ECHOMIND_ENV'] = 'testing'  # Alembic imports models only; never loads local dotenv.
    engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 10})
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            connection.execute(text('SELECT pg_advisory_xact_lock(184733028)'))
            if connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() != '0022':
                raise RuntimeError('Database revision changed; review again.')
            connection.execute(text('LOCK TABLE public.campus_locations IN ACCESS EXCLUSIVE MODE'))
            if connection.execute(text('SELECT count(*) FROM public.campus_locations')).scalar_one() != 0:
                raise RuntimeError('Legacy table gained data; stop and review a new backup.')
            config = Config(str(ROOT / 'echomind-backend/alembic.ini'))
            config.set_main_option('script_location', str(ROOT / 'echomind-backend/alembic'))
            config.attributes['connection'] = connection
            command.upgrade(config, '0023')
            if (connection.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one() != '0023'
                    or connection.execute(text("SELECT to_regclass('public.campus_locations') IS NULL")).scalar_one() is not True):
                raise RuntimeError('Post-migration assertion failed; transaction rolled back.')
        print('Reviewed migration committed: 0022 -> 0023. Empty legacy table removed; private backup preserved.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-manifest', required=True, type=Path)
    parser.add_argument('--expected-project', required=True)
    args = parser.parse_args()
    try:
        apply(args.backup_manifest, args.expected_project)
    except Exception:
        print('Migration aborted; inspect privately. Credentials and database error text suppressed.')
        raise SystemExit(1) from None
