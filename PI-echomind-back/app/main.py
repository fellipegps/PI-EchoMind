"""
EchoMind AI Totem - Backend Principal
FastAPI + LangChain + Groq + pgvector
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging

from .database import engine, Base, get_db
from .middleware import TimingMiddleware, RequestLogMiddleware, latency_store
from .schemas import (
    ChatRequest,
    FaqCreate, FaqUpdate, FaqResponse,
    EventCreate, EventUpdate, EventResponse,
    ConfigUpdate, ConfigResponse,
    UnansweredQuestionResponse, ConvertToFaqRequest,
    DashboardResponse,
)
from . import crud
from .rag_engine import get_rag_engine

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echomind")

# ─── App & CORS ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="EchoMind AI Totem API",
    description="Backend para o sistema de Totem de IA com RAG sobre pgvector",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Em produção, restrinja ao domínio do front
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares próprios (ordem importa: último registrado = primeiro executado)
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestLogMiddleware)

# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Cria tabelas e inicializa o engine de RAG."""
    logger.info("🚀 Iniciando EchoMind Backend...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tabelas sincronizadas com o banco de dados.")


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT  /chat  (núcleo do sistema)
# ══════════════════════════════════════════════════════════════════════════════

@app.post(
    "/chat",
    summary="Chat com streaming da IA via RAG",
    tags=["Chat"],
)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    # Inicializa o RAGEngine ANTES de abrir o stream.
    # Erros de configuração (GROQ_API_KEY ausente, etc.) geram HTTP 503
    # limpo que o frontend trata corretamente via onError.
    try:
        rag = get_rag_engine(db)
    except Exception as exc:
        logger.error("[CHAT] Falha ao inicializar RAGEngine: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    async def stream_generator():
        full_response = ""
        try:
            async for token in rag.astream_chat(question):
                if not token:
                    continue
                full_response += token
                yield token
        except Exception as exc:
            # CRÍTICO: NÃO fazer yield de texto de erro aqui.
            # O frontend interpreta qualquer yield como resposta da IA.
            # Apenas loga — o frontend detecta stream vazio via onDone()
            # e o agente/page.tsx já exibe a mensagem adequada.
            logger.error("[CHAT] Erro durante streaming: %s", exc, exc_info=True)
        finally:
            crud.save_interaction(db, question=question, answer=full_response)

    return StreamingResponse(stream_generator(), media_type="text/plain")


# ══════════════════════════════════════════════════════════════════════════════
#  FAQs  /faqs
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/faqs", response_model=list[FaqResponse], tags=["Base de Conhecimento"])
def list_faqs(db: Session = Depends(get_db)):
    return crud.get_faqs(db)


@app.get("/faqs/totem", response_model=list[FaqResponse], tags=["Base de Conhecimento"])
def list_totem_faqs(db: Session = Depends(get_db)):
    """Retorna apenas as FAQs marcadas para exibição no totem (máx. 4)."""
    return crud.get_totem_faqs(db)


@app.post("/faqs", response_model=FaqResponse, status_code=201, tags=["Base de Conhecimento"])
def create_faq(payload: FaqCreate, db: Session = Depends(get_db)):
    faq = crud.create_faq(db, payload)
    # Indexa no pgvector para RAG
    engine = get_rag_engine(db)
    engine.index_faq(faq)
    return faq


@app.put("/faqs/{faq_id}", response_model=FaqResponse, tags=["Base de Conhecimento"])
def update_faq(faq_id: str, payload: FaqUpdate, db: Session = Depends(get_db)):
    faq = crud.update_faq(db, faq_id, payload)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    engine = get_rag_engine(db)
    engine.reindex_faq(faq)
    return faq


@app.patch("/faqs/{faq_id}/toggle-totem", response_model=FaqResponse, tags=["Base de Conhecimento"])
def toggle_totem(faq_id: str, db: Session = Depends(get_db)):
    """Ativa ou desativa a exibição da FAQ no totem (limite: 4 FAQs ativas)."""
    faq = crud.toggle_faq_totem(db, faq_id)
    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    if faq == "limit_exceeded":
        raise HTTPException(status_code=409, detail="Limite máximo de 4 FAQs no totem atingido.")
    return faq


@app.delete("/faqs/{faq_id}", status_code=204, tags=["Base de Conhecimento"])
def delete_faq(faq_id: str, db: Session = Depends(get_db)):
    if not crud.delete_faq(db, faq_id):
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    engine = get_rag_engine(db)
    engine.delete_document(faq_id, source="faq")


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS  /events
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/events", response_model=list[EventResponse], tags=["Base de Conhecimento"])
def list_events(db: Session = Depends(get_db)):
    return crud.get_events(db)


@app.post("/events", response_model=EventResponse, status_code=201, tags=["Base de Conhecimento"])
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    event = crud.create_event(db, payload)
    engine = get_rag_engine(db)
    engine.index_event(event)
    return event


@app.put("/events/{event_id}", response_model=EventResponse, tags=["Base de Conhecimento"])
def update_event(event_id: str, payload: EventUpdate, db: Session = Depends(get_db)):
    event = crud.update_event(db, event_id, payload)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    engine = get_rag_engine(db)
    engine.reindex_event(event)
    return event


@app.delete("/events/{event_id}", status_code=204, tags=["Base de Conhecimento"])
def delete_event(event_id: str, db: Session = Depends(get_db)):
    if not crud.delete_event(db, event_id):
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    engine = get_rag_engine(db)
    engine.delete_document(event_id, source="event")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES  /config
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/config", response_model=ConfigResponse, tags=["Configurações"])
def get_config(db: Session = Depends(get_db)):
    config = crud.get_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada. Crie uma primeiro.")
    return config


@app.put("/config", response_model=ConfigResponse, tags=["Configurações"])
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)):
    return crud.upsert_config(db, payload)


# ══════════════════════════════════════════════════════════════════════════════
#  NÃO RESPONDIDAS  /unanswered
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/unanswered", response_model=list[UnansweredQuestionResponse], tags=["Não Respondidas"])
def list_unanswered(db: Session = Depends(get_db)):
    return crud.get_unanswered_questions(db)


@app.post("/unanswered/{question_id}/convert", response_model=FaqResponse, status_code=201, tags=["Não Respondidas"])
def convert_to_faq(question_id: str, payload: ConvertToFaqRequest, db: Session = Depends(get_db)):
    """Converte uma pergunta não respondida em FAQ oficial e a indexa no RAG."""
    faq = crud.convert_unanswered_to_faq(db, question_id, payload.answer)
    if not faq:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
    engine = get_rag_engine(db)
    engine.index_faq(faq)
    return faq


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD  /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
def get_dashboard(db: Session = Depends(get_db)):
    stats = crud.get_dashboard_stats(db)
    # Substitui o tempo médio mockado pelo valor real do middleware
    real_avg = latency_store.summary()["avg_response_time"]
    stats["avg_response_time"] = real_avg
    return stats


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "service": "EchoMind API"}


@app.get("/metrics", tags=["Sistema"])
def metrics():
    """Métricas internas de latência — útil para monitoramento."""
    return latency_store.summary()
