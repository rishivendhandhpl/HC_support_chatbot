// Streaming chat client. POSTs to {apiBase}/chat and parses the SSE-style
// stream, invoking onToken for each delta. Uses fetch + ReadableStream so we
// can send a POST body (EventSource only supports GET).

import type { HCChatConfig } from "./types";

interface StreamHandlers {
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
  // Called when the request is cancelled via the AbortSignal (Stop button).
  onAbort?: () => void;
}

function isAbort(err: unknown, signal?: AbortSignal): boolean {
  return (
    signal?.aborted === true ||
    (err instanceof DOMException && err.name === "AbortError")
  );
}

export async function streamChat(
  config: HCChatConfig,
  message: string,
  sessionId: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${config.apiBase}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        is_pro: config.isPro,
        customer_id: config.customerId,
      }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Chat request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line (\n\n or \r\n\r\n).
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const result = parseFrame(frame);
        if (result.done) {
          handlers.onDone();
          return;
        }
        if (result.data) {
          handlers.onToken(result.data.replace(/\\n/g, "\n"));
        }
      }
    }
    handlers.onDone();
  } catch (err) {
    if (isAbort(err, signal)) {
      handlers.onAbort?.();
      return;
    }
    handlers.onError(err instanceof Error ? err : new Error(String(err)));
  }
}

interface ParsedFrame {
  data: string | null;
  done: boolean;
}

function parseFrame(frame: string): ParsedFrame {
  let event: string | null = null;
  const dataParts: string[] = [];
  for (const rawLine of frame.split(/\r?\n/)) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataParts.push(line.slice(5).replace(/^ /, ""));
    }
  }
  const data = dataParts.join("\n");
  if (event === "done" || data === "[DONE]") {
    return { data: null, done: true };
  }
  return { data: data || null, done: false };
}
