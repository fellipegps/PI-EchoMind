# syntax=docker/dockerfile:1
# Python 3.12, Debian Bookworm; update the digest deliberately when rebuilding.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/var/cache/echomind/models \
    DOCUMENT_STORAGE_DIR=/var/lib/echomind/documents \
    RATE_LIMIT_INSTANCE_COUNT=1 \
    UVICORN_WORKERS=1 \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY requirements-deploy.lock ./requirements-deploy.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-deploy.lock \
    && python -m pip check \
    && groupadd --gid 10001 echomind \
    && useradd --uid 10001 --gid 10001 --create-home echomind \
    && mkdir -p /var/cache/echomind/models /var/lib/echomind/documents \
    && chown -R echomind:echomind /var/cache/echomind /var/lib/echomind

# Explicit copies keep local configuration and uploaded data out of the image.
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts/reindex_all.py ./scripts/reindex_all.py
COPY scripts/check_database.py ./scripts/check_database.py

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

# Liveness only: this endpoint does not validate Supabase, Groq or embeddings.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).close()"]

# Trust proxy headers only after configuring the HTTPS proxy's exact address.
# Database migrations and RAG reindexing are separate, explicit operations.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--timeout-graceful-shutdown", "300"]
