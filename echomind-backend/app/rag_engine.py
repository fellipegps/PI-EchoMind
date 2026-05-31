"""
rag_engine.py — Motor RAG do EchoMind
LangChain + ChatGroq (llama-3.3-70b-versatile) + pgvector

Arquitetura:
  • LLM via API Groq — latência de geração ~10× menor que modelos locais.
    O modelo llama-3.3-70b-versatile oferece alta performance e é o substituto
    oficial do llama-3.3-70b-specdec (descontinuado pela Groq).
  • Embeddings gerados localmente via FastEmbed — sem torch, sem DLLs do Windows,
    384 dims (compatível com pgvector).
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
from pathlib import Path
from typing import AsyncGenerator

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy.orm import Session

from .database import (
    DATABASE_URL,
    CompanyEvent,
    Config,
    Faq,
    SessionLocal,
    UnansweredQuestion,
    utc_now,
)

logger = logging.getLogger("echomind.rag")

# ─── Configuração via variáveis de ambiente ───────────────────────────────────

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")

EMBED_MODEL  = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Garante que o cache de modelos use um caminho valido em Windows, Linux e macOS.
_MODEL_CACHE = os.getenv(
    "HF_HOME",
    str(Path.home() / ".cache" / "echomind_models"),
)
os.environ.setdefault("HF_HOME", _MODEL_CACHE)
os.environ.setdefault("TRANSFORMERS_CACHE", _MODEL_CACHE)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _MODEL_CACHE)

# Threshold de DISTÂNCIA coseno (0 = idêntico, 2 = oposto).
# O modelo BAAI/bge-small-en-v1.5 gera vetores onde:
#   < 0.30 = muito similar (mesma pergunta reformulada)
#   0.30–0.45 = relacionado (contexto relevante)
#   > 0.45 = provavelmente não relacionado
# 0.70 (valor antigo) era tolerante demais — aprovava docs irrelevantes,
# fazendo o LLM sempre receber "contexto" e nunca registrar não respondidas.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))
TOP_K_DOCS           = int(os.getenv("TOP_K_DOCS", "3"))
RAG_WARMUP_ENABLED   = os.getenv("RAG_WARMUP_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}

# ─── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é o assistente de {company_name}. Responda SOMENTE com base nas INFORMAÇÕES abaixo.
Se a informação não estiver nas INFORMAÇÕES, responda: \
"Não tenho essa informação. Consulte {company_name} ou acesse {website}."
Não invente nada. Responda em Português do Brasil. Seja {tone}.

Data de hoje: {today}

INFORMAÇÕES OFICIAIS:
{context}

Com base EXCLUSIVAMENTE nas INFORMAÇÕES OFICIAIS acima, responda de forma concisa \
(máximo 3 parágrafos):
"""


# ─── Singletons ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embeddings() -> FastEmbedEmbeddings:
    """
    Embeddings locais via FastEmbed (fastembed), sem torch e sem DLLs do Windows.
    BAAI/bge-small-en-v1.5: 384 dims, compacto e rapido para CPU.
    """
    logger.info("[RAG] Carregando modelo de embeddings via FastEmbed: %s", EMBED_MODEL)
    try:
        return FastEmbedEmbeddings(model_name=EMBED_MODEL, cache_dir=_MODEL_CACHE)
    except Exception as exc:
        raise RuntimeError(
            "Falha ao carregar embeddings FastEmbed. Execute: pip install fastembed"
        ) from exc


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
        temperature=0.0,
        streaming=True,
        max_tokens=400,
    )


@lru_cache(maxsize=1)
def _get_vector_store() -> PGVector:
    """
    FIX Bug 3: singleton com @lru_cache garante que TODAS as operações
    (add_documents, similarity_search, delete) usam a mesma instância
    PGVector com a mesma conexão interna ao LangChain.

    Antes, _get_vector_store() era chamado sem cache em delete_document(),
    criando uma instância diferente da usada em _upsert_document(). Como o
    PGVector do LangChain rastreia documentos por UUID interno de sessão,
    a instância nova não conhecia os IDs inseridos pela instância antiga —
    tornando o delete sempre ineficaz.
    """
    logger.info("[RAG] Inicializando PGVector singleton...")
    return PGVector(
        connection_string=DATABASE_URL,
        embedding_function=_get_embeddings(),
        collection_name="knowledge_documents",
        use_jsonb=True,
        engine_args={
            "pool_pre_ping": True,
            "connect_args": {"sslmode": "require"},
        },
    )


