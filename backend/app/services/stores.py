"""Storage backends: pgvector (Postgres) and a file-backed in-memory store.

Both expose the same interface so the rest of the app is backend-agnostic:
- replace_chunks(): idempotent re-index of the knowledge base
- search(): top-k nearest chunks with the SERVER-SIDE pro_only gate
- add_turn() / get_history(): conversation persistence

The store is selected by ``settings.store_backend`` and provided to routers via
the ``get_store`` FastAPI dependency.
"""
from __future__ import annotations

import logging
import pickle
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.conversation_turn import ConversationTurn
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.retrieval import Retrieved

logger = logging.getLogger(__name__)

_MAX_HISTORY_TURNS = 8


@dataclass
class ChunkRecord:
    """A knowledge chunk ready to be stored (embedding already computed)."""

    text: str
    section: str
    question: str
    pro_only: bool
    source_file: str
    embedding: list[float]


class Store(ABC):
    """Backend-agnostic storage interface."""

    @abstractmethod
    def replace_chunks(self, records: list[ChunkRecord]) -> None: ...

    @abstractmethod
    def search(self, query_vec: list[float], is_pro: bool, k: int) -> list[Retrieved]: ...

    @abstractmethod
    def add_turn(
        self, session_id: str, role: str, content: str, is_pro: bool, customer_id: str | None
    ) -> None: ...

    @abstractmethod
    def get_history(self, session_id: str) -> list[dict[str, str]]: ...


# --------------------------------------------------------------------------- #
# pgvector backend                                                            #
# --------------------------------------------------------------------------- #
class PgVectorStore(Store):
    """Postgres + pgvector backed store (production)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_chunks(self, records: list[ChunkRecord]) -> None:
        self.db.query(KnowledgeChunk).delete()
        self.db.add_all(
            [
                KnowledgeChunk(
                    embedding=r.embedding,
                    text=r.text,
                    section=r.section,
                    question=r.question,
                    pro_only=r.pro_only,
                    source_file=r.source_file,
                )
                for r in records
            ]
        )
        self.db.commit()

    def search(self, query_vec: list[float], is_pro: bool, k: int) -> list[Retrieved]:
        distance = KnowledgeChunk.embedding.cosine_distance(query_vec)
        stmt = select(KnowledgeChunk, distance.label("distance"))
        if not is_pro:
            stmt = stmt.where(KnowledgeChunk.pro_only.is_(False))
        stmt = stmt.order_by(distance).limit(k)
        return [
            Retrieved(c.section, c.question, c.text, c.pro_only, float(dist))
            for c, dist in self.db.execute(stmt).all()
        ]

    def add_turn(
        self, session_id: str, role: str, content: str, is_pro: bool, customer_id: str | None
    ) -> None:
        self.db.add(
            ConversationTurn(
                session_id=session_id,
                role=role,
                content=content,
                is_pro=is_pro,
                customer_id=customer_id,
            )
        )
        self.db.commit()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        stmt = (
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.id.desc())
            .limit(_MAX_HISTORY_TURNS)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]


# --------------------------------------------------------------------------- #
# in-memory / file-backed backend (Docker-free dev)                           #
# --------------------------------------------------------------------------- #
class MemoryStore(Store):
    """File-backed vector store. Chunks persist to disk; history is in-memory.

    Cosine similarity is computed with numpy. Intended for local dev where
    spinning up Postgres + pgvector is inconvenient.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: list[ChunkRecord] = []
        self._matrix: np.ndarray | None = None  # normalized embeddings (N, dim)
        self._history: dict[str, list[dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            with self.path.open("rb") as fh:
                self._records = pickle.load(fh)
            self._rebuild_matrix()
            logger.info("MemoryStore loaded %d chunks from %s", len(self._records), self.path)

    def _persist(self) -> None:
        with self.path.open("wb") as fh:
            pickle.dump(self._records, fh)

    def _rebuild_matrix(self) -> None:
        if not self._records:
            self._matrix = None
            return
        mat = np.array([r.embedding for r in self._records], dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
        self._matrix = mat / norms

    def replace_chunks(self, records: list[ChunkRecord]) -> None:
        self._records = list(records)
        self._rebuild_matrix()
        self._persist()
        logger.info("MemoryStore stored %d chunks to %s", len(records), self.path)

    def search(self, query_vec: list[float], is_pro: bool, k: int) -> list[Retrieved]:
        if self._matrix is None or not self._records:
            return []
        q = np.array(query_vec, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-9)
        sims = self._matrix @ q  # cosine similarity (vectors are normalized)
        order = np.argsort(-sims)
        out: list[Retrieved] = []
        for idx in order:
            rec = self._records[idx]
            if not is_pro and rec.pro_only:
                continue  # SERVER-SIDE GATE
            out.append(
                Retrieved(rec.section, rec.question, rec.text, rec.pro_only, float(1 - sims[idx]))
            )
            if len(out) >= k:
                break
        return out

    def add_turn(
        self, session_id: str, role: str, content: str, is_pro: bool, customer_id: str | None
    ) -> None:
        self._history.setdefault(session_id, []).append({"role": role, "content": content})

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return self._history.get(session_id, [])[-_MAX_HISTORY_TURNS:]


@lru_cache
def get_memory_store() -> MemoryStore:
    """Cached singleton memory store."""
    return MemoryStore(Path(get_settings().vector_store_path))


def get_store() -> Iterator[Store]:
    """FastAPI dependency yielding the configured store.

    In ``memory`` mode no database connection is opened.
    """
    settings = get_settings()
    if settings.store_backend == "memory":
        yield get_memory_store()
        return
    db = SessionLocal()
    try:
        yield PgVectorStore(db)
    finally:
        db.close()
