"""Read-only release preflight. Receives DATABASE_URL from the process, never dotenv.

No migrations, table changes, reindexing, user data or secret values are emitted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


BACKEND = Path(__file__).resolve().parents[1]
# Historical revisions import pure helpers from app; no runtime config is loaded.
sys.path.insert(0, str(BACKEND))
REQUIRED_TABLES = {
    "alembic_version", "config", "faqs", "events", "event_courses", "interactions",
    "documents", "document_chunks", "document_chunk_parents", "rag_metric_daily",
    "unanswered_questions", "unanswered_suppressions", "campuses", "campus_buildings",
    "campus_spaces", "campus_path_nodes", "campus_path_edges",
}


def check(database_url: str) -> dict:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("PostgreSQL obrigatório.")
    local = url.host in {"localhost", "127.0.0.1", "::1"}
    if not local and (url.port == 6543 or url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}):
        raise ValueError("Use conexão direta ou session pooler com TLS; transaction pooler não é aceito.")
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            connection.execute(text("SET LOCAL lock_timeout = '3s'"))
            current = list(MigrationContext.configure(connection).get_current_heads())
            if len(current) > 1:
                raise ValueError("Múltiplas revisões aplicadas; reconcilie antes de publicar.")
            pending = [revision.revision for revision in scripts.iterate_revisions(head, current[0] if current else "base")][::-1]
            vector_info = connection.execute(text(
                "SELECT e.extversion, n.nspname FROM pg_extension e "
                "JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname = 'vector'"
            )).one_or_none()
            vector = vector_info[0] if vector_info else None
            major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
            tables = connection.execute(text(
                "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r'"
            )).all()
            unprotected = sorted(row[0] for row in tables if not row[1])
            missing = sorted(REQUIRED_TABLES - {row[0] for row in tables})
            dimensions = connection.execute(text(
                "SELECT c.relname, a.attname, a.atttypmod FROM pg_attribute a "
                "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_type t ON t.oid=a.atttypid WHERE n.nspname='public' "
                "AND c.relkind='r' AND NOT a.attisdropped AND t.typname='vector'"
            )).all()
            wrong_dimensions = [f"{row[0]}.{row[1]}" for row in dimensions if row[2] not in {-1, 384}]
            # LangChain may use unbounded vector columns. Check stored dimensions
            # rather than treating typmod=-1 as an incompatible model.
            quote = connection.dialect.identifier_preparer.quote_identifier
            for table, column, dimension in dimensions:
                if dimension == -1 and vector_info:
                    function = f"{quote(vector_info[1])}.vector_dims"
                    incompatible = connection.execute(text(
                        f"SELECT EXISTS (SELECT 1 FROM public.{quote(table)} "
                        f"WHERE {quote(column)} IS NOT NULL AND {function}({quote(column)}) <> 384)"
                    )).scalar_one()
                    if incompatible:
                        wrong_dimensions.append(f"{table}.{column}")
            legacy_count = None
            if any(row[0] == "campus_locations" for row in tables):
                legacy_count = connection.execute(text("SELECT count(*) FROM public.campus_locations")).scalar_one()
            return {
                "head": head, "current": current, "pending": pending,
                "postgres_major": major, "vector_version": vector,
                "public_tables_without_rls": unprotected,
                "missing_tables": missing, "vector_columns_not_384": wrong_dimensions,
                "legacy_location_count": legacy_count,
                "ready": current == [head] and vector is not None and not unprotected and
                         not missing and not wrong_dimensions and major == 17,
            }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="Inventory only; still reports ready=false.")
    args = parser.parse_args()
    try:
        report = check(os.environ["DATABASE_URL"])
    except Exception:
        # Driver errors can contain a DSN, SQL parameters or user records.
        print("Preflight indisponível. Confira conexão, TLS, permissões e histórico Alembic em ambiente privado.")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] or args.inventory else 1


if __name__ == "__main__":
    raise SystemExit(main())
