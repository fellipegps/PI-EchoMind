"""
rag_engine.py — Motor RAG do EchoMind
LangChain + ChatGroq (llama-3.3-70b-versatile) + pgvector

Arquitetura:
  • LLM via API Groq — latência de geração ~10× menor que modelos locais.
    O modelo llama-3.3-70b-versatile oferece alta performance e é o substituto
    oficial do llama-3.3-70b-specdec (descontinuado pela Groq).
  • Embeddings gerados localmente via sentence-transformers — sem servidor
    externo, sem container adicional, 768 dims (compatível com pgvector).
  • Singletons via @lru_cache para LLM, Embeddings e VectorStore.
  • Retrieval com threshold manual sobre distância coseno bruta do pgvector.
  • _register_unanswered em background task para não bloquear o stream.
  • Config da instituição em cache com TTL de 60s.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from functools import lru_cache
from typing import AsyncGenerator

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy.orm import Session

from .database import CompanyEvent, Config, Faq, KnowledgeDocument, UnansweredQuestion

logger = logging.getLogger("echomind.rag")

# ─── Configuração via variáveis de ambiente ───────────────────────────────────

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")

EMBED_MODEL  = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://echomind:echomind@db:5432/echomind")

# Garante que sentence-transformers lê o cache de /app/model_cache
# (mesmo local onde o Dockerfile baixou o modelo durante o build)
_MODEL_CACHE = os.getenv("HF_HOME", "/app/model_cache")
os.environ.setdefault("HF_HOME", _MODEL_CACHE)
os.environ.setdefault("TRANSFORMERS_CACHE", _MODEL_CACHE)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _MODEL_CACHE)

# Threshold de DISTÂNCIA coseno (0 = idêntico, 2 = oposto).
# 0.70 é tolerante para bancos em fase inicial.
# Diminua para 0.50 quando o banco estiver bem populado.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.70"))
TOP_K_DOCS           = int(os.getenv("TOP_K_DOCS", "3"))

# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é o assistente de {company_name}. Responda SOMENTE com base nas INFORMAÇÕES abaixo.
Se a informação não estiver nas INFORMAÇÕES, responda: \
"Não tenho essa informação. Consulte {company_name} ou acesse {website}."
Não invente nada. Responda em Português do Brasil. Seja {tone}.

INFORMAÇÕES OFICIAIS:
{context}

Com base EXCLUSIVAMENTE nas INFORMAÇÕES OFICIAIS acima, responda de forma concisa \
(máximo 3 parágrafos):
"""


# ─── Singletons ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embeddings() -> HuggingFaceEmbeddings:
    """
    Embeddings locais via sentence-transformers.
    O modelo é carregado uma vez e reutilizado em todos os requests.
    paraphrase-multilingual-mpnet-base-v2: 768 dims, excelente suporte ao PT-BR.
    """
    logger.info("[RAG] Carregando modelo de embeddings: %s", EMBED_MODEL)
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


@lru_cache(maxsize=1)
def _get_llm() -> ChatGroq:
    """
    ChatGroq otimizado para totem: temperature=0 (determinístico),
    max_tokens=400 (respostas concisas), streaming ativado.
    """
    logger.info("[RAG] Inicializando ChatGroq: %s", GROQ_LLM_MODEL)
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY não definida. "
            "Adicione a chave no arquivo .env antes de iniciar o backend."
        )
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_LLM_MODEL,
        temperature=0.0,    # determinístico — sem variação entre respostas
        streaming=True,     # tokens chegam ao frontend assim que gerados
        max_tokens=400,     # respostas concisas para totem (~3 parágrafos)
    )


@lru_cache(maxsize=1)
def _get_vector_store() -> PGVector:
    logger.info("[RAG] Inicializando PGVector...")
    return PGVector(
        connection_string=DATABASE_URL,
        embedding_function=_get_embeddings(),
        collection_name="knowledge_documents",
        use_jsonb=True,
    )


# ─── Cache de configuração (TTL 60s) ─────────────────────────────────────────

_config_cache: dict = {}
_config_cache_ts: float = 0.0
_CONFIG_TTL = 60.0


def _load_config_cached(db: Session) -> dict:
    """Lê config da instituição com cache de 60s — evita SELECT a cada request."""
    global _config_cache, _config_cache_ts
    now = time.monotonic()
    if _config_cache and (now - _config_cache_ts) < _CONFIG_TTL:
        return _config_cache

    cfg = db.query(Config).first()
    _config_cache = {
        "company_name": cfg.company_name if cfg else "nossa instituição",
        "website":      (cfg.website if cfg else None) or "o site da instituição",
        "tone":         cfg.tone_of_voice if cfg else "profissional e cordial",
    }
    _config_cache_ts = now
    return _config_cache


# ─── Retrieval com threshold manual ──────────────────────────────────────────

