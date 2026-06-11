# H&C Chatbot — Build & Integration Guide

> How to build the Hair & Compounds AI Virtual Stylist and inject it as a chat widget into the Shopify store at **https://www.haircompounds.com/**.
>
> Companion files: [HC_SYSTEM_INSTRUCTION.md](HC_SYSTEM_INSTRUCTION.md) (persona + policy prompt) · [HC_FAQ.md](HC_FAQ.md) (knowledge base).

---

## 1. Overview

A floating chat widget embedded in the Shopify theme. The widget talks to a backend RAG service that answers using the H&C system prompt + FAQ knowledge base. The single most important business rule:

> **A logged-in Shopify customer = an approved Pro member = a paid user.**
> Only Pro users may see pricing, deep order/account links, and place-order guidance. Anonymous (logged-out) visitors get general info only.

```
Shopify storefront (haircompounds.com)
        │  app-embed snippet injects widget + passes customer state
        ▼
  Chat widget (JS, loaded on every page)
        │  POST /chat  { message, session_id, is_pro, customer_id }
        ▼
  Backend RAG API (FastAPI)
        │  retrieve top-k chunks from FAQ/Instruction vector store
        │  build prompt = system instruction + is_pro flag + retrieved context
        ▼
  OpenAI (gpt-4o-mini)  →  streamed answer back to widget
```

---

## 2. Tech Stack

- **Backend:** FastAPI + Python 3.11+
- **LLM:** OpenAI `gpt-4o-mini` via the OpenAI API (`openai` Python SDK)
- **Embeddings:** OpenAI `text-embedding-3-small` (1536-dim; cheap and strong for FAQ retrieval)
- **RAG:** embeddings + a vector store (pgvector on PostgreSQL, or a lightweight local FAISS/Chroma to start)
- **Widget:** vanilla TS/JS bundle (framework-free so it injects cleanly into any Shopify theme) — built with Vite, output as a single IIFE `.js`
- **Hosting:** API behind HTTPS (Render/Fly/Railway/your VPS); widget bundle on a CDN

> Keep the widget framework-free. A React/Chakra app is fine for an internal admin dashboard, but the injected storefront bundle must be small and not collide with the theme.

---

## 3. Shopify Injection

### Option A — App Embed Block (recommended)
Ship the widget as a **Shopify Theme App Extension** with an app-embed block. The merchant toggles it on once in **Theme Editor → App embeds**; it then loads on every page with no `theme.liquid` edits and survives theme updates.

`blocks/chat_widget.liquid`:
```liquid
{% comment %} H&C AI Stylist widget {% endcomment %}
<script>
  window.HC_CHAT = {
    apiBase: "{{ block.settings.api_base }}",
    isPro: {% if customer %}true{% else %}false{% endif %},
    customerId: {% if customer %}"{{ customer.id }}"{% else %}null{% endif %},
    customerName: {% if customer %}{{ customer.first_name | json }}{% else %}null{% endif %}
  };
</script>
<script src="{{ 'hc-chat-widget.js' | asset_url }}" defer></script>

{% schema %}
{
  "name": "H&C AI Stylist",
  "target": "body",
  "settings": [
    { "type": "text", "id": "api_base", "label": "Chat API base URL",
      "default": "https://api.your-domain.com" }
  ]
}
{% endschema %}
```

