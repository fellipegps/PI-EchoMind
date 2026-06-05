"""
EchoMind AI Totem - Backend Principal
FastAPI + LangChain + Groq + pgvector
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio
import logging
import os

from .database import engine, Base, get_db, AdminUser
from .middleware import TimingMiddleware, RequestLogMiddleware, latency_store
from .schemas import (
    ChatRequest,
    FaqCreate, FaqUpdate, FaqResponse,
    EventCreate, EventUpdate, EventResponse,
    ConfigUpdate, ConfigResponse,
    UnansweredQuestionResponse, ConvertToFaqRequest,
    DashboardResponse, FeedbackRequest, FeedbackResponse,
    TokenResponse, AdminUserResponse,
)
from . import crud
from .auth import get_current_user
from .rag_engine import (
    get_rag_engine,
    _register_unanswered_standalone,
    warm_up_rag_runtime,
)
from .supabase_client import supabase
from .voice_service import synthesize as tts_synthesize

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echomind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando EchoMind Backend...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tabelas sincronizadas com o banco de dados.")
    warmup_timeout = float(os.getenv("RAG_WARMUP_TIMEOUT_SECONDS", "30"))
    try:
        await asyncio.wait_for(
            asyncio.to_thread(warm_up_rag_runtime),
            timeout=warmup_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[RAG] Warm-up excedeu %.0fs; o backend continuara subindo.",
            warmup_timeout,
        )
    except Exception as exc:
        logger.warning("[RAG] Warm-up falhou; o backend continuara subindo: %s", exc)
    yield

# ─── App & CORS ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="EchoMind AI Totem API",
    description="Backend para o sistema de Totem de IA com RAG sobre pgvector",
    version="1.0.0",
    lifespan=lifespan,
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

router_auth = APIRouter(prefix="/auth", tags=["Autenticação"])
router_chat = APIRouter(prefix="/chat", tags=["Chat"])
router_faqs = APIRouter(prefix="/faqs", tags=["Base de Conhecimento"])
router_events = APIRouter(prefix="/events", tags=["Base de Conhecimento"])
router_config = APIRouter(prefix="/config", tags=["Configurações"])
router_unanswered = APIRouter(prefix="/unanswered", tags=["Não Respondidas"])
router_dashboard = APIRouter(prefix="/dashboard", tags=["Dashboard"])
router_tts = APIRouter(prefix="/tts", tags=["Voz"])
router_feedback = APIRouter(prefix="/feedback", tags=["Feedback"])
router_system = APIRouter(tags=["Sistema"])


def get_rag(db: Session = Depends(get_db)) -> object:
    return get_rag_engine(db)


class AuthCredentials(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH  /auth
# ══════════════════════════════════════════════════════════════════════════════

@router_auth.post("/login", response_model=TokenResponse)
def login(payload: AuthCredentials):
    """Autentica via Supabase Auth e retorna o access_token emitido pelo Supabase."""
    try:
        response = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    access_token = getattr(session, "access_token", None)
    email = getattr(user, "email", None) or payload.email
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("[AUTH] Login bem-sucedido: %s", email)
    return TokenResponse(access_token=access_token, token_type="bearer", email=email)


@router_auth.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: AuthCredentials):
    try:
        response = supabase.auth.admin.create_user(
            {
                "email": payload.email,
                "password": payload.password,
                "email_confirm": True,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    user = getattr(response, "user", None)
    return {"email": getattr(user, "email", None) or payload.email}


@router_auth.post("/reset-password")
def reset_password(payload: PasswordResetRequest):
    try:
        supabase.auth.reset_password_email(payload.email)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Email enviado"}


@router_auth.get("/me", response_model=AdminUserResponse)
def get_me(current_user: AdminUser = Depends(get_current_user)):
    """Retorna os dados do usuário autenticado. Útil para validar token no frontend."""
    return current_user


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT  /chat  (núcleo do sistema)
# ══════════════════════════════════════════════════════════════════════════════

@router_chat.post(
    "",
    summary="Chat com streaming da IA via RAG",
)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")

    cached = crud.find_cached_faq_answer(question)
    if cached:
        faq_id, cached_answer = cached
        crud.increment_faq_consult(db, faq_id)

        async def cached_stream_generator():
            for char in cached_answer:
                yield char
            crud.save_interaction(db, question=question, answer=cached_answer)

        return StreamingResponse(cached_stream_generator(), media_type="text/plain")

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
            logger.error("[CHAT] Erro durante streaming: %s", exc, exc_info=True)
        finally:
            # Persiste a interação (sempre)
            crud.save_interaction(db, question=question, answer=full_response)

            # Se o RAG não encontrou documentos relevantes, registra a pergunta
            # como não respondida. Feito aqui com await run_in_executor — garante
            # execução no event loop correto, ainda dentro do ciclo de vida do
            # request, evitando o problema de create_task() que disparava após
            # o context do request ser destruído.
            if not rag.last_had_docs:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, _register_unanswered_standalone, question
                    )
                except Exception as exc:
                    logger.error("[CHAT] Falha ao registrar pergunta não respondida: %s", exc)

    return StreamingResponse(stream_generator(), media_type="text/plain")


# ══════════════════════════════════════════════════════════════════════════════
#  FAQs  /faqs
# ══════════════════════════════════════════════════════════════════════════════

@router_faqs.get("", response_model=list[FaqResponse])
def list_faqs(db: Session = Depends(get_db)):
    return crud.get_faqs(db)


@router_faqs.get("/totem", response_model=list[FaqResponse])
def list_totem_faqs(db: Session = Depends(get_db)):
    """Retorna apenas as FAQs marcadas para exibição no totem (máx. 4)."""
    return crud.get_totem_faqs(db)


@router_faqs.post("", response_model=FaqResponse, status_code=201)
def create_faq(
    payload: FaqCreate,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    faq = crud.create_faq(db, payload)
    rag.index_faq(faq)
    return faq


@router_faqs.put("/{faq_id}", response_model=FaqResponse)
def update_faq(
    faq_id: str,
    payload: FaqUpdate,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    faq = crud.update_faq(db, faq_id, payload)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    rag.reindex_faq(faq)
    return faq


@router_faqs.patch("/{faq_id}/toggle-totem", response_model=FaqResponse)
def toggle_totem(
    faq_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    """Ativa ou desativa a exibição da FAQ no totem (limite: 4 FAQs ativas)."""
    faq = crud.toggle_faq_totem(db, faq_id)
    if faq is None:
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    if faq == "limit_exceeded":
        raise HTTPException(status_code=409, detail="Limite máximo de 4 FAQs no totem atingido.")
    return faq


@router_faqs.delete("/{faq_id}", status_code=204)
def delete_faq(
    faq_id: str,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    if not crud.delete_faq(db, faq_id):
        raise HTTPException(status_code=404, detail="FAQ não encontrada.")
    rag.delete_document(faq_id, source="faq")


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS  /events
# ══════════════════════════════════════════════════════════════════════════════

@router_events.get("", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)):
    return crud.get_events(db)


@router_events.post("", response_model=EventResponse, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    event = crud.create_event(db, payload)
    rag.index_event(event)
    return event


@router_events.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    event = crud.update_event(db, event_id, payload)
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    rag.reindex_event(event)
    return event


@router_events.delete("/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    if not crud.delete_event(db, event_id):
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    rag.delete_document(event_id, source="event")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES  /config
# ══════════════════════════════════════════════════════════════════════════════

@router_config.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)):
    config = crud.get_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada. Crie uma primeiro.")
    return config


@router_config.put("", response_model=ConfigResponse)
def update_config(
    payload: ConfigUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    return crud.upsert_config(db, payload)


# ══════════════════════════════════════════════════════════════════════════════
#  NÃO RESPONDIDAS  /unanswered
# ══════════════════════════════════════════════════════════════════════════════

@router_unanswered.get("", response_model=list[UnansweredQuestionResponse])
def list_unanswered(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    return crud.get_unanswered_questions(db)


@router_unanswered.delete("/{question_id}", status_code=204)
def delete_unanswered(
    question_id: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    """Remove permanentemente uma pergunta da lista de pendentes sem convertê-la."""
    if not crud.delete_unanswered_question(db, question_id):
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")


@router_unanswered.post("/{question_id}/convert", response_model=FaqResponse, status_code=201)
def convert_to_faq(
    question_id: str,
    payload: ConvertToFaqRequest,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    """Converte uma pergunta não respondida em FAQ oficial e a indexa no RAG."""
    faq = crud.convert_unanswered_to_faq(db, question_id, payload.answer, payload.question)
    if not faq:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
    rag.index_faq(faq)
    return faq


@router_unanswered.post("/{question_id}/learn", status_code=204)
def learn_from_unanswered(
    question_id: str,
    payload: ConvertToFaqRequest,
    db: Session = Depends(get_db),
    rag = Depends(get_rag),
    _: AdminUser = Depends(get_current_user),
):
    """
    Fluxo de curadoria (Human-in-the-loop):
      1. Gera embedding do par (pergunta + resposta manual).
      2. Persiste o vetor no pgvector, expandindo a base de conhecimento.
      3. Remove a pergunta da lista de pendentes.
    """
    uq = crud.get_unanswered_by_id(db, question_id)
    if not uq:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")

    rag.learn_from_curation(
        question=uq["canonical_question"],
        answer=payload.answer,
        source_id=question_id,
    )
    crud.delete_unanswered_question(db, question_id)
    logger.info("[LEARN] Curadoria aplicada para question_id=%s", question_id)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD  /dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router_dashboard.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_user),
):
    stats = crud.get_dashboard_stats(db)
    real_avg = latency_store.summary()["avg_response_time"]
    stats["avg_response_time"] = real_avg
    return stats



# ══════════════════════════════════════════════════════════════════════════════
#  FEEDBACK  /feedback
# ══════════════════════════════════════════════════════════════════════════════

@router_feedback.post("", response_model=FeedbackResponse, status_code=201)
def save_response_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """Registra avaliação simples do usuário sobre a resposta do totem."""
    crud.save_feedback(
        db,
        question=payload.question.strip(),
        answer=payload.answer.strip(),
        helpful=payload.helpful,
    )
    return FeedbackResponse(saved=True, helpful=payload.helpful)

# ══════════════════════════════════════════════════════════════════════════════
#  TTS  /tts
# ══════════════════════════════════════════════════════════════════════════════

@router_tts.get(
    "",
    summary="Síntese de voz via Microsoft Edge TTS",
    response_class=Response,
)
async def tts(
    texto: str = Query(..., min_length=1, max_length=1500, description="Texto a ser sintetizado"),
    genero: str = Query("feminina", description="Gênero da voz: 'feminina' ou 'masculina'"),
):
    """
    Recebe um texto e retorna o áudio MP3 sintetizado usando Microsoft Edge TTS.

    - **texto**: texto a ser lido (máximo 1500 caracteres)
    - **genero**: `feminina` → pt-BR-FranciscaNeural | `masculina` → pt-BR-AntonioNeural
    """
    if genero not in ("feminina", "masculina"):
        raise HTTPException(status_code=400, detail="genero deve ser 'feminina' ou 'masculina'.")

    try:
        audio_bytes = await tts_synthesize(text=texto, gender=genero)
    except RuntimeError as exc:
        logger.error("[TTS] %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            # Sem cache — cada texto gera áudio novo
            "Cache-Control": "no-store",
            "Content-Length": str(len(audio_bytes)),
        },
    )


# ─── Health Check ─────────────────────────────────────────────────────────────

@router_system.get("/health")
def health():
    return {"status": "ok", "service": "EchoMind API"}


@router_system.get("/metrics")
def metrics():
    """Métricas internas de latência — útil para monitoramento."""
    return latency_store.summary()


app.include_router(router_auth)
app.include_router(router_chat)
app.include_router(router_faqs)
app.include_router(router_events)
app.include_router(router_config)
app.include_router(router_unanswered)
app.include_router(router_dashboard)
app.include_router(router_feedback)
app.include_router(router_tts)
app.include_router(router_system)
