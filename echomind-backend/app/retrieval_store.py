"""Consulta elegivel sobre o schema do langchain-community 0.2.19 fixado no projeto."""

from datetime import date

from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .database import Document as StoredDocument, DocumentChunk, DocumentChunkParent


class RetrievalPGVector(PGVector):
    def similarity_search_ready_with_score(
        self, query: str, *, tenant_id: str, today: date, k: int,
    ) -> list[tuple[Document, float]]:
        """Filtra o estado relacional antes do ORDER BY/LIMIT, sem carregar todos os IDs.

        A API de filtro JSON do PGVector nao expressa EXISTS nas tabelas documentais.
        Este adaptador preserva seu binding, colecao e metrica de distancia. A busca
        original continua disponivel para manutencao/reindexacao de vetores residuais.
        O chamador ainda revalida as fontes depois da consulta por causa de corridas.
        """
        embedding = self.embedding_function.embed_query(query)
        row = self.EmbeddingStore
        metadata = row.cmetadata
        source_type = metadata["source_type"].astext
        source_id = metadata["source_id"].astext
        document_id = metadata["document_id"].astext
        is_parent = source_type == "document_parent"
        chunk_id = case(
            (is_parent, metadata["matched_child_id"].astext),
            else_=source_id,
        )
        ready_chunk = (
            select(DocumentChunk.id)
            .join(
                StoredDocument,
                and_(StoredDocument.id == DocumentChunk.document_id,
                     StoredDocument.tenant_id == DocumentChunk.tenant_id),
            )
            .outerjoin(
                DocumentChunkParent,
                and_(DocumentChunkParent.id == DocumentChunk.parent_id,
                     DocumentChunkParent.document_id == DocumentChunk.document_id,
                     DocumentChunkParent.tenant_id == DocumentChunk.tenant_id),
            )
            .where(
                DocumentChunk.id == chunk_id,
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
                StoredDocument.tenant_id == tenant_id,
                StoredDocument.status == "ready",
                or_(StoredDocument.valid_until.is_(None), StoredDocument.valid_until >= today),
                or_(source_type == "document_chunk", DocumentChunkParent.id == source_id),
            )
            .correlate(row)
            .exists()
        )
        is_document = source_type.in_(("document_chunk", "document_parent"))
        eligible_source = or_(
            and_(is_document, ready_chunk),
            # NULL source_type era uma fonte comum no caminho anterior.
            func.coalesce(source_type, "").notin_(("document_chunk", "document_parent", "event")),
        )
        with Session(self._bind) as session:
            collection = self.get_collection(session)
            if collection is None:
                raise ValueError("Collection not found")
            distance = self.distance_strategy(embedding).label("distance")
            results = (
                session.query(row, distance)
                .filter(
                    row.collection_id == collection.uuid,
                    metadata["tenant_id"].astext == tenant_id,
                    eligible_source,
                )
                .order_by(distance.asc())
                .limit(k)
                .all()
            )
            return [
                (Document(page_content=item.document, metadata=item.cmetadata), float(score))
                for item, score in results
            ]
