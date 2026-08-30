# Offline verification

Deterministic checks run without models, containers or cloud resources.

## 2026-08-30 — where an agent writes, and what a published copy says

Three consecutive cloud runs failed at 1/3 with the same `FileNotFoundError`: a stage's
result file was absent from the workspace the engine reads. The agents' own logs said
where it went.

- **The agent resolves relative paths against `HOME`, not its working directory.** The
  literature agent for `search_node_000002` reported writing `p_search.json` "in the
  working directory" and linked it at `/tmp/urithiru-agent-*/search_node_000002/` — its
  private home — while its workspace was `/tmp/urithiru-cloud-*/sandbox_artifacts/
  search_node_000002/`. The launch script does `cd` into the workspace, so the shell's
  directory was right and the file tool's base was not. Every prompt then asserted
  "absolute paths are rejected", which steered it at the one form that lands in `HOME`.
  Naming the workspace absolutely in the launch prompt, and deleting that claim from all
  four goal prompts, is the fix; it is a correction to the instruction, not a workaround.
- **The fix holds.** Run `68943881` (seed 11) completed 3/3 with no `stage_failed` event
  of any kind: three proposal, three literature, three experiment and three external
  stages all passed on their first attempt. The three runs before it failed at 1/3.
- **A retry now gets a clean home.** `code_node_000001` failed its first attempt and its
  second ran a full 2m49s analysis and wrote `result.json` to the workspace. Before
  `reset` cleared the goal's home, a second attempt resumed the failed attempt's session
  state and returned in about 35 seconds having written nothing, so retries were never
  second chances. This is the cloud-runtime `HOME` behaviour the 2026-08-29 section
  listed as uncovered.

Budget growth, added so a finished run can be deepened rather than repeated:

- **The checkpoint guard admits growth and nothing else.** Loading a 3-step checkpoint
  with `steps=6` succeeds; with `steps=2` it raises, and with a different seed it raises.
- **`amend_budget` writes nothing when nothing changed**, refuses a lower step count, and
  rejects an invalid stage limit through the existing `Config` validation (`code_minutes
  = 0` → "Budget values must be positive").
- **The execution timeout follows the new budget**, 19,980s at 3 steps to 56,160s at 6.
- **Live:** run `68943881` was resumed from 3 steps to 30 and continued from its
  checkpoint, reusing all three completed evaluations rather than re-running them.

What a published copy is allowed to say, now that one is served publicly:

- **No published byte names the project or the bucket.** Every file `publish` writes is
  scanned for `gs://` and the bucket name; the event log, which carried the full run
  reference on every line, is rewritten to drop that one field and keeps every other
  field and every line; the index identifies a run by its id alone; the checkpoint is
  copied verbatim. Verified over the deployed service as well: its served HTML and
  JavaScript contain no project id, project number, bucket, `gs://`, or launch token, and
  the built client bundle references no environment variable at all.
- **`unpublish` removes only the copy.** The run's own files survive, other published
  runs and their index rows are untouched, and a reference whose last segment resolves to
  the published directory itself is refused — without that check a reference ending in
  `/.` would have deleted every published run, which is what the test was written to
  catch and did.
- **Launching is refused by default.** With no `URITHIRU_LAUNCH_TOKEN` the deployment
  answers 503 and reports `launchEnabled: false`; with one configured, an absent, wrong,
  truncated, over-long, unprefixed or `Basic`-prefixed credential is 401 and only the
  exact token passes; launches beyond the hourly allowance are 429. Confirmed against the
  live service, which returned 503 before a token was configured and 401 after.

Every command in the README's setup and verification sections was executed as written:
`uv run pytest` (54 passed), `ruff check`, `ruff format --check`, `pyright` (0 errors),
and in `web/`, `bun test` (17 passed) and `bun run check` (0 errors, 0 warnings, 0 hints).

## 2026-08-29 — the four-stage engine

