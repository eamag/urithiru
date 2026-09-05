import { defineConfig } from "astro/config";
import svelte from "@astrojs/svelte";

// This is a static site: a landing page and a read-only viewer over run JSON published
// under public/runs. Cloudflare Pages serves the dist/ directory as-is, so
// there is no adapter and no server to trust forwarded headers from.
export default defineConfig({
  integrations: [svelte()],
  output: "static",
  server: {
    host: "127.0.0.1",
    port: 4321,
  },
});
