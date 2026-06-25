// H&C AI Virtual Stylist — storefront widget entry point.
// Framework-free; builds to a single IIFE that injects into the Shopify theme.

import styles from "./styles.css?inline";
import { streamChat } from "./api";
import { renderMarkdown } from "./markdown";
import { getSessionId, newSessionId } from "./session";
import type { HCChatConfig } from "./types";

// Keep in sync with backend MAX_WORDS_PER_QUERY (schemas/chat.py).
const MAX_WORDS_PER_QUERY = 200;

// Animated "thinking" indicator shown until the first token streams in.
const THINKING_HTML =
  '<span class="hc-chat-typing" aria-label="Thinking">' +
  "<span></span><span></span><span></span></span>";

function readConfig(): HCChatConfig {
  const cfg = window.HC_CHAT;
  return {
    apiBase: cfg?.apiBase ?? "",
    isPro: cfg?.isPro ?? false,
    customerId: cfg?.customerId ?? null,
    customerName: cfg?.customerName ?? null,
  };
}

class ChatWidget {
  private readonly config: HCChatConfig;
  private sessionId: string;
  private isPro: boolean;
  private panel!: HTMLDivElement;
  private messages!: HTMLDivElement;
  private input!: HTMLTextAreaElement;
  private sendBtn!: HTMLButtonElement;
  private busy = false;
  private controller: AbortController | null = null;

  constructor(config: HCChatConfig) {
    this.config = config;
    this.sessionId = getSessionId();
    this.isPro = config.isPro;
  }

  // The config used for each request reflects the live demo toggle, not just
  // the initial window.HC_CHAT value.
  private requestConfig(): HCChatConfig {
    return {
      ...this.config,
      isPro: this.isPro,
      customerId: this.isPro ? (this.config.customerId ?? "demo-pro") : null,
    };
  }

  mount(): void {
    const root = document.createElement("div");
    root.className = "hc-chat-root";

    const launcher = document.createElement("button");
    launcher.className = "hc-chat-launcher";
    launcher.setAttribute("aria-label", "Open H&C Stylist chat");
    launcher.textContent = "💬";
    launcher.addEventListener("click", () => this.togglePanel());

    this.panel = this.buildPanel();
    root.appendChild(this.panel);
    root.appendChild(launcher);
    document.body.appendChild(root);

    this.greet();
  }

