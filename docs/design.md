# Standalone Urithiru

The implementation follows the original research engine, with shared state held by
cohesive classes and short methods. The line-by-line source mapping, and where this
version has since deliberately diverged, are in [original-logic.md](original-logic.md).

## What stays

The workflow is EDA → candidate deduplication/selection → parametric prior →
literature belief → empirical belief → optional independent external verification →
one MCTS update. It keeps UCT, progressive widening, evidence retrieval, candidate
audits, the belief representation and the reward.

`BeliefAnalysis` holds one evaluation's three KLs. `CandidateSelector` holds its model
and caches. `MCTSTree` holds the root and nodes. `UrithiruEngine` holds the run state.
`ResearchAgent` builds the goals; the sandbox runs them. Methods take the changing
domain inputs, not repeated configuration bundles.

## What changes

- The package installs independently, without importing the research checkout.
- CSV/TSV/Parquet/XLSX/XLS and optional text metadata replace benchmark-specific loaders.
- The literature and empirical beliefs come from **two agents in separate workspaces, started
  together**. The literature agent is never given the data, so data-blindness is
  structural rather than prompt-enforced and audited afterwards from file timestamps.
- Both runtimes launch the same agent CLI. Docker provides a container per goal; Cloud
  Run always provides a private workspace and `HOME`, and uses its Preview sandbox only
  when that launcher and an ADC credential path are available.
- Every record validates itself on construction, so an unparseable agent result fails at
  the boundary and the stage retries.
- Checkpoints are ordinary JSON, atomically replaced; the event stream is `events.jsonl`
  beside them, so anything outside the process can follow a run.
- One `[budget]` section holds every timeout, output cap and retry count, one field per stage.
- Four packages: `core` (science), `agents` (prompts and readers), `runtime` (execution), `cloud`.

There is no generic store, journal, task-state framework, reconciliation command,
streaming layer or doctor command. Historical experiments and inactive belief modes
are not ported. See [architecture.md](architecture.md), [local.md](local.md),
[google.md](google.md), and [provenance.md](provenance.md).

## What was deliberately left out

- **A second state store.** `mcts_state.json` is already authoritative and already
  checkpointed to the bucket. Mirroring it into a database would create two copies to
  keep in agreement across a resume, for no capability the bucket lacks.
- **An additional agent framework.** The Google GenAI SDK does the prior, merge and
  embedding calls, and the agent CLI runs in the runtime workspaces. Wrapping working components
  in a second orchestration layer adds a layer, not a behaviour.
- **Belief diagnostics nothing reads.** Six numbers survive because each answers a
  question no other answers; see [architecture.md](architecture.md). Variants that were
  monotone transforms of a kept number, or a second measure of the same disagreement,
  were removed rather than exported unused.

## Verification boundary

Deterministic behaviour is verified offline against stubs and saved artifacts:
[offline-verification.md](offline-verification.md). The Google container fallback was
also exercised end to end; local Docker and Preview gVisor remain separate verification
boundaries.

No public service is exposed, and no license or publication decision is made by this
implementation.
