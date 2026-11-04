"""Grants reais em banco descartável com roles equivalentes às do Supabase."""
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def test_hardening_revokes_direct_and_default_grants_without_breaking_backend(postgres_engine):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    with postgres_engine.begin() as connection:
        config.attributes["connection"] = connection
        for role in ("anon", "authenticated"):
            connection.execute(text(f"""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    CREATE ROLE {role} NOLOGIN;
                END IF;
            END $$"""))
            connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        command.downgrade(config, "0024")
        connection.execute(text("GRANT ALL ON TABLE public.config TO PUBLIC, anon, authenticated"))
        connection.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC, anon, authenticated"))
        command.upgrade(config, "0025")
        connection.execute(text("CREATE TABLE public.privacy_future_table_probe (id integer)"))
        for table in ("config", "privacy_future_table_probe"):
            for role in ("anon", "authenticated"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                    assert connection.execute(text(
                        "SELECT has_table_privilege(:role,:table,:privilege)"
                    ), {"role": role, "table": f"public.{table}", "privilege": privilege}).scalar() is False
                with pytest.raises(DBAPIError), connection.begin_nested():
                    connection.execute(text(f"SET LOCAL ROLE {role}"))
                    connection.execute(text(f"SELECT * FROM public.{table} LIMIT 0"))
        connection.execute(text("INSERT INTO public.config (id,tenant_id,public_slug,company_name) VALUES ('acl-probe','acl-probe','acl-probe','Synthetic')"))
        assert connection.execute(text("SELECT count(*) FROM public.config WHERE id='acl-probe'")).scalar() == 1
        command.downgrade(config, "0024")
        assert connection.execute(text("SELECT has_table_privilege('anon','public.config','SELECT')")).scalar() is False
        command.upgrade(config, "0025")
        connection.execute(text("DELETE FROM public.config WHERE id='acl-probe'"))
        connection.execute(text("DROP TABLE public.privacy_future_table_probe"))
        command.upgrade(config, "head")
