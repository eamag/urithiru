# Offline verification

Deterministic checks run without models, containers or cloud resources.

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

The stage-per-`HOME` change and the live log upload are both cloud-runtime behaviour and
are not covered here; see the live acceptance step in [google.md](google.md).

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