### Option B — Theme code snippet (fast, no app)
Paste the same `<script>` block before `</body>` in `theme.liquid` (or a snippet `{% render %}`'d there). Quicker, but it's a manual edit that a theme update/restore can wipe.

### The Pro signal comes from Liquid, not the browser
Shopify's `customer` object is only truthy server-side when the visitor is logged in. **Always derive `isPro` from `{% if customer %}` in Liquid** — never trust a client-side cookie/localStorage flag, which a visitor could forge to unlock pricing.

---

## 4. Pro vs. Anonymous Behavior

| Capability | Anonymous visitor | Logged-in (Pro) |
|---|---|---|
| General brand / product / texture info | ✅ | ✅ |
| FAQ answers (shipping, returns, curly care, etc.) | ✅ | ✅ |
| General info links (Production House, education) | ✅ | ✅ |
| **Pricing details / quotes** | ❌ → guide them to log in / apply | ✅ |
| **Deep account/order/return deep-links** | ❌ | ✅ |
| Place-order / checkout guidance | ❌ | ✅ |

When an anonymous user asks for anything Pro-gated, the bot should:
1. Explain pricing/ordering is for approved Pro members only.
2. Point to the **NEW ACCOUNT** application (general info link — safe to share).
3. Note that if they can already log in and see pricing, their access is active.

This must be enforced **server-side** in the prompt assembly (Section 6) — not just asked of the model politely. The `is_pro` flag is the gate.

---

## 5. Backend — RAG Pipeline

### 5.1 Ingestion (one-time / on content change)
1. Load [HC_SYSTEM_INSTRUCTION.md](HC_SYSTEM_INSTRUCTION.md) and [HC_FAQ.md](HC_FAQ.md).
2. Chunk the FAQ **per Q&A** (each `###` question + its answer = one chunk). This keeps retrieval clean — one question maps to one chunk. Keep the section heading as metadata.
3. Embed each chunk; store vector + text + metadata `{ section, question, pro_only }` in the vector store.
4. Mark pricing/order/account chunks `pro_only: true` so retrieval can filter them out for anonymous users if desired.

### 5.2 Retrieval + answer (`POST /chat`)
```
1. Receive { message, session_id, is_pro, customer_id }.
2. Embed `message`; retrieve top-k (k=4-5) chunks.
   - If not is_pro, drop chunks flagged pro_only from context.
3. Assemble prompt (Section 6).
4. Call OpenAI (gpt-4o-mini), stream tokens.
5. Persist turn to conversation history keyed by session_id.
6. Return streamed answer.
```

### 5.3 Endpoints
- `POST /chat` — main chat (streaming, SSE).
- `GET /health` — liveness.
- (optional) `POST /ingest` — re-index knowledge base after editing the `.md` files.

Use `logging` (never `print`). Secrets (`ANTHROPIC_API_KEY`, DB URL) via env vars only.

---

## 6. Prompt Assembly

Send the H&C system instruction as the `system` message, then inject the Pro flag and retrieved context as a `user` message. OpenAI chat-completions sketch:

```python
from openai import OpenAI
client = OpenAI()  # reads OPENAI_API_KEY

system = HC_SYSTEM_INSTRUCTION_MD  # full text of HC_SYSTEM_INSTRUCTION.md

access = (
    "USER STATUS: PRO (logged-in, paid). You may share pricing guidance, "
    "order/account/return deep-links, and checkout help."
    if is_pro else
    "USER STATUS: ANONYMOUS (not logged in). Do NOT share pricing, quotes, or "
    "deep account/order links. If asked, explain pricing is Pro-only and point "
    "them to the NEW ACCOUNT application. General info links are allowed."
)

context = "\n\n".join(retrieved_chunks)

messages = [
    {"role": "system", "content": system},
    # ...prior turns from this session_id here...
    {"role": "user", "content":
        f"{access}\n\nKNOWLEDGE BASE CONTEXT:\n{context}\n\n"
        f"CURRENT PST TIME: {now_pst}\n\nUSER QUESTION:\n{message}"}
]

stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    temperature=0.2,
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    # ...forward delta to the widget over SSE...
```

Notes:
- **Inject current PST time** every request so the bot can correctly answer "when will my order ship?" against the **1 PM PST** same-day cutoff.
- Keep `temperature` low (≈0.2) — this is policy support, accuracy over creativity.
- Instruct the model to answer **only** from the provided context + system instruction, and to never invent policies, prices, or links.

---

## 7. Widget Frontend (`hc-chat-widget.js`)

Behavior:
- Floating launcher bubble bottom-right; opens a chat panel.
- Reads config from `window.HC_CHAT` (set by the Liquid snippet).
- Generates/stores a `session_id` in `sessionStorage` for conversation continuity.
- Sends `{ message, session_id, is_pro: window.HC_CHAT.isPro, customer_id }` to `${apiBase}/chat`; renders streamed response.
- Greets Pro users by `customerName` when present.
- Renders markdown (bold, lists, links) so policy formatting from the answers displays cleanly.

Constraints (per project standards):
- TypeScript with explicit interfaces, **no `any`**.
- No `console.log` in the production bundle.
- Scoped CSS (prefix all classes, e.g. `.hc-chat-…`, or Shadow DOM) so it never clashes with the Shopify theme.

---

## 8. Security & Guardrails

- **Pricing gate is server-side.** The model is told the user's status, but retrieval also filters `pro_only` chunks for anonymous users — defense in depth.
- **Never trust client-sent `is_pro` blindly.** It originates from Liquid `{% if customer %}`; for stronger guarantees, verify the customer via Shopify (e.g., App Proxy signed requests or a customer-token check) before honoring Pro access on the API.
- **CORS:** allow only `https://www.haircompounds.com` (and any staging domain).
- **Rate limit** `/chat` per session/IP to control API cost and abuse.
- **No PII in logs.** Log `customer_id` and `session_id` at most; never message content with personal data in plaintext if avoidable.
- Bot must **refuse to invent** policies, prices, links, or stock — answer "let me connect you" / point to **818-922-8586** / **orders@haircompounds.com** when unsure.

---

## 9. Links to Resolve Before Launch

The knowledge base references link labels without URLs. Map these to real haircompounds.com URLs and have the bot emit real markdown links:

| Label in KB | Known / needed URL |
|---|---|
| NEW ACCOUNT | https://www.haircompounds.com/account/register |
| Return Form | https://www.haircompounds.com/pages/contact-hc |
| COLOR MATCHING FORM | _need URL_ |
| Color Chart | _need URL_ |
| Production House page | _need URL_ |
| New Stock / waitlist page | _need URL_ |
| Custom Order page | _need URL_ |
| Grey Blends / custom design options | _need URL_ |
| Store Policy | _need URL_ |
| Education / classes section | _need URL_ |
| Facebook group for extensionists | _need URL_ |

> Action: collect the remaining URLs, then add them into the prompt/KB so the bot links instead of printing bare label text.

---

## 10. Build Order (suggested)

1. Scaffold FastAPI backend + `/health`.
2. Ingestion script → embed & store the two `.md` files (chunk FAQ per Q&A).
3. `/chat` endpoint with retrieval + OpenAI call + streaming, honoring `is_pro`.
4. Inject current PST time + access rules into the prompt; test the ship-cutoff logic.
5. Build the widget bundle; wire `window.HC_CHAT` config.
6. Package as a Shopify Theme App Extension (app-embed block) — or paste the snippet for a quick first test.
7. Lock down CORS to haircompounds.com, add rate limiting, resolve links (Section 9).
8. QA: test as logged-out (no pricing) vs. logged-in (Pro) on the live theme.

---

## 11. Environment Variables

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
DATABASE_URL=postgresql://user:pass@localhost:5432/hc_chatbot
ALLOWED_ORIGINS=https://www.haircompounds.com
VITE_API_URL=https://api.your-domain.com
```
