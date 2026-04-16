# ─── Estágio de Build ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Estágio de Runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia pacotes do estágio de build
COPY --from=builder /install /usr/local

# Copia o código da aplicação
COPY ./app ./app
COPY seed.py .

# ── Modelo de embeddings ──────────────────────────────────────────────────────
# Define um cache em /app/model_cache (dentro do WORKDIR, com permissão garantida).
# O modelo é baixado AQUI, ainda como root, e os arquivos ficam em /app/model_cache.
# Em runtime o appuser lê desse diretório sem precisar de escrita.
ENV HF_HOME=/app/model_cache
ENV TRANSFORMERS_CACHE=/app/model_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')" \
    && echo "Modelo de embeddings baixado com sucesso."

# ── Usuário não-root ──────────────────────────────────────────────────────────
# Criado DEPOIS do download do modelo, garantindo que appuser pode ler /app/model_cache
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "asyncio"]
