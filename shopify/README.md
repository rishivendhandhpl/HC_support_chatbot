# Shopify Integration — H&C AI Stylist

Ships the widget as a **Theme App Extension** with an app-embed block.

## Layout

```
shopify/extensions/hc-chat-widget/
├── shopify.extension.toml
├── blocks/chat_widget.liquid      # app-embed block (target: body)
└── assets/hc-chat-widget.js       # copy widget/dist/hc-chat-widget.js here before deploy
```

## Deploy

1. Build the widget: `cd ../widget && npm run build`.
2. Copy `widget/dist/hc-chat-widget.js` → `shopify/extensions/hc-chat-widget/assets/`.
3. From the Shopify app project: `shopify app deploy`.
4. In the store admin: **Theme Editor → App embeds → H&C AI Stylist → enable**, then
   set the **Chat API base URL** to your deployed API.

## Pro gate (critical)

`isPro` comes from `{% if customer %}` in `blocks/chat_widget.liquid` — truthy
only when the visitor is logged in server-side. Do **not** replace this with a
client-side flag; the backend also re-checks `is_pro` and filters `pro_only`
knowledge chunks, but the Liquid value is the source of truth passed in.

## Quick test (Option B, no app)

Paste the `<script>` block from `chat_widget.liquid` before `</body>` in
`theme.liquid` and host `hc-chat-widget.js` somewhere reachable. Faster to try,
but a theme update/restore can wipe it — use the app-embed for production.
