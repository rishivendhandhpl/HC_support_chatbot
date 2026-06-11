# H&C AI Stylist — Storefront Widget

Framework-free TypeScript chat widget, built by Vite into a single IIFE bundle
(`dist/hc-chat-widget.js`) that injects into the Hair & Compounds Shopify theme.

## Build

```bash
npm install
npm run build      # → dist/hc-chat-widget.js
npm run type-check # strict TS, no `any`
```

## How it loads

The Shopify app-embed block (`shopify/extensions/.../blocks/chat_widget.liquid`)
sets `window.HC_CHAT` and loads `hc-chat-widget.js`:

```js
window.HC_CHAT = {
  apiBase: "https://api.your-domain.com",
  isPro: true,            // from Liquid {% if customer %} — server-side only
  customerId: "123",
  customerName: "Jane"
};
```

The widget:
- shows a floating launcher (bottom-right) → opens a chat panel,
- keeps a `session_id` in `sessionStorage` for conversation continuity,
- POSTs `{ message, session_id, is_pro, customer_id }` to `${apiBase}/chat`,
- renders the SSE-streamed markdown answer,
- greets Pro users by `customerName`.

## Constraints

- TypeScript strict, **no `any`**.
- **No `console.log`** in shipped code.
- All CSS classes prefixed `.hc-chat-` so they never clash with the theme.
