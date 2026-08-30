# Urithiru web

A static Astro + Svelte page that renders a discovery run: the search tree, the belief
chain behind each hypothesis, and the event log as it arrives.

There is no API and no server. `urithiru publish` copies the three files the page reads
— `mcts_state.json`, `events.jsonl` and a trimmed `run.json` — into `public/runs/<id>/`,
and the page renders the orchestrator's own output verbatim.

```bash
# a finished run, or --watch to keep a live one up to date
urithiru publish gs://your-bucket/urithiru/<run-id> --watch

bun install
bun run dev
```

`--watch` re-copies every five seconds until the run reports finishing, so the page
follows a live run at the same latency as `urithiru logs --follow`.

To read a run straight out of Cloud Storage instead, copy `.env.example` to `.env` and
point `PUBLIC_RUN_BASE` at a prefix the browser can fetch. That needs the objects to be
publicly readable and CORS-enabled on the bucket; the default keeps the bucket private.

Runs are chosen with `?run=<id>`, and the page polls every three seconds.

```bash
bun run check   # astro check
bun run build   # static output in dist/
```
