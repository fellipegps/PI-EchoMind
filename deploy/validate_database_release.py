"""Rehearse migrations and application backup in disposable LOCAL PostgreSQL.

Requires Docker and the backend Python dependencies already installed.
Never loads .env, connects to Supabase, or downloads an image.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "echomind-backend"
IMAGE = "pgvector/pgvector:0.8.6-pg17"


def run(arguments: list[str], **options) -> str:
    response = subprocess.run(arguments, capture_output=True, text=True, timeout=120, **options)
    if response.returncode:
        # Only synthetic data/credentials are used by this test.
        raise RuntimeError(response.stdout + response.stderr)
    return response.stdout.strip()


def main() -> None:
    name = "echomind-release-test-" + uuid.uuid4().hex[:10]
    created = False

    def inside(*command: str) -> str:
        return run(["docker", "exec", name, *command])

    def sql(query: str, database: str = "echomind_integration") -> str:
        return inside("psql", "-U", "echomind_ci", "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", query)

    try:
        run(["docker", "run", "--rm", "--pull", "never", "--name", name, "-d",
             "-e", "POSTGRES_USER=echomind_ci", "-e", "POSTGRES_PASSWORD=echomind_ci",
             "-e", "POSTGRES_DB=echomind_integration", "-p", "127.0.0.1::5432", IMAGE])
        created = True
        port = int(run(["docker", "port", name, "5432/tcp"]).rsplit(":", 1)[1])
        for _ in range(60):
            try:
                sql("SELECT 1")
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError("Local PostgreSQL did not become ready.")
        environment = os.environ | {
            "DATABASE_URL": f"postgresql://echomind_ci:echomind_ci@127.0.0.1:{port}/echomind_integration?sslmode=disable",
            "ECHOMIND_ENV": "testing", "PYTHONDONTWRITEBYTECODE": "1",
        }

        def migrate(target: str) -> None:
            run([sys.executable, "-m", "alembic", "upgrade", target], cwd=BACKEND, env=environment)

        def preflight() -> dict:
            return json.loads(run([sys.executable, "scripts/check_database.py", "--inventory"],
                                  cwd=BACKEND, env=environment))

        migrate("0022")
        sql("INSERT INTO campus_locations (id,tenant_id,name,x,y) "
            "VALUES ('release-sentinel','synthetic-tenant','Restore sentinel',50,50)")
        before = preflight()
        assert before["current"] == ["0022"] and before["pending"] == ["0023"]
        assert before["legacy_location_count"] == 1 and not before["ready"]
        print("PASS: read-only preflight detects pending destructive migration", flush=True)

        inside("pg_dump", "-U", "echomind_ci", "-d", "echomind_integration", "--schema=public",
               "--format=custom", "--no-owner", "--no-privileges", "--file=/tmp/before.dump")
        inside("pg_restore", "--list", "/tmp/before.dump")
        migrate("head")
        after = preflight()
        assert after["ready"] and after["current"] == ["0023"]
        assert sql("SELECT to_regclass('public.campus_locations') IS NULL") == "t"
        print("PASS: migration reaches head and removes retired table", flush=True)

        sql("CREATE TABLE release_vector_probe (embedding vector); "
            "ALTER TABLE release_vector_probe ENABLE ROW LEVEL SECURITY; "
            "INSERT INTO release_vector_probe VALUES (array_fill(1::real, ARRAY[384])::vector)")
        assert preflight()["ready"]
        sql("UPDATE release_vector_probe SET embedding='[1,2,3]'::vector")
        incompatible = preflight()
        assert not incompatible["ready"]
        assert incompatible["vector_columns_not_384"] == ["release_vector_probe.embedding"]
        sql("DROP TABLE release_vector_probe")
        print("PASS: preflight checks stored dimensions in unbounded vector columns", flush=True)

        inside("createdb", "-U", "echomind_ci", "echomind_restorecheck")
        sql('CREATE EXTENSION vector; CREATE EXTENSION "uuid-ossp"', "echomind_restorecheck")
        # --schema also skips CREATE SCHEMA public, which exists in the empty DB.
        inside("pg_restore", "-U", "echomind_ci", "-d", "echomind_restorecheck", "--schema=public",
               "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction", "/tmp/before.dump")
        assert sql("SELECT version_num FROM alembic_version", "echomind_restorecheck") == "0022"
        assert sql("SELECT count(*) FROM campus_locations WHERE id='release-sentinel'", "echomind_restorecheck") == "1"
        assert sql("SELECT relrowsecurity FROM pg_class WHERE oid='public.campus_locations'::regclass",
                   "echomind_restorecheck") == "t"
        print("PASS: backup restores previous revision, removed data and RLS in separate empty DB", flush=True)

        # The archive stays inside the disposable container; no real data is read.
        print("PASS: no remote database, real credentials or persistent backup files used", flush=True)
    finally:
        if created:
            run(["docker", "stop", name])


if __name__ == "__main__":
    main()
