# Urithiru

Autonomous scientific discovery over your own tabular data. You supply CSV, TSV,
Parquet or Excel files and optional text notes. Agents perform exploratory analysis,
propose falsifiable hypotheses, form a literature-only prior, test each hypothesis
with code they write and execute, optionally seek independent external evidence, and
return a ranked report of what survived.

Beliefs reported by the system are **elicited model assessments, not calibrated
statistical confidence**.

## How it works

A run is a Monte Carlo tree search over hypotheses. Each **step** takes one
hypothesis through three stages:

1. **Proposal** — an agent performs exploratory analysis on your files and proposes
   candidate claims. Duplicates are removed and the most novel candidate is selected.
2. **Verification** — a second agent forms a literature-only prior, freezes it, then
   writes and runs code against your data to test the claim.
3. **External** — when the belief moved enough to be surprising, a third agent looks
   for independent data elsewhere and tests the claim again.

The result updates the tree, and the next step explores from there. `--steps` is how
many hypotheses you want evaluated.

Every evaluation follows the same order: a data-blind literature assessment is
frozen to `p_search.json` **before** the agent may open the dataset, then the
empirical test runs. That ordering is what makes the belief change meaningful.

Full detail: [docs/design.md](docs/design.md), [docs/architecture.md](docs/architecture.md).

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone <this repository> && cd urithiru
uv sync --locked
uv run urithiru --help
```

## Run on Google Cloud

The cloud runtime uses the **Antigravity CLI** for the agents, the **Google GenAI
SDK** for priors, deduplication and embeddings, one **Cloud Run Job** for the search
loop, a **Cloud Run sandbox** to isolate generated code, and **Cloud Storage** for
inputs, checkpoints and artifacts.

1. Copy `configs/google.toml` and replace `project` and `bucket` with your own.
   Placeholder values are rejected at load time.
2. Provision the project and deploy both jobs: [docs/google.md](docs/google.md).
3. Start a run. It returns immediately with a run reference and an execution name:

```sh
uv run urithiru run --config configs/google.toml \
  --data ./data/measurements.csv --metadata ./data/notes.md \
  --steps 3 --seed 42
```

```sh
uv run urithiru status gs://your-bucket/urithiru/<run-id>
uv run urithiru cancel gs://your-bucket/urithiru/<run-id>
uv run urithiru export gs://your-bucket/urithiru/<run-id> --output ./export
```

## Run locally

The local runtime drives a Docker sandbox holding your own agent CLI image and
login volume; the package does not redistribute either. Model calls for the prior,
embeddings and deduplication use a Vertex AI express key. Full setup:
[docs/local.md](docs/local.md).

```sh
export PROJECT_ID=... VERTEX_API_KEY=...
uv run urithiru run --data ./data/measurements.csv
```

`--config` defaults to `configs/docker.toml`, `--steps` to 3 and `--seed` to 42, so
`--data` is the only required option. `urithiru run --help` lists every default.

The command prints `run=<directory>` and then one JSON event per line as work
happens. Manage it with the same `status`, `resume`, `cancel` and `export`
subcommands, passing the run directory instead of a `gs://` reference.

## Steps and time

`--steps` sets how many hypotheses to evaluate. The `[budget]` section of the profile
sets how long each stage may take, in minutes:

```toml
[budget]
proposal_minutes = 5
verification_minutes = 10
external_minutes = 10
grace_minutes = 4
```

Override any of them for one run without editing the profile:

```sh
uv run urithiru run --data ./data.csv --steps 5 --external-minutes 25
```

A step costs at most `proposal + verification + external` minutes, and steps run
`parallelism` at a time (2 by default), so 5 steps with the values above is roughly
40-75 minutes of wall clock. Not every step reaches the external stage: it runs only
when the seed result was surprising. The same `[budget]` section also holds the
agent's turn cap, generated-script timeout, model output cap, download caps and the
retry count.

## Output

A run directory (local or in the bucket) holds:

```text
run_config.json         resolved settings, input hashes and metadata
mcts_state.json         authoritative tree, RNG, pending/completed IDs and status
candidate_audits.json   raw proposals, duplicate decisions and selection evidence
inputs/                 your original files, unmodified
evaluations/            one immutable JSON per completed hypothesis
sandbox_artifacts/      the agent's code, execution logs and retained sources
```

`urithiru export` copies all of that to a new directory and adds `report.json` and
`report.md`, ranked by reward. Treat the evidence directory as private until you
have reviewed it.

## Commands

```text
urithiru run      --data FILE...        start a run
urithiru status   RUN                   progress and last update
urithiru resume   RUN                   continue from the checkpoint
urithiru cancel   RUN                   stop, preserving completed work
urithiru export   RUN --output DIR      copy the run and write the ranked report
```

`RUN` is a local run directory or the `gs://bucket/prefix/run-id` printed at start;
every command works on both. The entry point is `app()` in
[src/urithiru/cli.py](src/urithiru/cli.py), where each command is one function whose
signature is its argument list and defaults.

## Reliability

Runs are checkpointed after every state change and resume from where they stopped;
completed evaluations are reused rather than recomputed. A transient agent or API
failure retries up to the profile's `stage_attempts`. Cancellation is cooperative and
preserves the checkpoint. Deterministic behaviour is verified offline against saved
artifacts: [docs/offline-verification.md](docs/offline-verification.md).

## Provenance

The scientific engine — the MCTS search, belief analysis and prompt contracts —
**pre-exists this application work** and is ported here, as recorded in
[docs/provenance.md](docs/provenance.md). The standalone package, both runtimes,
the CLI and the cloud deployment are the new work.

