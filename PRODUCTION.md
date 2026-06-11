# H&C AI Stylist — Production Deployment Guide

End-to-end guide to take the chatbot live on **https://www.haircompounds.com**.

```
Storefront (Liquid app-embed sets window.HC_CHAT)
   │  widget POSTs to  /apps/hc-chat/chat   (same-origin)
   ▼
Shopify App Proxy  ── signs request, appends logged_in_customer_id + signature
   ▼
Backend API (FastAPI)  ── verifies signature, derives is_pro server-side
   │  retrieve (pgvector, pro_only-gated) → prompt → gpt-4o-mini (stream)
   ▼
Postgres + pgvector            OpenAI
```

The security model: **Pro status is never trusted from the browser.** Shopify
signs proxied requests and tells the backend the verified `logged_in_customer_id`;
the backend HMAC-verifies that signature and sets `is_pro` itself.

---

## 0. Prerequisites

- A **Shopify Partner account** + a custom app installed on the haircompounds store.
- A host for the API with HTTPS (Render / Fly.io / Railway / a VPS).
- A **managed Postgres with the `pgvector` extension** (Render PG, Neon, Supabase, RDS…).
- An **OpenAI API key** with a billing cap set.
- Node 20+ and the **Shopify CLI** (`npm i -g @shopify/cli`) to deploy the extension.

---

## 1. Secrets & environment

Create the production `.env` (never commit it). See `.env.example`:

```env
OPENAI_API_KEY=sk-...                 # rotated, capped
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small

STORE_BACKEND=pgvector
DATABASE_URL=postgresql://USER:PASS@HOST:5432/hc_chatbot   # managed PG w/ pgvector

ALLOWED_ORIGINS=https://www.haircompounds.com
RATE_LIMIT_PER_MIN=20

REQUIRE_PROXY_SIGNATURE=true          # CRITICAL in production
SHOPIFY_APP_SECRET=shpss_...          # the app's client secret (step 4)
```

> `SHOPIFY_APP_SECRET` is the **client secret** of your Shopify app
> (Partners → your app → API credentials). It's what Shopify signs App Proxy
> requests with.

---

## 2. Database

Provision Postgres, then enable pgvector and run migrations:

```bash
# pgvector extension (most managed providers allow this; the migration also runs it)
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"

cd backend
alembic upgrade head      # creates knowledge_chunks + conversation_turns
```

---

## 3. Deploy the backend API

Build context is the repo root (so the KB markdown is baked into the image):

```bash
docker build -f backend/Dockerfile -t hc-backend .
```

Deploy that image to your host with the env vars from step 1. After it's up:

```bash
# one-time: seed the knowledge base into pgvector
curl -X POST https://api.YOUR-DOMAIN.com/ingest
# expect {"chunks_indexed":49,"pro_only_chunks":14}

curl https://api.YOUR-DOMAIN.com/health   # {"status":"ok"}
```

> Re-run `/ingest` whenever you edit `HC_FAQ.md` / `HC_SYSTEM_INSTRUCTION.md`
> (and rebuild/redeploy so the new files are in the image). Consider protecting
> `/ingest` behind an admin token or network rule before launch.

### Provider notes
- **Render/Railway:** point at the repo, set Dockerfile path `backend/Dockerfile`,
  add env vars, attach a Postgres add-on with pgvector.
- **Fly.io:** `fly launch` from repo root, `fly secrets set ...`, attach Fly Postgres.

---

## 4. Shopify app + App Proxy (the security layer)

In **Partners → your app → Configuration → App proxy**:

| Field | Value |
|-------|-------|
| Subpath prefix | `apps` |
| Subpath | `hc-chat` |
| Proxy URL | `https://api.YOUR-DOMAIN.com` |

This makes `https://www.haircompounds.com/apps/hc-chat/chat` forward to your
API's `/chat`, with Shopify appending `shop`, `logged_in_customer_id`,
`timestamp`, and `signature`. The backend verifies `signature` against
`SHOPIFY_APP_SECRET` and trusts `logged_in_customer_id` for Pro status.

> Same-origin bonus: because the widget calls `/apps/hc-chat/...` on the store's
> own domain, there are **no CORS issues** in production.

---

## 5. Build & deploy the widget

```bash
cd widget
npm ci
npm run build                        # → dist/hc-chat-widget.js (single IIFE)
cp dist/hc-chat-widget.js ../shopify/extensions/hc-chat-widget/assets/
```

Deploy the Theme App Extension:

```bash
cd ../shopify          # your Shopify app project root linked via `shopify app`
shopify app deploy
```

Then in the **store admin → Online Store → Themes → Customize → App embeds**:
1. Enable **H&C AI Stylist**.
2. Set **Chat API base URL** to `/apps/hc-chat` (the App Proxy subpath).
3. Save.

---

## 6. Pre-launch security checklist

- [ ] `REQUIRE_PROXY_SIGNATURE=true` and `SHOPIFY_APP_SECRET` set in prod.
- [ ] App Proxy URL points to the API; `api_base` in the embed is `/apps/hc-chat`.
- [ ] `ALLOWED_ORIGINS` = the live store only.
- [ ] `RATE_LIMIT_PER_MIN` tuned for real traffic.
- [ ] OpenAI key rotated, usage cap set, not committed anywhere.
- [ ] `/ingest` not publicly abusable (admin token / IP allowlist).
- [ ] All 9 outstanding KB links resolved to real URLs (see PRP "Links to Resolve").
- [ ] Logs contain only `customer_id` / `session_id`, never message PII.

---

## 7. QA on the live theme

| Scenario | Expected |
|----------|----------|
| Logged-out visitor asks for pricing | Refused + linked to NEW ACCOUNT |
| Logged-in (Pro) asks for pricing | Pricing/order guidance allowed |
| "When will my order ship?" near 1 PM PST | Correct same-day vs next-day answer |
| Out-of-scope question | Falls back to 818-922-8586 / orders@haircompounds.com |
| View page source / network tab | Cannot unlock pricing by editing the request |

---

## 8. Operations

- **Re-index KB:** edit the `.md` files → rebuild/redeploy backend → `POST /ingest`.
- **Costs:** `text-embedding-3-small` for ~49 chunks is negligible; `gpt-4o-mini`
  streaming per chat is cheap. Watch the OpenAI dashboard; the cap protects you.
- **Scaling:** the API is stateless except for the DB; run multiple replicas
  behind the host's load balancer. pgvector handles the retrieval.
- **Conversation history** persists in `conversation_turns` (last 8 turns replayed
  for continuity). Add a retention/cleanup job if volume grows.
- **Key rotation:** rotate `OPENAI_API_KEY` and `SHOPIFY_APP_SECRET` periodically;
  update env and restart.

---

## 9. Local dev vs production at a glance

| | Local dev | Production |
|--|-----------|------------|
| `STORE_BACKEND` | `memory` (file-backed) | `pgvector` |
| `REQUIRE_PROXY_SIGNATURE` | `false` (trust body) | `true` (Shopify-signed) |
| Widget `api_base` | `http://localhost:8000` | `/apps/hc-chat` |
| DB | none needed | managed Postgres + pgvector |
| Run | `uvicorn app.main:app` + `vite` | Docker image on HTTPS host |
