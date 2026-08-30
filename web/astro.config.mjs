import { defineConfig } from "astro/config";
import node from "@astrojs/node";
import svelte from "@astrojs/svelte";

export default defineConfig({
  adapter: node({ mode: "standalone" }),
  integrations: [svelte()],
  output: "server",
  server: {
    host: "127.0.0.1",
    port: 4321,
  },
});
