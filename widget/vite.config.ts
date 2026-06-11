import { defineConfig } from "vite";
import { resolve } from "node:path";

// Build a single self-contained IIFE bundle that injects cleanly into the
// Shopify theme. CSS is inlined into the JS (cssCodeSplit: false) so only one
// asset — hc-chat-widget.js — needs to be hosted.
export default defineConfig({
  build: {
    cssCodeSplit: false,
    lib: {
      entry: resolve(__dirname, "src/main.ts"),
      name: "HCChat",
      formats: ["iife"],
      fileName: () => "hc-chat-widget.js",
    },
    rollupOptions: {
      output: {
        // Inline everything; no external runtime deps.
        inlineDynamicImports: true,
      },
    },
    minify: "esbuild",
  },
});
