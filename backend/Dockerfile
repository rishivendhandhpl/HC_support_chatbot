# syntax=docker/dockerfile:1
# Build context is the REPO ROOT (see docker-compose.yml) so the knowledge-base
# markdown files at the root can be copied into the image.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FAQ_PATH=/kb/HC_FAQ.md \
    SYSTEM_INSTRUCTION_PATH=/kb/HC_SYSTEM_INSTRUCTION.md \
    WIKI_DIR=/kb/companyWiki

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/

# Knowledge base lives outside /app so a dev source mount of /app won't hide it.
COPY HC_FAQ.md HC_SYSTEM_INSTRUCTION.md /kb/
COPY companyWiki/ /kb/companyWiki/

RUN useradd --create-home --uid 1001 appuser \
    && chown -R appuser:appuser /app /kb
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
