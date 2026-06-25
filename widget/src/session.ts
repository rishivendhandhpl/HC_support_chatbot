// Session id persistence for conversation continuity within a browser tab.

const KEY = "hc_chat_session_id";

export function getSessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(KEY);
    if (existing) return existing;
    const id = generateId();
    window.sessionStorage.setItem(KEY, id);
    return id;
  } catch {
    // sessionStorage may be unavailable (private mode); fall back to ephemeral.
    return generateId();
  }
}

// Start a fresh conversation (e.g. when the demo Pro toggle flips) so history
// and Pro-gating from the previous mode don't carry over.
export function newSessionId(): string {
  const id = generateId();
  try {
    window.sessionStorage.setItem(KEY, id);
  } catch {
    // sessionStorage unavailable; the returned id is still used in-memory.
  }
  return id;
}

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `hc-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
