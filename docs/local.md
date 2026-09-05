# Local setup

See [architecture.md](architecture.md) and
[google.md](google.md). The package does not read the parent repository and does not
automatically load any `.env` file.

```sh
uv sync --locked
uv run urithiru --help
```

## Sandbox image

Start Docker or OrbStack, build the included worker image, then create a persistent
volume for the agent CLI login:

```sh
docker build -t urithiru-sandbox:latest .
docker volume create agy_credentials
docker run --rm -it --user root \
  -v agy_credentials:/root \
  --entrypoint /usr/local/bin/agy \
  urithiru-sandbox:latest
```

The image installs the agent CLI from its official installer and builds the scientific
Python environment from `deploy/analysis-requirements.txt`; the repository contains
neither the CLI binary nor credentials.

A step runs its search and code containers at the same time, so budget for
`2 x search.parallelism` containers at 4 GiB and 3 CPUs each.

Local agent stages run as root so they can read the mounted login volume. On Linux this
leaves root-owned files in the run directory; run the CLI as a user that can delete
them, or use Docker Desktop / OrbStack on macOS where the mount is remapped.

## Credentials

Export `VERTEX_API_KEY` in the calling shell. It covers the host's prior, embedding
and deduplication calls through the Google GenAI SDK. Credentials are never written
into run configuration.

## Run

```sh
uv run urithiru run \
  --data /absolute/path/data.csv --data /absolute/path/context.xlsx \
  --metadata /absolute/path/description.md \
  --steps 3
```

`--data` and `--metadata` are repeatable, one flag per file. `--config` defaults to
the Docker profile bundled in the package, `--steps` to 3 and `--seed` to 42;
`urithiru run --help` lists every option with its default. Pass a copied profile with
`--config` when you want to change models, budgets or the image name.

Inputs can be CSV, TSV, Parquet, XLSX or XLS; the agent interprets workbook sheets.
Metadata is optional UTF-8 text, passed intact without benchmark parsing. The
runtime comes from the profile — there is no `--runtime` flag.

The CLI prints `run=<directory>` and then JSON events as stages execute:
`stage_started`, `agent_started`, `agent_finished`, `stage_completed`, `stage_failed`,
`stage_backoff`, `proposals_ready`, `deduplicated`, `hypothesis_selected`,
`external_skipped`, `hypothesis_evaluated`, and `run_finished`. Pipe through
`jq -r .message` for a plain progress log. The same lines are appended to
`<run>/events.jsonl`, which is what to read to follow a run in progress. Model calls and
the agent CLI use their configured account quota; this command is not an offline check.

```sh
uv run urithiru status  /absolute/path/runs/RUN_ID
uv run urithiru logs    /absolute/path/runs/RUN_ID --follow
uv run urithiru publish /absolute/path/runs/RUN_ID --watch
uv run urithiru cancel  /absolute/path/runs/RUN_ID
uv run urithiru resume  /absolute/path/runs/RUN_ID
uv run urithiru export  /absolute/path/runs/RUN_ID --output /absolute/path/new-export
```

## Steps and time

`--steps` is how many hypotheses to evaluate. The profile's `[budget]` section states
every wall-clock and size limit explicitly — one `<stage>_minutes` per stage, the grace
period, the model output cap, the input-bundle limit in MiB and the retry count. There
are no timeout constants anywhere else in the code.

`--proposal-minutes`, `--search-minutes`, `--code-minutes` and `--external-minutes`
override the corresponding profile value for a single run:

```sh
uv run urithiru run --data /absolute/path/data.csv --steps 5 --external-minutes 25
```

The run record stores the resolved values, so a `resume` cannot silently change the
limits the run started under.

## Behaviour

Resume loads the original run configuration and checkpoint. Start a new run to
change data, models, budget or scientific settings. A failed workspace is retained
as `<goal>_previous_<hex>`; a valid completed result is reused. Each stage gets its own
workspace under `sandbox_artifacts/`, so `search_node_000001/` holds no data files at
all while `code_node_000001/` holds a copy of your inputs. A transient stage
failure retries up to the budget's attempt limit before the run fails, and siblings
that already succeeded are committed to the checkpoint first.

Export requires a new destination and includes original inputs, generated code,
structured metrics, source captures and logs. Stop or finish a run before export.
Treat the evidence directory as private until reviewed. Model beliefs are elicited
assessments, not calibrated statistical confidence. The host validates the result
schema but does not recompute agent-reported metrics, certify its validity flags or
prove the provenance independence of an external source.
