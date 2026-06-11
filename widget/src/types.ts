// Shared widget types. No `any` permitted anywhere in this bundle.

export interface HCChatConfig {
  apiBase: string;
  isPro: boolean;
  customerId: string | null;
  customerName: string | null;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

declare global {
  interface Window {
    HC_CHAT?: HCChatConfig;
  }
}
