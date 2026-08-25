#!/usr/bin/env python3
"""Reindexa manualmente fontes RAG persistidas, uma colecao por tenant."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import (  # noqa: E402
    CompanyEvent,
    DATABASE_URL,
    Document,
    DocumentChunk,
    Faq,
    SessionLocal,
)
from app.rag_engine import (  # noqa: E402
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    EMBED_MODEL,
    clear_tenant_collection,
    get_rag_indexer,
)
from app.schemas import DocumentStatus  # noqa: E402


log = logging.getLogger("reindex_all")


@dataclass(frozen=True)
class ReindexResult:
    tenant_id: str
    faq_count: int
    event_count: int
    document_count: int = 0
    document_chunk_count: int = 0


class TenantReindexError(RuntimeError):
    """Identifica o tenant que falhou e os ja concluidos nesta execucao."""

    def __init__(self, tenant_id: str, completed_tenant_ids: tuple[str, ...]):
        self.tenant_id = tenant_id
        self.completed_tenant_ids = completed_tenant_ids
        completed = ", ".join(completed_tenant_ids) if completed_tenant_ids else "nenhum"
        super().__init__(
            f"Falha ao reindexar tenant {tenant_id!r}; "
            f"tenants concluidos antes da falha: {completed}."
        )


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
    """Seleciona tenants com FAQ, evento ou documento ready para reindexar."""
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
    document_rows = (
        db.query(Document.tenant_id)
        .filter(
            Document.tenant_id.isnot(None),
            Document.tenant_id != "",
            Document.status == DocumentStatus.READY.value,
        )
        .distinct()
        .all()
    )
    return sorted({row[0] for row in (*faq_rows, *event_rows, *document_rows)})


def reindex_tenant(db: Session, tenant_id: str) -> ReindexResult:
    """Reconstrói uma colecao com fontes persistidas e prontas do tenant."""
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
    documents = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.READY.value,
        )
        .order_by(Document.id.asc())
        .all()
    )
    document_ids = [document.id for document in documents]
    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id.in_(document_ids),
        )
        .order_by(
            DocumentChunk.document_id.asc(),
            DocumentChunk.chunk_index.asc(),
            DocumentChunk.id.asc(),
        )
        .all()
        if document_ids
        else []
    )

    documents_by_id = {document.id: document for document in documents}
    actual_chunk_counts = {document.id: 0 for document in documents}
    for chunk in chunks:
        actual_chunk_counts[chunk.document_id] += 1
    for document in documents:
        actual_count = actual_chunk_counts[document.id]
        if document.chunk_count != actual_count:
            raise RuntimeError(
                "Contagem de chunks inconsistente antes da limpeza da colecao: "
                f"tenant={tenant_id!r}, document_id={document.id!r}, "
                f"registrado={document.chunk_count}, persistido={actual_count}."
            )

    # Valida a configuracao do RAG antes da limpeza destrutiva da colecao.
    rag = get_rag_indexer(db, tenant_id=tenant_id)
    clear_tenant_collection(tenant_id)

    for faq in faqs:
        rag.index_faq(faq)
    for event in events:
        rag.index_event(event)
    for chunk in chunks:
        rag.index_document_chunk(documents_by_id[chunk.document_id], chunk)

    return ReindexResult(
        tenant_id=tenant_id,
        faq_count=len(faqs),
        event_count=len(events),
        document_count=len(documents),
        document_chunk_count=len(chunks),
    )


def reindex_all(db: Session) -> list[ReindexResult]:
    results: list[ReindexResult] = []
    for tenant_id in list_tenant_ids(db):
        log.info("Reindexando tenant %s...", tenant_id)
        try:
            result = reindex_tenant(db, tenant_id)
            results.append(result)
            log.info(
                "Tenant %s concluido: %d FAQ(s), %d evento(s), "
                "%d documento(s) ready, %d chunk(s).",
                tenant_id,
                result.faq_count,
                result.event_count,
                result.document_count,
                result.document_chunk_count,
            )
        except Exception as exc:
            completed_tenant_ids = tuple(result.tenant_id for result in results)
            log.exception(
                "Tenant %s falhou; reindexacao interrompida apos: %s.",
                tenant_id,
                ", ".join(completed_tenant_ids) or "nenhum tenant",
            )
            raise TenantReindexError(tenant_id, completed_tenant_ids) from exc
        finally:
            db.expunge_all()
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Limpa e reindexa colecoes RAG de FAQs, eventos e chunks ready por tenant."
        )
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
            "das colecoes RAG por tenant."
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
    total_documents = sum(result.document_count for result in results)
    total_document_chunks = sum(result.document_chunk_count for result in results)
    log.info(
        "Reindexacao concluida: %d tenant(s), %d FAQ(s), %d evento(s), "
        "%d documento(s) ready, %d chunk(s).",
        len(results),
        total_faqs,
        total_events,
        total_documents,
        total_document_chunks,
    )


if __name__ == "__main__":
    main()
