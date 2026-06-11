"""End-to-end smoke test against the live OpenAI API (no database required).

Exercises the real pipeline: parse KB -> embed (OpenAI) -> in-memory cosine
retrieval with the server-side pro_only gate -> prompt assembly -> streamed
gpt-4o-mini answer. Run from backend/:  python -m scripts.smoke_test
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.dependencies import get_openai_client, get_pst_now
from app.services.embeddings import embed_text, embed_texts
from app.services.ingestion import parse_files
from app.services.prompt import build_messages
from app.services.retrieval import Retrieved

REPO = Path(__file__).resolve().parents[2]


def in_memory_retrieve(query, chunks, vectors, is_pro, k=5):
    """Cosine retrieval over pre-computed vectors, applying the Pro gate."""
    qv = np.array(embed_text(query), dtype=np.float32)
    qn = qv / (np.linalg.norm(qv) + 1e-9)
    scored = []
    for chunk, vec in zip(chunks, vectors):
        if not is_pro and chunk.pro_only:
            continue  # SERVER-SIDE GATE: withhold pro_only from anonymous users
        v = np.array(vec, dtype=np.float32)
        sim = float(np.dot(qn, v / (np.linalg.norm(v) + 1e-9)))
        scored.append((sim, chunk))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [
        Retrieved(c.section, c.question, c.text, c.pro_only, 1 - sim)
        for sim, c in scored[:k]
    ]


def ask(client, model, query, chunks, vectors, is_pro):
    label = "PRO" if is_pro else "ANONYMOUS"
    retrieved = in_memory_retrieve(query, chunks, vectors, is_pro)
    print(f"\n{'='*70}\n[{label}] Q: {query}")
    print(f"  retrieved sections: {[r.section for r in retrieved]}")
    print(f"  any pro_only in context? {any(r.pro_only for r in retrieved)}")
    messages = build_messages(query, retrieved, is_pro=is_pro, now_pst=get_pst_now())
    stream = client.chat.completions.create(
        model=model, messages=messages, temperature=0.2, stream=True
    )
    print("  A: ", end="")
    for ch in stream:
        sys.stdout.write(ch.choices[0].delta.content or "")
        sys.stdout.flush()
    print()


def main() -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    client = get_openai_client()

    print("Parsing knowledge base...")
    chunks = parse_files(REPO / "HC_FAQ.md", REPO / "HC_SYSTEM_INSTRUCTION.md")
    pro_only = sum(c.pro_only for c in chunks)
    print(f"  parsed {len(chunks)} chunks ({pro_only} pro_only)")

    print("Embedding chunks via OpenAI (text-embedding-3-small)...")
    vectors = embed_texts([c.text for c in chunks])
    print(f"  got {len(vectors)} vectors, dim={len(vectors[0])}")

    model = settings.openai_model
    # 1) Anonymous asks for pricing -> must refuse + point to NEW ACCOUNT.
    ask(client, model, "What are your prices for curly hair?", chunks, vectors, is_pro=False)
    # 2) Pro asks for pricing -> allowed to guide.
    ask(client, model, "What are your prices for curly hair?", chunks, vectors, is_pro=True)
    # 3) Product knowledge (public) -> answered for anonymous.
    ask(client, model, "Do you sell straight hair?", chunks, vectors, is_pro=False)
    # 4) Shipping timing -> uses injected PST cutoff logic.
    ask(client, model, "If I order now, when will it ship?", chunks, vectors, is_pro=True)

    print(f"\n{'='*70}\nSMOKE TEST COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
