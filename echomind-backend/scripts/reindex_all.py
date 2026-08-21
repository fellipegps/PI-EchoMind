#!/usr/bin/env python3
"""Reindexa manualmente FAQs e eventos, uma colecao isolada por tenant."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import CompanyEvent, DATABASE_URL, Faq, SessionLocal  # noqa: E402
from app.rag_engine import (  # noqa: E402
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    EMBED_MODEL,
    clear_tenant_collection,
    get_rag_engine,
)


log = logging.getLogger("reindex_all")


@dataclass(frozen=True)
class ReindexResult:
    tenant_id: str
    faq_count: int
    event_count: int


def validate_configuration() -> None:
    """Impede limpeza com modelo, dimensao ou banco incompatíveis."""
    if EMBED_MODEL != DEFAULT_EMBED_MODEL:
        raise RuntimeError(
            f"EMBED_MODEL deve ser {DEFAULT_EMBED_MODEL!r} antes da reindexacao; "
            f"recebido {EMBED_MODEL!r}."
        )
    if EMBEDDING_DIM != DEFAULT_EMBEDDING_DIM:
        raise RuntimeError(
            f"EMBEDDING_DIM deve permanecer em {DEFAULT_EMBEDDING_DIM}."
        )
    if not DATABASE_URL.startswith("postgresql"):
        raise RuntimeError("A reindexacao exige DATABASE_URL PostgreSQL valida.")


def list_tenant_ids(db: Session) -> list[str]:
    """Seleciona somente tenants que possuem FAQ ou evento para reindexar."""
    faq_rows = (
        db.query(Faq.tenant_id)
        .filter(Faq.tenant_id.isnot(None), Faq.tenant_id != "")
        .distinct()
        .all()
    )
    event_rows = (
        db.query(CompanyEvent.tenant_id)
        .filter(CompanyEvent.tenant_id.isnot(None), CompanyEvent.tenant_id != "")
        .distinct()
        .all()
    )
    return sorted({row[0] for row in (*faq_rows, *event_rows)})


def reindex_tenant(db: Session, tenant_id: str) -> ReindexResult:
    """Limpa uma colecao e reindexa apenas FAQs/eventos do mesmo tenant."""
    faqs = (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id)
        .order_by(Faq.id.asc())
        .all()
    )
    events = (
        db.query(CompanyEvent)
        .filter(CompanyEvent.tenant_id == tenant_id)
        .order_by(CompanyEvent.id.asc())
        .all()
    )

    # Valida a configuracao do RAG antes da limpeza destrutiva da colecao.
    rag = get_rag_engine(db, tenant_id=tenant_id)
    clear_tenant_collection(tenant_id)

    for faq in faqs:
        rag.index_faq(faq)
    for event in events:
        rag.index_event(event)

    return ReindexResult(
        tenant_id=tenant_id,
        faq_count=len(faqs),
        event_count=len(events),
    )


def reindex_all(db: Session) -> list[ReindexResult]:
    results: list[ReindexResult] = []
    for tenant_id in list_tenant_ids(db):
        log.info("Reindexando tenant %s...", tenant_id)
        result = reindex_tenant(db, tenant_id)
        results.append(result)
        log.info(
            "Tenant %s concluido: %d FAQ(s), %d evento(s).",
            tenant_id,
            result.faq_count,
            result.event_count,
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpa e reindexa colecoes RAG de FAQs/eventos por tenant."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma conscientemente a limpeza das colecoes antes da reindexacao.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    args = parse_args()
    if not args.confirm:
        raise SystemExit(
            "Reindexacao nao executada. Use --confirm para autorizar a limpeza "
            "das colecoes de FAQs/eventos."
        )

    try:
        validate_configuration()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    db = SessionLocal()
    try:
        results = reindex_all(db)
    except Exception:
        log.exception("Reindexacao interrompida com erro visivel.")
        raise SystemExit(1)
    finally:
        db.close()

    total_faqs = sum(result.faq_count for result in results)
    total_events = sum(result.event_count for result in results)
    log.info(
        "Reindexacao concluida: %d tenant(s), %d FAQ(s), %d evento(s).",
        len(results),
        total_faqs,
        total_events,
    )


if __name__ == "__main__":
    main()
