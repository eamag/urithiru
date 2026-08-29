# Urithiru web

Astro + Svelte frontend for launching discovery jobs and inspecting live MCTS runs.

```bash
bun install
bun run dev
```

Without configuration, the app opens an interactive demo workspace backed by the
real Urithiru belief and tree concepts. To connect a deployed API, copy
`.env.example` to `.env` and set `PUBLIC_API_BASE_URL`.

The frontend expects:

- `GET /runs` → an array of `DiscoveryRun` objects, or `{ "runs": [...] }`
- `POST /runs` → a `DiscoveryRun`, or `{ "run": ... }`

`POST /runs` is multipart form data. Dataset files repeat under `data`, followed by
the text fields `title`, `metadata`, and `budget` (`fast`, `standard`, or `deep`).
While an API is configured, the dashboard refreshes run state every five seconds.

Production build:

```bash
bun run build
```
