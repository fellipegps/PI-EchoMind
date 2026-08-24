"""Fixtures exclusivas dos testes com PostgreSQL e pgvector reais."""

from __future__ import annotations

import os
from collections.abc import Generator
from hashlib import sha256
from math import sqrt

import pytest
from langchain_core.embeddings import Embeddings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool


EXPECTED_DATABASE_NAME = "echomind_integration"
LOCAL_DATABASE_HOSTS = {"127.0.0.1", "localhost", "::1"}


class DeterministicFakeEmbeddings(Embeddings):
    """Embedding 384d local e estavel, sem modelos ou chamadas externas."""

    dimension = 384

    @classmethod
    def _embed(cls, text_value: str) -> list[float]:
        digest = sha256(text_value.encode("utf-8")).digest()
        values = [digest[index % len(digest)] / 127.5 - 1.0 for index in range(cls.dimension)]
        norm = sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text_value) for text_value in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture(scope="session")
def deterministic_fake_embeddings() -> DeterministicFakeEmbeddings:
    return DeterministicFakeEmbeddings()


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    """Aceita somente o banco local e descartavel reservado para integracao."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.fail("DATABASE_URL deve apontar para o PostgreSQL descartavel de integracao.")

    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail("A suite integration exige PostgreSQL real; SQLite nao e aceito.")
    if parsed_url.host not in LOCAL_DATABASE_HOSTS:
        pytest.fail("A suite integration recusa bancos remotos, inclusive staging/producao.")
    if parsed_url.database != EXPECTED_DATABASE_NAME:
        pytest.fail(
            f"O banco descartavel deve se chamar {EXPECTED_DATABASE_NAME!r}; "
            f"recebido {parsed_url.database!r}."
        )

    return database_url


@pytest.fixture(scope="session")
def postgres_engine(integration_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(integration_database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield engine
    finally:
        engine.dispose()
