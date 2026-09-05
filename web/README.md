# Urithiru web

A static Astro and Svelte site with two surfaces:

- `/` explains the Bayesian MCTS exploration engine and highlights reviewed,
  published evidence when any is bundled with the site.
- `/workspace` renders published runs, their search trees, four-stage belief chains,
  generated experiment evidence and retained event logs.

The site has no server API and cannot launch, resume or cancel a run. The CLI owns
those operations. `urithiru publish` copies a sanitized `mcts_state.json`,
`events.jsonl` and `run.json` into `public/runs/<id>/`; the static build includes those
files without exposing cloud credentials.

```sh
# Run from the repository root first.
uv run urithiru publish /absolute/path/runs/<run-id>

cd web
bun install --frozen-lockfile
bun run dev
```

A new clone contains no published runs and displays an empty state. Runs are selected
with `/workspace?run=<id>`, and individual nodes are addressable with
`&node=<node-id>`. Legacy `/?run=...` links redirect to the workspace.

Build the production site with:

```sh
bun test
bun run check
bun run build
bun run preview
```

Deploy the generated `dist/` directory to any static host. Set `PUBLIC_RUN_BASE` at
build time only when the published run files are served from a different public path;
the default is `/runs`.
