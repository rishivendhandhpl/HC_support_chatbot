# H&C AI Virtual Stylist

A production RAG (retrieval-augmented generation) support chatbot for
[Hair & Compounds](https://www.haircompounds.com). It answers customer questions
grounded in a curated knowledge base, gates Pro-only content behind verified
Shopify login, and streams responses into a framework-free storefront widget.

```
Storefront (Shopify Liquid app-embed)
   │  widget POSTs to /apps/hc-chat/chat   (same-origin)
   ▼
Shopify App Proxy ── signs request, appends logged_in_customer_id + signature
   ▼
FastAPI backend ── HMAC-verifies signature, derives is_pro server-side
   │  retrieve (pgvector, pro-gated) → build prompt → gpt-4o-mini (SSE stream)
   ▼
Postgres + pgvector            OpenAI
```

**Security model:** Pro status is never trusted from the browser. Shopify signs
proxied requests and reports the verified `logged_in_customer_id`; the backend
HMAC-verifies that signature and sets `is_pro` itself, so a client cannot forge
access to Pro-only knowledge.

## Stack

- **Backend:** FastAPI (Python 3.11), SQLAlchemy, Alembic, slowapi rate limiting
- **Retrieval:** OpenAI embeddings + pgvector (with a file-backed memory store for local dev)
- **LLM:** OpenAI `gpt-4o-mini`, streamed over Server-Sent Events
- **Widget:** TypeScript + Vite, no UI framework, embedded via a Shopify theme app extension
- **Infra:** Docker + docker-compose, GitHub Actions CI

## Repository layout

```
backend/    FastAPI app, services (retrieval, ingestion, chat), Alembic migrations, tests
widget/     TypeScript storefront chat widget (Vite build)
shopify/    Theme app extension (Liquid app-embed + bundled widget asset)
*.md        Knowledge base + system instruction + build/production docs
```

## Quick start (local, no database)

```bash
cp .env.example .env          # set OPENAI_API_KEY; leave STORE_BACKEND=memory
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# in another shell, index the knowledge base:
curl -X POST http://localhost:8000/ingest
```

Run the widget dev server:

```bash
cd widget && npm install && npm run dev
```

## Quick start (Docker, with Postgres + pgvector)

```bash
cp .env.example .env          # set OPENAI_API_KEY and a strong POSTGRES_PASSWORD
docker compose up --build
docker compose exec backend alembic upgrade head
curl -X POST http://localhost:8000/ingest
```

## Configuration

All settings come from environment variables (see `.env.example`). The backend
**fails fast at startup** if it is misconfigured — for example a missing
`OPENAI_API_KEY`, `REQUIRE_PROXY_SIGNATURE=true` with no `SHOPIFY_APP_SECRET`,
or a wildcard CORS origin combined with credentialed requests.

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI key (set a billing cap) |
| `STORE_BACKEND` | `pgvector` (production) or `memory` (local dev) |
| `DATABASE_URL` | Postgres connection (pgvector backend) |
| `ALLOWED_ORIGINS` | Comma-separated CORS allow-list |
| `RATE_LIMIT_PER_MIN` | Per-IP request limit |
| `REQUIRE_PROXY_SIGNATURE` | Enforce Shopify App Proxy verification (true in production) |
| `SHOPIFY_APP_SECRET` | Shopify app secret used to verify proxy signatures |
| `VITE_API_URL` | Widget API base (the App Proxy subpath in production) |

> Never commit a real `.env`. `.env`, `backend/.env`, and the local vector store
> are gitignored.

## Tests & linting

```bash
cd backend
ruff check app/
pytest
```

CI (`.github/workflows/ci.yml`) runs backend lint + tests and the widget
type-check + build on every push and pull request to `main`.

## Deployment

See [PRODUCTION.md](PRODUCTION.md) for the end-to-end production deployment
guide (secrets, managed Postgres with pgvector, the Shopify extension, and the
App Proxy wiring).
