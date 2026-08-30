# Urithiru

Autonomous scientific discovery over your own tabular data. You supply CSV, TSV,
Parquet or Excel files and optional text notes. Agents perform exploratory analysis,
propose falsifiable hypotheses, form a literature-only prior, test each hypothesis
with code they write and execute, optionally seek independent external evidence, and
return a ranked report of what survived.

Beliefs reported by the system are **elicited model assessments, not calibrated
statistical confidence**.

## How it works

A run is a Monte Carlo tree search over hypotheses. Each **step** can use four agent
stages on one claim:

1. **Proposal** — an agent explores your files and proposes candidate claims.
   Duplicates are removed and the most novel candidate is selected.
2. **Search** and **Code**, at the same time, in separate workspaces and private homes. The search
   agent judges the claim from published literature; its workspace never receives your
   data. The code agent writes and runs an analysis against your data; it is never told
   what the literature concluded.
3. **External** — when those two answers disagree enough to be surprising, a fourth
   agent goes looking for independent data elsewhere and tests the claim again.

The result updates the tree, and the next step explores from there. `--steps` is how
many hypotheses you want evaluated.

The distance between the search and code beliefs is the whole point, so the two are
produced by agents that cannot see each other's work. Data-blindness is not a rule the
literature agent is asked to follow — the files are simply absent from its workspace.

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
loop, a private workspace and `HOME` per goal, and **Cloud Storage** for inputs,
checkpoints and artifacts. Preview gVisor isolation can be enabled when available;
otherwise the run logs its container-isolation fallback. There is no second state
store: the checkpoint and event log in the bucket are what a run is.

1. Copy `configs/google.toml` and replace `project` and `bucket` with your own.
   Placeholder values are rejected at load time.
2. Provision the project and deploy the job: [docs/google.md](docs/google.md).
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

## Watch it

`web/` is a static page that renders a run: the search tree, the four beliefs behind
each hypothesis, and the event log. It has no server and no credentials —
`urithiru publish` copies the run's checkpoint and event log next to it, and `--watch`
keeps copying until the run finishes.

```sh
uv run urithiru publish gs://your-bucket/urithiru/<run-id> --watch
cd web && bun install && bun run dev
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
search_minutes = 8      # these two run at the same time,
code_minutes = 10       # so a step costs the larger of them, not the sum
external_minutes = 10
grace_minutes = 4
```

Override any of them for one run without editing the profile:

```sh
uv run urithiru run --data ./data.csv --steps 5 --external-minutes 25
```

A step costs at most `proposal + max(search, code) + external` minutes, and steps run
`parallelism` at a time (2 by default), so 5 steps with the values above is roughly
35-65 minutes of wall clock. Not every step reaches the external stage: it runs only
when the two beliefs disagreed enough. Because search and code run together, a step
holds up to two sandboxes at once, and a run holds up to `2 x parallelism`.

## Output

A run directory (local or in the bucket) holds:

```text
run_config.json         resolved settings, input hashes and metadata
mcts_state.json         authoritative tree, RNG, pending/completed IDs and status
events.jsonl            every event in order; read this to follow a run in progress
candidate_audits.json   raw proposals, duplicate decisions and selection evidence
inputs/                 your original files, unmodified
evaluations/            one immutable JSON per completed hypothesis
sandbox_artifacts/      each agent's code, execution logs and retained sources
```

`urithiru export` copies all of that to a new directory and adds `report.json` and
`report.md`, ranked by reward. Treat the evidence directory as private until you
have reviewed it.

## Commands

```text
urithiru run      --data FILE...        start a run
urithiru status   RUN                   progress, last update, and whether it is alive
urithiru logs     RUN [--follow]        the run's event log, in order
urithiru resume   RUN                   continue from the checkpoint
urithiru cancel   RUN                   stop, preserving completed work
urithiru publish  RUN [--watch]         copy the run where the web page can read it
urithiru export   RUN --output DIR      copy the run and write the ranked report
```

`RUN` is a local run directory or the `gs://bucket/prefix/run-id` printed at start;
every command works on both. The entry point is `app()` in
[src/urithiru/cli.py](src/urithiru/cli.py), where each command is one function whose
signature is its argument list and defaults.

## Reliability

Runs are checkpointed after every state change and resume from where they stopped;
completed evaluations, embeddings and duplicate decisions are reused rather than
recomputed. A transient agent or API
failure retries up to the profile's `stage_attempts`. Cancellation is cooperative and
preserves the checkpoint. Deterministic behaviour is verified offline against saved
artifacts: [docs/offline-verification.md](docs/offline-verification.md).

## Provenance

The scientific engine — the MCTS search, belief analysis and prompt contracts —
**pre-exists this application work** and is ported here, as recorded in
[docs/provenance.md](docs/provenance.md). The standalone package, both runtimes,
the CLI and the cloud deployment are the new work.