  private buildPanel(): HTMLDivElement {
    const panel = document.createElement("div");
    panel.className = "hc-chat-panel";

    const header = document.createElement("div");
    header.className = "hc-chat-header";
    const title = document.createElement("span");
    title.textContent = "H&C AI Stylist";
    const close = document.createElement("button");
    close.className = "hc-chat-close";
    close.setAttribute("aria-label", "Close chat");
    close.textContent = "×";
    close.addEventListener("click", () => this.togglePanel());
    header.append(title, close);

    // Demo control: flip between Pro (logged-in member) and standard access so
    // the Pro gating can be shown live. In production the Shopify theme sets the
    // real value via window.HC_CHAT.isPro.
    const demoBar = document.createElement("label");
    demoBar.className = "hc-chat-demo";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.className = "hc-chat-pro-toggle";
    toggle.checked = this.isPro;
    toggle.addEventListener("change", () => this.setProMode(toggle.checked));
    const demoLabel = document.createElement("span");
    demoLabel.textContent = "Pro mode (logged-in member) — demo";
    demoBar.append(toggle, demoLabel);

    this.messages = document.createElement("div");
    this.messages.className = "hc-chat-messages";

    const inputRow = document.createElement("div");
    inputRow.className = "hc-chat-input-row";
    this.input = document.createElement("textarea");
    this.input.className = "hc-chat-input";
    this.input.rows = 1;
    this.input.placeholder = "Ask about products, orders, shipping…";
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void this.send();
      }
    });
    this.sendBtn = document.createElement("button");
    this.sendBtn.className = "hc-chat-send";
    this.sendBtn.textContent = "Send";
    // While a response streams, this button becomes a Stop control.
    this.sendBtn.addEventListener("click", () => this.onSendClick());
    inputRow.append(this.input, this.sendBtn);

    panel.append(header, demoBar, this.messages, inputRow);
    return panel;
  }

  // Flip Pro/standard mode: start a clean conversation so the previous mode's
  // history and gated context don't leak across the switch, then re-greet.
  private setProMode(isPro: boolean): void {
    if (this.busy) return;
    this.isPro = isPro;
    this.sessionId = newSessionId();
    this.messages.innerHTML = "";
    this.greet();
  }

  private togglePanel(): void {
    this.panel.classList.toggle("hc-chat-open");
    if (this.panel.classList.contains("hc-chat-open")) {
      this.input.focus();
    }
  }

  private greet(): void {
    const name = this.config.customerName;
    const who = name ? ` ${name}` : "";
    const hello = this.isPro
      ? `Hi${who}! **Pro mode** is on. I can help with pricing, quotes, ordering and checkout, and account/order/return links — plus all product info.`
      : "Hi! I'm the H&C AI Stylist (**standard mode**). I can help with products, textures, hair science, shipping, and returns. Pricing, quotes, ordering, and account/order links are **Pro-only** — turn on Pro mode above to see them.";
    this.appendMessage("assistant", hello);
  }

  private appendMessage(role: "user" | "assistant", text: string): HTMLDivElement {
    const el = document.createElement("div");
    el.className = `hc-chat-msg ${role === "user" ? "hc-chat-user" : "hc-chat-bot"}`;
    if (role === "assistant") {
      el.innerHTML = renderMarkdown(text);
    } else {
      el.textContent = text;
    }
    this.messages.appendChild(el);
    this.messages.scrollTop = this.messages.scrollHeight;
    return el;
  }

  // The send button doubles as Stop while a response is streaming.
  private onSendClick(): void {
    if (this.busy) this.stop();
    else void this.send();
  }

  // Cancel the in-flight request; streamChat resolves via onAbort.
  private stop(): void {
    this.controller?.abort();
  }

  private async send(): Promise<void> {
    const text = this.input.value.trim();
    if (!text || this.busy) return;
    const wordCount = text.split(/\s+/).length;
    if (wordCount > MAX_WORDS_PER_QUERY) {
      this.appendMessage(
        "assistant",
        `Your message is ${wordCount} words. Please keep each question to ${MAX_WORDS_PER_QUERY} words or fewer and try again.`,
      );
      return;
    }
    if (!this.config.apiBase) {
      this.appendMessage("assistant", "Chat is not configured. Please try again later.");
      return;
    }

    this.setBusy(true);
    this.input.value = "";
    this.appendMessage("user", text);

    const botEl = this.appendMessage("assistant", "");
    botEl.classList.add("hc-chat-thinking");
    botEl.innerHTML = THINKING_HTML;
    let accumulated = "";

    this.controller = new AbortController();
    await streamChat(
      this.requestConfig(),
      text,
      this.sessionId,
      {
        onToken: (chunk) => {
          if (!accumulated) botEl.classList.remove("hc-chat-thinking");
          accumulated += chunk;
          botEl.innerHTML = renderMarkdown(accumulated);
          this.messages.scrollTop = this.messages.scrollHeight;
        },
        onDone: () => {
          if (!accumulated) botEl.textContent = "Sorry, I didn't catch that.";
          this.finish();
        },
        onError: () => {
          botEl.classList.remove("hc-chat-thinking");
          botEl.textContent =
            "Sorry, something went wrong. Please call 818-922-8586 or email orders@haircompounds.com.";
          this.finish();
        },
        onAbort: () => {
          botEl.classList.remove("hc-chat-thinking");
          if (accumulated) {
            botEl.innerHTML =
              renderMarkdown(accumulated) +
              '<span class="hc-chat-stopped">Stopped</span>';
          } else {
            botEl.textContent = "Stopped.";
          }
          this.finish();
        },
      },
      this.controller.signal,
    );
  }

  private setBusy(busy: boolean): void {
    this.busy = busy;
    this.sendBtn.textContent = busy ? "Stop" : "Send";
    this.sendBtn.classList.toggle("hc-chat-stop", busy);
    if (!busy) this.controller = null;
  }

  private finish(): void {
    this.setBusy(false);
    this.input.focus();
  }
}

function injectStyles(): void {
  if (document.getElementById("hc-chat-styles")) return;
  const style = document.createElement("style");
  style.id = "hc-chat-styles";
  style.textContent = styles;
  document.head.appendChild(style);
}

function init(): void {
  if (document.getElementById("hc-chat-mounted")) return;
  const marker = document.createElement("meta");
  marker.id = "hc-chat-mounted";
  document.head.appendChild(marker);
  injectStyles();
  new ChatWidget(readConfig()).mount();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
