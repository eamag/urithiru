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

## Not verified

Live agent authentication, Docker image execution, cloud IAM and deployment, Gemini
model access and a real end-to-end cloud discovery remain unverified. In particular
the two-container split changes the wall-clock and memory profile of a step, and that
has not been measured against a real deployment. See [local.md](local.md) and
[google.md](google.md) for the prerequisites and the separate live acceptance step.
