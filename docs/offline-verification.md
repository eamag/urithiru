# Offline verification — 2026-08-28

Verification of the simplified implementation in [design.md](design.md) and [original-logic.md](original-logic.md).
No test files, cloud resources, paid model calls or Docker experiments were added.

## Scientific comparisons

- Compared all 15 active belief diagnostics on 32 saved research evaluations:
  480 comparisons, maximum absolute difference `1.1102230246251565e-16` from the
  original calculations.
- Compared three deduplication cases using actual saved embeddings and model-merge
  decisions: initial candidates, repeated candidates and an existing verified claim.
  Survivors and duplicate mappings matched the original implementation.
- Cached evidence-retrieval ordering matched the original float32 calculation.

These are deterministic comparisons, not a claim that changed runtimes or prompt
packaging produce identical stochastic discovery trajectories.

## File and checkpoint checks

- Staged a CSV, a two-sheet XLSX workbook and arbitrary JSON metadata; file hashes
  and workbook sheets were preserved, and benchmark-like metadata fields were not stripped.
- Parsed an actual archived AGY verification result. Missing empirical counts failed;
  an empty proposal list remained a valid stop outcome.
- Restored an interrupted checkpoint containing a recorded complete evaluation.
  Two resume calls produced one root visit and one completed evaluation, with no
  model or Docker calls. JSON/Markdown evidence export succeeded.

## Packaging and SDK checks

- Built the wheel and source distribution.
- Installed the wheel in a clean Python 3.12 environment outside the repository;
  imports and CLI help worked, and prompt resources were packaged.
- Confirmed the removed Journal/Store/protocol modules are absent from the wheel.
- Constructed seven Google SDK tool declarations without model requests.
  Phase A guards rejected normalized-path attempts to access inputs or overwrite
  the frozen search file.
- Ruff and Pyright checks passed for the standalone package and deployment renderer.

## Not verified

Live AGY authentication, Docker image execution, cloud IAM/deployment, Gemini model
access/grounding and a real end-to-end cloud discovery remain unverified. See
[local.md](local.md) and [google.md](google.md) for the prerequisites and the separate live acceptance step.

