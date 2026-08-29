# Standalone Urithiru

The implementation follows the original research engine, with shared state held
by cohesive classes and short methods. The line-by-line source mapping and the
mistakes corrected from the initial rewrite are recorded in [original-logic.md](original-logic.md).

## What stays

The active workflow is EDA → candidate deduplication/selection → parametric prior
→ literature assessment → empirical verification → optional independent external
verification → one MCTS update. It keeps UCT, progressive widening, evidence
retrieval, candidate audits and every active belief diagnostic.

`BeliefAnalysis` holds prior/search/code beliefs. `CandidateSelector` holds its
model and caches. `MCTSTree` holds the root and nodes. `UrithiruEngine` holds the
run state. `ResearchAgent` builds the original scientific goals; the sandbox runs
them. Methods take the changing domain inputs, not repeated configuration bundles.

## What changes

- The package installs independently, without importing the research checkout.
- CSV/TSV/Parquet/XLSX/XLS and optional text metadata replace benchmark-specific loaders.
- EDA supplies a descriptive schema for subsequent data-blind verification.
- Docker uses the operator's existing agent image and login volume; extra credentials are declared.
- Both runtimes launch the same agent CLI; Cloud Run isolates it with a Cloud Run sandbox.
- Checkpoints are ordinary JSON files, atomically replaced using a temporary file.
- One `[budget]` config section holds every timeout, turn cap, download cap and retry count.
- Four packages: `core` (science), `agents` (prompts and readers), `runtime` (execution), `cloud`.
- Every event is one JSON line on stdout: readable locally, structured in Cloud Logging.

There is no generic store, journal, task-state framework, reconciliation command,
streaming layer or doctor command. Historical experiments and inactive belief modes
are not ported. See [architecture.md](architecture.md), [local.md](local.md), [google.md](google.md), and [provenance.md](provenance.md).

## Verification boundary

Verify deterministic scientific calculations, cached candidate decisions, result
parsing, checkpoint restoration and standalone packaging without adding tests or
calling models. Docker and Google end-to-end execution remain unverified until
their prerequisites and separately authorized execution are available.

No cloud resources are provisioned, no public service is exposed, and no license
or publication decision is made by this implementation.