def _make_vector_id(source_id: str, source_type: str) -> str:
    """
    FIX Bug 1 + Bug 2: gera um UUID v5 determinístico a partir de
    (source_id, source_type).

    UUID v5 = hash SHA-1 de um namespace + nome → mesmo input sempre
    produz o mesmo UUID. Isso é a chave de todo o fix:

    • _upsert_document() passa esse ID como `ids=[vector_id]` para o
      LangChain, que o usa como custom_id na tabela langchain_pg_embedding.

    • delete_document() recalcula o mesmo UUID e passa como `ids=[vector_id]`
      para vs.delete() — garantindo que o vetor correto é encontrado e
      deletado, independentemente de quando ou quantas vezes foi indexado.

    Antes, add_documents() sem `ids` gerava um UUID aleatório a cada
    chamada. delete() recebia filter={...} (assinatura errada do PGVector)
    e silenciava a exceção — nunca deletava nada.
    """
    import uuid
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace DNS padrão
    return str(uuid.uuid5(namespace, f"{source_type}:{source_id}"))


def warm_up_rag_runtime() -> None:
    """
    Carrega os singletons pesados do RAG antes da primeira interacao real.

    A funcao e intencionalmente tolerante a falhas: se um servico externo
    estiver indisponivel no startup, o backend continua subindo e o endpoint
    /chat preserva o tratamento de erro existente.
    """
    if not RAG_WARMUP_ENABLED:
        logger.info("[RAG] Warm-up desativado por RAG_WARMUP_ENABLED.")
        return

    if DATABASE_URL.startswith("sqlite"):
        logger.info("[RAG] Warm-up ignorado em banco SQLite/testes.")
        return

    started = time.monotonic()
    logger.info("[RAG] Iniciando warm-up do motor RAG...")

    try:
        _get_llm()
    except Exception as exc:
        logger.warning("[RAG] Warm-up do LLM falhou: %s", exc)

    try:
        embeddings = _get_embeddings()
        embeddings.embed_query("aquecimento do mecanismo de busca")
    except Exception as exc:
        logger.warning("[RAG] Warm-up dos embeddings falhou: %s", exc)

    try:
        vector_store = _get_vector_store()
        vector_store.similarity_search_with_score(
            "aquecimento do mecanismo de busca",
            k=1,
        )
    except Exception as exc:
        logger.warning("[RAG] Warm-up do pgvector falhou: %s", exc)

    elapsed = time.monotonic() - started
    logger.info("[RAG] Warm-up finalizado em %.2fs.", elapsed)


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
        self.db           = db
        self._llm         = _get_llm()
        self._config      = _load_config_cached(db)
        self.last_had_docs: bool = True  # atualizado por astream_chat; lido no main.py

    async def astream_chat(self, question: str) -> AsyncGenerator[str, None]:
        """
        Retorna tokens da resposta via streaming.
        Após o streaming, `self.last_had_docs` indica se a pergunta foi
        genuinamente respondida. O main.py usa esse flag no finally para
        registrar perguntas não respondidas.

        Dois casos disparam o registro:
        1. Nenhum documento passou o threshold de similaridade (sem contexto).
        2. O LLM recebeu documentos mas respondeu negativamente — significa
           que os docs eram irrelevantes (falsos positivos do retriever).
        """
        docs = await _retrieve_docs(question)

        if not docs:
            # Caso 1: retriever não encontrou nada relevante
            self.last_had_docs = False
            fallback = (
                f"Não tenho informações suficientes para responder a isso. "
                f"Por favor, consulte {self._config['company_name']} diretamente "
                f"ou acesse {self._config['website']}."
            )
            for char in fallback:
                yield char
            return

        # Caso 2: docs encontrados — mas o LLM pode ainda não saber responder
        # (docs eram irrelevantes / falsos positivos do retriever).
        # Acumulamos a resposta completa para verificar depois.
        context_text = "\n\n---\n\n".join(d.page_content for d in docs)
        from datetime import date as _date
        _months = ["","janeiro","fevereiro","março","abril","maio","junho",
                   "julho","agosto","setembro","outubro","novembro","dezembro"]
        _t = _date.today()
        today_str = f"{_t.day} de {_months[_t.month]} de {_t.year}"
        system_msg = (
            SYSTEM_PROMPT
            .replace("{company_name}", self._config["company_name"])
            .replace("{website}",      self._config["website"])
            .replace("{tone}",         self._config["tone"])
            .replace("{today}",        today_str)
            .replace("{context}",      context_text)
        )

        full_answer = ""
        async for chunk in self._llm.astream([
            SystemMessage(content=system_msg),
            HumanMessage(content=question),
        ]):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                full_answer += token
                yield token

        # Detecta se o LLM confessou não saber — mesmo com docs disponíveis
        _negative_markers = (
            "não tenho essa informação",
            "não tenho informações",
            "não possuo essa informação",
            "não encontrei informações",
        )
        answered = not any(m in full_answer.lower() for m in _negative_markers)
        self.last_had_docs = answered
        if not answered:
            logger.info(
                "[RAG] LLM respondeu negativamente mesmo com %d doc(s) — "
                "registrando como não respondida. Pergunta: '%.60s'",
                len(docs), question
            )

    def learn_from_curation(self, question: str, answer: str, source_id: str) -> None:
        """
        Fluxo Human-in-the-loop:
        Converte o par (pergunta + resposta manual do curador) em embedding
        e o persiste no pgvector como um novo documento de conhecimento.

        O texto indexado segue o mesmo padrão das FAQs para garantir
        consistência no retrieval:
          'Pergunta: <q>\\nResposta: <a>'

        source_type='curated' permite distinguir no futuro documentos
        originados de curadoria manual de FAQs e eventos.
        """
        content = f"Pergunta: {question}\nResposta: {answer}"
        self._upsert_document(
            source_id=source_id,
            source_type="curated",
            content=content,
        )
        logger.info("[RAG] Curadoria indexada: source_id=%s | pergunta='%.60s'", source_id, question)

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
        """
        FIX Bug 1 + Bug 2: deleta o vetor do pgvector usando o UUID
        determinístico gerado por _make_vector_id().

        Antes:
          • delete(filter={...}) — assinatura errada; PGVector.delete() aceita
            apenas ids=[...]. A exceção era silenciada pelo except, deixando
            vetores órfãos para sempre.

        Agora:
          • Recalcula o mesmo UUID v5 usado no momento da indexação.
          • Chama delete(ids=[vector_id]) com a assinatura correta.
          • Mesmo singleton (_get_vector_store()) = mesma instância que inseriu.
        """
        vector_id = _make_vector_id(source_id, source)
        try:
            _get_vector_store().delete(ids=[vector_id])
            logger.info("[RAG] Vetor deletado do pgvector: %s:%s (vector_id=%s)",
                        source, source_id, vector_id)
        except Exception as exc:
            logger.error("[RAG] Falha ao deletar vetor %s: %s", vector_id, exc)

    def _upsert_document(self, source_id: str, source_type: str, content: str) -> None:
        """
        FIX Bug 2: passa `ids=[vector_id]` determinístico para add_documents().

        Antes, add_documents() sem ids gerava um UUID aleatório a cada chamada.
        Isso tornava impossível deletar o vetor depois — não havia como saber
        qual UUID o LangChain havia gerado na inserção anterior.

        Agora, o mesmo _make_vector_id(source_id, source_type) é usado tanto
        aqui quanto em delete_document(), garantindo correspondência exata.
        Múltiplos upserts do mesmo documento sobrescrevem o mesmo ID —
        comportamento correto para re-indexação de FAQs editadas.
        """
        vector_id = _make_vector_id(source_id, source_type)
        try:
            _get_vector_store().add_documents(
                [Document(
                    page_content=content,
                    metadata={"source_id": source_id, "source_type": source_type},
                )],
                ids=[vector_id],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao indexar documento {source_type}:{source_id} no pgvector."
            ) from exc
        logger.info("[RAG] Indexado: %s:%s (vector_id=%s)", source_type, source_id, vector_id)

