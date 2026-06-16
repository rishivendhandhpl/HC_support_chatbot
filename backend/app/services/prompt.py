"""Prompt assembly — the real server-side Pro gate."""
from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.services.retrieval import Retrieved

logger = logging.getLogger(__name__)

_PRO_ACCESS = (
    "USER STATUS: PRO (logged-in, paid). You may share pricing guidance, "
    "order/account/return deep-links, and checkout help."
)
_ANON_ACCESS = (
    "USER STATUS: ANONYMOUS (not logged in). Do NOT share pricing, quotes, or "
    "deep account/order links. If asked, explain pricing is for approved Pro "
    "members only and point them to the NEW ACCOUNT application "
    "(https://www.haircompounds.com/pages/create-an-account). General info links are allowed."
)

_GROUNDING = (
    "Answer ONLY from the system instruction and the KNOWLEDGE BASE CONTEXT below. "
    "Never invent policies, prices, links, or stock. If the answer is not covered, "
    "say you'll connect them and point to 818-922-8586 or orders@haircompounds.com."
)


@lru_cache
def load_system_instruction() -> str:
    """Load HC_SYSTEM_INSTRUCTION.md as the system message (cached)."""
    settings = get_settings()
    path = Path(settings.system_instruction_path)
    if not path.exists():
        logger.warning("System instruction file missing: %s", path)
        return "You are the Hair & Compounds (H&C) AI Virtual Stylist & Support Specialist."
    return path.read_text(encoding="utf-8")


def build_user_content(
    message: str, chunks: list[Retrieved], is_pro: bool, now_pst: datetime
) -> str:
    """Assemble the user-message payload: access directive + time + context + question."""
    access = _PRO_ACCESS if is_pro else _ANON_ACCESS
    context = "\n\n---\n\n".join(c.text for c in chunks) or "(no relevant context found)"
    pst_str = now_pst.strftime("%A %Y-%m-%d %I:%M %p %Z")
    return (
        f"{access}\n\n{_GROUNDING}\n\n"
        f"CURRENT PST TIME: {pst_str}\n"
        f"(Same-day ship cutoff is 1 PM PST, Mon-Fri.)\n\n"
        f"KNOWLEDGE BASE CONTEXT:\n{context}\n\n"
        f"USER QUESTION:\n{message}"
    )


def build_messages(
    message: str,
    chunks: list[Retrieved],
    is_pro: bool,
    now_pst: datetime,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build the full chat-completions message list."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": load_system_instruction()}
    ]
    if history:
        messages.extend(history)
    messages.append(
        {"role": "user", "content": build_user_content(message, chunks, is_pro, now_pst)}
    )
    return messages
