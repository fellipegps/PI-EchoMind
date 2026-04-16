"""
alembic/env.py
Conecta o Alembic ao SQLAlchemy e ao DATABASE_URL do ambiente.
Suporta migrações online (com banco ativo) e offline (gera SQL puro).
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ─── Garante que o pacote `app` seja importável ───────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base  # noqa: E402 — importa após ajuste do path

# ─── Lê configuração do alembic.ini ──────────────────────────────────────────
config = context.config

# Sobrescreve a URL com a variável de ambiente (prioridade sobre alembic.ini)
database_url = os.getenv(
    "DATABASE_URL",
    "postgresql://echomind:echomind@localhost:5432/echomind",
)
config.set_main_option("sqlalchemy.url", database_url)

# Configura logging conforme definido no alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata com todos os modelos — necessário para autogenerate
target_metadata = Base.metadata


# ─── Modo Offline (gera SQL sem conectar ao banco) ────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Necessário para pgvector: não tenta inspecionar tipos customizados
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ─── Modo Online (conecta e aplica as migrações) ──────────────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