The refactor described in [original-logic.md](original-logic.md#later-divergence-2026-08-29)
was exercised end to end against stub agents and a stub model: a `Sandbox` subclass
that writes exactly what each real agent would leave behind, and a model whose
embeddings are a hashed bag of words so textually similar claims really are nearby.
Two steps, five proposed claims including one exact and one near duplicate.

- **The literature agent never receives the data.** Its workspace contained
  `['goal.txt']`; the code agent's contained `['000_measurements.csv', 'goal.txt']`.
  This is the structural replacement for the old modification-time check.
- **The two agents run concurrently.** Both `stage_started` events precede either
  `stage_completed`, for both nodes in the batch.
- **Deduplication caught both kinds.** The whitespace variant was recorded
  `exact_duplicate` and the trailing-period variant `semantic_duplicate`, each with
  the claim it repeats, and one candidate per round was selected.
- **Records survive the JSON round trip.** `Evaluation.from_dict` reconstructed the
  prior, both beliefs, the external result and all six diagnostics; `r_ice_norm`
  stayed in [0, 1] and `external_value` stayed nonnegative.
- **The tree agrees with the checkpoint.** Root visits equalled completed
  evaluations equalled the requested steps.
- **Resume is free.** A second engine over the same directory returned both
  evaluations having made zero agent calls and zero prior, merge or embedding calls.
- **Export ranks and renders.** `report.json` is ordered by reward and `report.md`
  carries the verdict wording (`independent check: contradicted`).
- **The event log is durable and well formed.** 25 events, one JSON object per line,
  including `hypothesis_evaluated`.

Ruff and Pyright pass over the package. The wheel and source distribution build, and
the wheel carries all six prompt files.

## 2026-08-29 — the page, and the log it reads

- **The page's belief arithmetic matches the engine's.** `probTrue` in
  `web/src/lib/run.ts` was run over a completed cloud run's stored category counts and
  compared against `Belief.prob_true` for the same records: maximum absolute difference
  `1.1102230246251565e-16`, one unit in the last place from summation order. The page
  re-derives the four probabilities rather than being handed them, so this is the check
  that it derives them the same way.
- **`publish` copies only what the page reads.** A published run directory contains
  `mcts_state.json`, `events.jsonl` and `run.json`, and `run.json` contains the dataset,
  steps, seed, models and budget and no `options` block — so no project, bucket or
  service account name leaves the run.
- **The event log is mirrored per line, and a failed mirror cannot stop a run.** With a
  stub mirror bound, two emits produced two calls carrying one and then two lines. With a
  mirror that raises, `emit` still returned and the line was still on disk; the failure
  went to stderr, because reporting it through `emit` would recurse. With no mirror bound
  — the local runtime — emits still append.
- **The event log has one writer.** `events.jsonl` was removed from `CHECKPOINT_FILES`
  when `mirror_events` took over uploading it; sharing an object between a
  generation-precondition writer and an unconditional one would have failed the
  precondition and stopped the run as if a second orchestrator had appeared.
- **A published directory name cannot escape.** `publish` derives the directory from the
  tail of the run reference and passes it through `safe_path`, so
  `gs://bucket/prefix/..` is rejected rather than writing into the parent.
- Ruff, Ruff format and Pyright pass over the package; `astro check` passes over the
  page with 0 errors, 0 warnings and 0 hints.

The live log upload is cloud-runtime behaviour and is not covered here; see the live
acceptance step in [google.md](google.md). The stage-per-`HOME` change is covered by the
2026-08-30 section above.

## 2026-08-28 — the original port

- Compared all 15 belief diagnostics then exported, on 32 saved research evaluations:
  480 comparisons, maximum absolute difference `1.1102230246251565e-16` from the
  original calculations. Six of those diagnostics remain; the reward and the KLs
  behind it are unchanged.
- Compared three deduplication cases using actual saved embeddings and model-merge
  decisions: initial candidates, repeated candidates and an existing verified claim.
  Survivors and duplicate mappings matched the original implementation. That
  comparison covered the Ward-linkage implementation since replaced; the current
  similarity-gated equivalent is covered by the 2026-08-29 checks above.
- Cached evidence-retrieval ordering matched the original calculation.
- Staged a CSV, a two-sheet XLSX workbook and arbitrary JSON metadata; file hashes
  and workbook sheets were preserved.
- Restored an interrupted checkpoint containing a recorded complete evaluation.
- Installed the wheel in a clean Python 3.12 environment outside the repository;
  imports, CLI help and packaged prompt resources worked.

These are deterministic comparisons, not a claim that changed runtimes or prompt
packaging produce identical stochastic discovery trajectories.

## Live and remaining verification

The Google fallback path was exercised end to end on 2026-08-29: Cloud Run deployment,
agent ADC authentication, Gemini access, concurrent search/code execution, per-event
Cloud Storage mirroring and an independent external check all completed. The accepted
run and its timing are recorded in [google.md](google.md#live-acceptance-recorded-2026-08-29).

The local Docker image, Preview gVisor path, live cancellation/resume and negative IAM
checks remain unverified. Deterministic parity still does not establish identical
stochastic trajectories under changed prompts, models or runtimes.
