from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db
from app.api.v1 import auth, faq, documents, voice, metrics, unanswered, events
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Usa o padrão moderno 'lifespan' do FastAPI (substitui o @app.on_event deprecated).
    Tudo antes do 'yield' roda no startup, tudo depois no shutdown.
    """
    await init_db()
    yield


app = FastAPI(
    title="EchoMind - Totem Universitário API",
    version="1.0.0",
    lifespan=lifespan
)

# Liberação de CORS para o Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Garante que a pasta static existe
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inclusão das Rotas
app.include_router(auth.router, prefix="/api/v1")
app.include_router(faq.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(unanswered.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "EchoMind API"}