async def _retrieve_docs(question: str) -> list[Document]:
    """
    Busca os TOP_K_DOCS documentos mais próximos e filtra pela distância
    coseno bruta do pgvector — mais confiável que o score normalizado do
    LangChain, que pode vir fora de [0, 1] e descartar docs válidos.
    """
    vs   = _get_vector_store()
    loop = asyncio.get_running_loop()

    results: list[tuple[Document, float]] = await loop.run_in_executor(
        None,
        lambda: vs.similarity_search_with_score(question, k=TOP_K_DOCS),
    )

    approved = [(doc, dist) for doc, dist in results if dist <= SIMILARITY_THRESHOLD]
    approved.sort(key=lambda x: x[1])

    if approved:
        logger.info("[RAG] %d doc(s) aprovado(s). Distâncias: %s",
                    len(approved), [f"{d:.3f}" for _, d in approved])
    else:
        nearest = results[0][1] if results else -1
        logger.info("[RAG] Nenhum doc abaixo de %.2f. Menor distância: %.3f",
                    SIMILARITY_THRESHOLD, nearest)

    return [doc for doc, _ in approved]


# ─── RAGEngine ────────────────────────────────────────────────────────────────

class RAGEngine:

    def __init__(self, db: Session):
        self.db      = db
        self._llm    = _get_llm()
        self._config = _load_config_cached(db)

    async def astream_chat(self, question: str) -> AsyncGenerator[str, None]:
        """Retorna tokens da resposta via streaming."""
        docs = await _retrieve_docs(question)

        if not docs:
            async def _bg(q: str) -> None:
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._register_unanswered, q)
                except Exception as exc:
                    logger.warning("[RAG] Erro ao registrar não respondida: %s", exc)
            asyncio.create_task(_bg(question))

            fallback = (
                f"Não tenho informações suficientes para responder a isso. "
                f"Por favor, consulte {self._config['company_name']} diretamente "
                f"ou acesse {self._config['website']}."
            )
            for char in fallback:
                yield char
            return

        context_text = "\n\n---\n\n".join(d.page_content for d in docs)
        system_msg = (
            SYSTEM_PROMPT
            .replace("{company_name}", self._config["company_name"])
            .replace("{website}",      self._config["website"])
            .replace("{tone}",         self._config["tone"])
            .replace("{context}",      context_text)
        )

        async for chunk in self._llm.astream([
            SystemMessage(content=system_msg),
            HumanMessage(content=question),
        ]):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield token

    # ─── Indexação ───────────────────────────────────────────────────────────

    def index_faq(self, faq: Faq) -> None:
        self._upsert_document(
            source_id=faq.id,
            source_type="faq",
            content=f"Pergunta: {faq.question}\nResposta: {faq.answer}",
        )

    def reindex_faq(self, faq: Faq) -> None:
        self.delete_document(faq.id, "faq")
        self.index_faq(faq)

    def index_event(self, event: CompanyEvent) -> None:
        desc = f"\nDescrição: {event.description}" if event.description else ""
        self._upsert_document(
            source_id=event.id,
            source_type="event",
            content=(
                f"Evento: {event.title}\n"
                f"Data: {event.event_date}\n"
                f"Tipo: {event.event_type}"
                f"{desc}"
            ),
        )

    def reindex_event(self, event: CompanyEvent) -> None:
        self.delete_document(event.id, "event")
        self.index_event(event)

    def delete_document(self, source_id: str, source: str) -> None:
        self.db.query(KnowledgeDocument).filter(
            KnowledgeDocument.source_id == source_id,
            KnowledgeDocument.source_type == source,
        ).delete()
        self.db.commit()
        try:
            _get_vector_store().delete(
                filter={"source_id": source_id, "source_type": source}
            )
        except Exception as exc:
            logger.warning("[RAG] Falha ao deletar do vector store: %s", exc)

    def _upsert_document(self, source_id: str, source_type: str, content: str) -> None:
        _get_vector_store().add_documents([Document(
            page_content=content,
            metadata={"source_id": source_id, "source_type": source_type},
        )])
        logger.info("[RAG] Indexado: %s:%s", source_type, source_id)

    # ─── Perguntas não respondidas ────────────────────────────────────────────

    def _register_unanswered(self, question: str) -> None:
        """Agrupa perguntas sem resposta por similaridade textual."""
        import difflib
        from datetime import datetime
        try:
            existing = (
                self.db.query(UnansweredQuestion)
                .filter(UnansweredQuestion.converted == False)
                .order_by(UnansweredQuestion.last_asked.desc())
                .limit(100)
                .all()
            )

            best_match, best_ratio = None, 0.0
            for uq in existing:
                ratio = difflib.SequenceMatcher(
                    None, question.lower(), uq.canonical_question.lower()
                ).ratio()
                if ratio > best_ratio:
                    best_ratio, best_match = ratio, uq

            if best_match and best_ratio > 0.65:
                similar = json.loads(best_match.similar_questions or "[]")
                if question not in similar and question != best_match.canonical_question:
                    similar.append(question)
                best_match.similar_questions = json.dumps(similar, ensure_ascii=False)
                best_match.count += 1
                best_match.last_asked = datetime.utcnow()
            else:
                self.db.add(UnansweredQuestion(
                    canonical_question=question,
                    similar_questions="[]",
                ))

            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error("[RAG] Erro ao salvar não respondida: %s", exc)


# ─── Factory ─────────────────────────────────────────────────────────────────

def get_rag_engine(db: Session) -> RAGEngine:
    return RAGEngine(db)