# ─── Registro standalone (background task) ───────────────────────────────────

def _register_unanswered_standalone(question: str) -> None:
    """
    Versão independente de _register_unanswered que cria e fecha sua própria
    Session do SQLAlchemy.

    Necessária porque asyncio.create_task() dispara a execução DEPOIS que o
    StreamingResponse do FastAPI termina — momento em que a Session injetada
    via Depends(get_db) já foi fechada. Usar self.db nesse ponto causaria
    erros silenciosos de 'Session already closed', impedindo o registro.
    """
    import difflib
    db = SessionLocal()
    try:
        existing = (
            db.query(UnansweredQuestion)
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
            best_match.last_asked = utc_now()
            logger.info("[RAG] Não respondida agrupada em '%s' (ratio=%.2f)",
                        best_match.canonical_question[:60], best_ratio)
        else:
            db.add(UnansweredQuestion(
                canonical_question=question,
                similar_questions="[]",
            ))
            logger.info("[RAG] Nova não respondida registrada: '%s'", question[:60])

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("[RAG] Erro ao salvar não respondida standalone: %s", exc)
    finally:
        db.close()


# ─── Factory ─────────────────────────────────────────────────────────────────

def get_rag_engine(db: Session) -> RAGEngine:
    return RAGEngine(db)
