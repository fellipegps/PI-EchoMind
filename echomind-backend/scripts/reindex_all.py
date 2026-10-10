#!/usr/bin/env python3
"""Reindexa manualmente fontes RAG persistidas, uma colecao por tenant."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from collections import Counter

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import (  # noqa: E402
    DATABASE_URL,
    Document,
    DocumentChunk,
    DocumentChunkParent,
    Faq,
    SessionLocal,
)
from app.document_ingestion import ChunkedTextBlock, group_document_children  # noqa: E402
from app.document_repository import (  # noqa: E402
    DocumentParentData,
    replace_document_parent_links,
)
from app.rag_engine import (  # noqa: E402
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    EMBED_MODEL,
    clear_tenant_collection,
    get_rag_indexer,
    _make_vector_id,
    _tenant_collection_metadata,
    _tenant_collection_name,
)
from app.schemas import DocumentStatus  # noqa: E402


log = logging.getLogger("reindex_all")


@dataclass(frozen=True)
class ReindexResult:
    tenant_id: str
    faq_count: int
    document_count: int = 0
    document_chunk_count: int = 0


@dataclass(frozen=True)
class CollectionInfo:
    collection_id: str
    name: str
    tenant_id: str | None
    vector_count: int
    status: str
    reason: str


@dataclass(frozen=True)
class ReindexAction:
    tenant_id: str
    collection_name: str
    collection_id: str | None
    vector_count: int


@dataclass(frozen=True)
class ReindexPlan:
    actions: tuple[ReindexAction, ...]
    collections: tuple[CollectionInfo, ...]
    blocked_tenants: tuple[str, ...]

    @property
    def tenant_ids(self) -> list[str]:
        return [action.tenant_id for action in self.actions]

    @property
    def requires_review(self) -> bool:
        return bool(self.blocked_tenants) or any(info.status == "review" for info in self.collections)


def identify_collection(collection_id, name, metadata, vectors) -> CollectionInfo:
    """Aceita marcador explicito ou o contrato completo dos vetores legados."""
    def result(status, reason, tenant=None):
        return CollectionInfo(str(collection_id), name, tenant, len(vectors), status, reason)

    metadata = metadata if isinstance(metadata, dict) else {}
    owner = metadata.get("managed_by")
    if not isinstance(name, str) or not name:
        return result("review" if owner == "echomind" else "foreign", "Colecao sem nome verificavel.")
    if owner and owner != "echomind":
        return result("foreign", "Proprietario declarado alheio ao EchoMind.")
    if not name.startswith("knowledge_") and owner != "echomind":
        return result("foreign", "Colecao fora do namespace gerenciado.")

    if owner == "echomind":
        tenant = metadata.get("tenant_id")
        if (
            not isinstance(tenant, str) or not tenant.strip()
            or type(metadata.get("schema_version")) is not int
            or metadata["schema_version"] != 1
            or name != _tenant_collection_name(tenant)
        ):
            return result("review", "Marcador de propriedade/tenant invalido ou nome incompativel.")
        if any(not isinstance(item, dict) or item.get("tenant_id") != tenant for _, item in vectors):
            return result("review", "Vetores conflitam com o tenant declarado na colecao.")
        return result("managed", "Marcador EchoMind e tenant original confirmados.", tenant)

    # Prefixo ou nome sanitizado isoladamente nunca provam identidade/propriedade.
    tenants = set()
    for vector_id, item in vectors:
        if not isinstance(item, dict):
            return result("review", "Vetor legado sem metadata verificavel.")
        tenant, source, source_id = (item.get(key) for key in ("tenant_id", "source_type", "source_id"))
        if (
            not isinstance(tenant, str) or not tenant.strip()
            or not isinstance(source_id, str) or not source_id.strip()
            # Eventos legados comprovam propriedade, mas nao sao reconstruidos.
            or not isinstance(source, str) or source not in {"faq", "document_chunk", "event"}
            or vector_id != _make_vector_id(source_id, source, tenant)
            or name != _tenant_collection_name(tenant)
        ):
            return result("review", "Contrato/ID deterministico legado nao comprova propriedade e tenant.")
        tenants.add(tenant)
    if len(tenants) != 1:
        return result("review", "Colecao sem tenant original unico e comprovado.")
    return result("managed", "Tenant e propriedade comprovados pelo contrato legado completo.", tenants.pop())


def read_collection_inventory(db: Session, *, name: str | None = None) -> list[CollectionInfo]:
    # A suite rapida usa SQLite sem tabelas internas LangChain. A operacao real
    # continua exigindo PostgreSQL em validate_configuration().
    if db.get_bind().dialect.name != "postgresql":
        return []
    inspector = inspect(db.connection())
    if not inspector.has_table("langchain_pg_collection", schema="public"):
        return []
    if not inspector.has_table("langchain_pg_embedding", schema="public"):
        raise RuntimeError("Inventario LangChain incompleto; nenhuma limpeza autorizada.")
    rows = db.execute(text("""
        SELECT c.uuid, c.name, c.cmetadata AS collection_metadata,
               e.uuid AS embedding_id, e.custom_id, e.cmetadata AS vector_metadata
        FROM public.langchain_pg_collection c
        LEFT JOIN public.langchain_pg_embedding e ON e.collection_id = c.uuid
    """ + (" WHERE c.name = :name" if name is not None else "") + " ORDER BY c.name, c.uuid"),
        {"name": name} if name is not None else {},
    ).mappings()
    collections = {}
    for row in rows:
        entry = collections.setdefault(row["uuid"], (row["name"], row["collection_metadata"], []))
        if row["embedding_id"] is not None:
            entry[2].append((row["custom_id"], row["vector_metadata"]))
    inventory = [identify_collection(identifier, *entry) for identifier, entry in collections.items()]
    names = Counter(info.name for info in inventory)
    return [
        replace(info, status="review", tenant_id=None, reason="Nome de colecao duplicado; identidade ambigua.")
        if names[info.name] > 1 and isinstance(info.name, str) and info.name.startswith("knowledge_") else info
        for info in inventory
    ]


class TenantReindexError(RuntimeError):
    """Identifica o tenant que falhou e os ja concluidos nesta execucao."""

    def __init__(self, tenant_id: str, completed_tenant_ids: tuple[str, ...]):
        self.tenant_id = tenant_id
        self.completed_tenant_ids = completed_tenant_ids
        completed = ", ".join(completed_tenant_ids) if completed_tenant_ids else "nenhum"
        super().__init__(
            f"Falha ao reindexar tenant {tenant_id!r}; "
            f"tenants concluidos antes da falha: {completed}. "
            "A colecao que falhou pode estar vazia ou parcial; corrija a causa "
            "e gere uma nova previa antes de repetir."
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


def _list_source_tenant_ids(db: Session) -> list[str]:
    """Seleciona tenants com FAQ ou documento ready para reindexar."""
    faq_rows = (
        db.query(Faq.tenant_id)
        .filter(Faq.tenant_id.isnot(None), Faq.tenant_id != "")
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
    return sorted({row[0] for row in (*faq_rows, *document_rows)})


def list_tenant_ids(db: Session, *, collections=None) -> list[str]:
    """Inclui tenants comprovados mesmo quando so restam vetores orfaos."""
    inventory = read_collection_inventory(db) if collections is None else collections
    return sorted(set(_list_source_tenant_ids(db)) | {
        info.tenant_id for info in inventory if info.status == "managed"
    })


def build_reindex_plan(db: Session) -> ReindexPlan:
    inventory = read_collection_inventory(db)
    tenants = list_tenant_ids(db, collections=inventory)
    actions, blocked = [], []
    for tenant in tenants:
        name = _tenant_collection_name(tenant)
        matches = [info for info in inventory if info.name == name]
        collision = sum(_tenant_collection_name(other) == name for other in tenants) > 1
        if collision or (matches and (
            len(matches) != 1 or matches[0].status != "managed" or matches[0].tenant_id != tenant
        )):
            blocked.append(tenant)
            continue
        info = matches[0] if matches else None
        actions.append(ReindexAction(tenant, name, info.collection_id if info else None, info.vector_count if info else 0))
    return ReindexPlan(tuple(actions), tuple(inventory), tuple(blocked))


def preview_reindex_plan(plan: ReindexPlan) -> None:
    for action in plan.actions:
        log.info(
            "PREVIA tenant=%r colecao=%r uuid=%s: remover %d vetor(es) e reconstruir FAQs/chunks ready.",
            action.tenant_id, action.collection_name, action.collection_id or "nova", action.vector_count,
        )
    for info in plan.collections:
        if info.status != "managed":
            log.warning(
                "%s colecao=%r uuid=%s vetores=%d: %s Nenhuma limpeza autorizada.",
                "REVISAO OPERACIONAL" if info.status == "review" else "PRESERVAR ALHEIA",
                info.name, info.collection_id, info.vector_count, info.reason,
            )
    for tenant in plan.blocked_tenants:
        log.warning("REVISAO OPERACIONAL tenant=%r: identidade/colecao conflitante; nenhuma limpeza autorizada.", tenant)


def validate_tenant_collection(db, tenant_id, *, expected_id=None, check_snapshot=False):
    name = _tenant_collection_name(tenant_id)
    if any(other != tenant_id and _tenant_collection_name(other) == name for other in _list_source_tenant_ids(db)):
        raise RuntimeError("Colisao de nomes entre tenants; requer revisao operacional.")
    matches = read_collection_inventory(db, name=name)
    if matches and (len(matches) != 1 or matches[0].status != "managed" or matches[0].tenant_id != tenant_id):
        raise RuntimeError("Propriedade/tenant da colecao nao comprovados; nenhuma limpeza autorizada.")
    if check_snapshot and (matches[0].collection_id if matches else None) != expected_id:
        raise RuntimeError("Colecao mudou desde a previa; gere um novo plano antes da limpeza.")


def reindex_tenant(db: Session, tenant_id: str) -> ReindexResult:
    """Reconstrói uma colecao com fontes persistidas e prontas do tenant."""
    faqs = (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id)
        .order_by(Faq.id.asc())
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

    # Revalida a identidade atual antes de qualquer criacao/limpeza vetorial.
    validate_tenant_collection(db, tenant_id)
    # Valida a configuracao do RAG antes da limpeza destrutiva da colecao.
    rag = get_rag_indexer(db, tenant_id=tenant_id)
    clear_tenant_collection(tenant_id)

    for faq in faqs:
        rag.index_faq(faq)
    for chunk in chunks:
        rag.index_document_chunk(documents_by_id[chunk.document_id], chunk)

    return ReindexResult(
        tenant_id=tenant_id,
        faq_count=len(faqs),
        document_count=len(documents),
        document_chunk_count=len(chunks),
    )


def reindex_all(db: Session, *, plan: ReindexPlan | None = None) -> list[ReindexResult]:
    plan = plan or build_reindex_plan(db)
    preview_reindex_plan(plan)
    results: list[ReindexResult] = []
    for action in plan.actions:
        tenant_id = action.tenant_id
        log.info("Reindexando tenant %s...", tenant_id)
        try:
            validate_tenant_collection(db, tenant_id, expected_id=action.collection_id, check_snapshot=True)
            result = reindex_tenant(db, tenant_id)
            results.append(result)
            log.info(
                "Tenant %s concluido: %d FAQ(s), %d documento(s) ready, %d chunk(s).",
                tenant_id,
                result.faq_count,
                result.document_count,
                result.document_chunk_count,
            )
        except Exception as exc:
            db.rollback()
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


def _rewrite_parent_child_tenant(
    db: Session,
    tenant_id: str,
    *,
    rollback: bool = False,
) -> int:
    """Regrava parents/vinculos de um tenant sem trocar IDs de chunks."""
    documents = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.READY.value,
        )
        .order_by(Document.id.asc())
        .all()
    )
    rewritten = 0
    for document in documents:
        chunks = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.tenant_id == document.tenant_id,
                DocumentChunk.document_id == document.id,
            )
            .order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
            .all()
        )
        parent_count = (
            db.query(DocumentChunkParent)
            .filter(
                DocumentChunkParent.tenant_id == document.tenant_id,
                DocumentChunkParent.document_id == document.id,
            )
            .count()
        )
        if not chunks or (rollback and parent_count == 0):
            continue
        if not rollback and parent_count and all(chunk.parent_id for chunk in chunks):
            continue

        if rollback:
            parent_data: list[DocumentParentData] = []
            chunk_parent_indexes: list[int | None] = [None] * len(chunks)
        else:
            grouped = group_document_children(
                tuple(
                    ChunkedTextBlock(
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        section_title=chunk.section_title,
                    )
                    for chunk in chunks
                )
            )
            chunk_parent_indexes = [chunk.parent_index for chunk in grouped.children]
            parent_data = [
                DocumentParentData(
                    content=parent.content,
                    page_start=parent.page_start,
                    page_end=parent.page_end,
                    section_title=parent.section_title,
                )
                for parent in grouped.parents
            ]
        replace_document_parent_links(
            db,
            tenant_id=document.tenant_id,
            document_id=document.id,
            parents=parent_data,
            chunk_parent_indexes=chunk_parent_indexes,
        )
        rewritten += 1
    return rewritten


def rewrite_parent_child(
    db: Session,
    *,
    rollback: bool = False,
    tenant_id: str | None = None,
) -> int:
    """Backfill relacional retomavel por tenant, preservando IDs vetoriais."""
    tenant_ids = [tenant_id] if tenant_id is not None else list_tenant_ids(db)
    rewritten = 0
    for selected_tenant_id in tenant_ids:
        try:
            rewritten += _rewrite_parent_child_tenant(
                db,
                selected_tenant_id,
                rollback=rollback,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.expunge_all()
    return rewritten


def rewrite_parent_child_and_reindex(
    db: Session,
    *,
    rollback: bool = False,
    tenant_ids: list[str] | None = None,
) -> tuple[int, list[ReindexResult]]:
    """Confirma e reconcilia cada tenant antes de avancar ao proximo."""
    rewritten = 0
    results: list[ReindexResult] = []
    for tenant_id in tenant_ids if tenant_ids is not None else build_reindex_plan(db).tenant_ids:
        log.info(
            "%s Parent-Child do tenant %s...",
            "Revertendo" if rollback else "Aplicando",
            tenant_id,
        )
        try:
            rewritten += _rewrite_parent_child_tenant(
                db,
                tenant_id,
                rollback=rollback,
            )
            # O estado relacional do tenant funciona como checkpoint. Como os
            # IDs dos chunks nao mudam, uma interrupcao aqui mantem os vetores
            # antigos validos e uma nova execucao pode reconcilia-los.
            db.commit()
            results.append(reindex_tenant(db, tenant_id))
        except Exception as exc:
            db.rollback()
            completed_tenant_ids = tuple(result.tenant_id for result in results)
            log.exception(
                "Tenant %s falhou; Parent-Child interrompido apos: %s.",
                tenant_id,
                ", ".join(completed_tenant_ids) or "nenhum tenant",
            )
            raise TenantReindexError(tenant_id, completed_tenant_ids) from exc
        finally:
            db.expunge_all()
    return rewritten, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Limpa e reindexa colecoes RAG de FAQs e chunks ready por tenant."
        )
    )
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma conscientemente a limpeza das colecoes antes da reindexacao.",
    )
    execution.add_argument(
        "--dry-run", action="store_true",
        help="Mostra a previa e as colecoes pendentes de revisao, sem alterar banco ou vetores.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--parent-child-backfill",
        action="store_true",
        help="Cria parents para chunks ready legados antes da reindexacao.",
    )
    mode.add_argument(
        "--parent-child-rollback",
        action="store_true",
        help="Remove vinculos/parents e volta aos chunks planos antes da reindexacao.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    args = parse_args()
    dry_run = getattr(args, "dry_run", False)
    if not args.confirm and not dry_run:
        raise SystemExit(
            "Reindexacao nao executada. Use --confirm para autorizar a limpeza "
            "das colecoes RAG por tenant, ou --dry-run para visualizar a previa."
        )

    try:
        validate_configuration()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    db = SessionLocal()
    try:
        plan = build_reindex_plan(db)
        backfill = getattr(args, "parent_child_backfill", False)
        rollback = getattr(args, "parent_child_rollback", False)
        if dry_run or backfill or rollback:
            preview_reindex_plan(plan)
        if backfill or rollback:
            log.info(
                "PREVIA Parent-Child: %s somente nos documentos ready dos tenants selecionados.",
                "remover parents/vinculos" if rollback else "reescrever parents/vinculos legados",
            )
        if dry_run:
            if plan.requires_review:
                raise SystemExit(2)
            return
        if backfill or rollback:
            rewritten, results = rewrite_parent_child_and_reindex(
                db,
                rollback=rollback,
                tenant_ids=plan.tenant_ids,
            )
            log.info(
                "%d documento(s) regravado(s) no modo %s.",
                rewritten,
                "rollback" if rollback else "backfill",
            )
        else:
            results = reindex_all(db, plan=plan)
    except Exception:
        log.exception("Reindexacao interrompida com erro visivel.")
        raise SystemExit(1)
    finally:
        db.close()

    total_faqs = sum(result.faq_count for result in results)
    total_documents = sum(result.document_count for result in results)
    total_document_chunks = sum(result.document_chunk_count for result in results)
    log.info(
        "Reindexacao concluida: %d tenant(s), %d FAQ(s), %d documento(s) ready, %d chunk(s).",
        len(results),
        total_faqs,
        total_documents,
        total_document_chunks,
    )
    if plan.requires_review:
        log.warning("Concluidas apenas as acoes comprovadas; existem casos de revisao operacional preservados.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
