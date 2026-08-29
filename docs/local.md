# Local setup

See [design.md](design.md), [architecture.md](architecture.md) and
[google.md](google.md). The package does not read the parent repository and does not
automatically load any `.env` file.

```sh
uv sync --locked
uv run urithiru --help
```

## Sandbox image

Start Docker or OrbStack and supply your existing `urithiru-sandbox:latest` image
and `agy_credentials` volume. The image must expose `/root/.local/bin/agy` and a
Python with pandas, numpy, scipy, statsmodels, openpyxl and xlrd — plus `pyarrow` if
you intend to pass Parquet files. This package's own `Dockerfile` builds the
separate Google SDK worker; it does not redistribute the agent CLI or your
credentials.

Authenticate interactively if needed:

```sh
docker run --rm -it -v agy_credentials:/root urithiru-sandbox:latest bash
# In that container:
/root/.local/bin/agy
```

The container runs as root so it can read the mounted login volume. On Linux this
leaves root-owned files in the run directory; run the CLI as a user that can delete
them, or use Docker Desktop / OrbStack on macOS where the mount is remapped.

## Editor setup

The parent research checkout also contains a package named `urithiru`, so opening the
outer directory as your editor's workspace root makes Pylance resolve `urithiru.*` to
the research engine and report symbols such as `Evaluation` as unknown imports. Open
**this** directory as the workspace root; `.vscode/settings.json` then points at the
local `.venv` and `src/`. The `pyright` CLI run from here has always resolved
correctly, which is why the editor and the command line disagreed.

## Credentials

Export `PROJECT_ID` and `VERTEX_API_KEY` in the calling shell. These cover the
host's prior, embedding and deduplication calls through the Google GenAI SDK in
Vertex express mode. Credentials are never written into run configuration.

Extra agent credentials are opt-in through `agent_env` in `configs/docker.toml`,
e.g. `["S2_API_KEY", "OPENALEX_API_KEY"]`. Export each declared value yourself;
a missing or empty value fails the run. Declared values are redacted from generated
artifacts after each container exits. Do not copy a research `.env` into a sandbox.

## Run

```sh
uv run urithiru run \
  --data /absolute/path/data.csv --data /absolute/path/context.xlsx \
  --metadata /absolute/path/description.md \
  --steps 3
```

`--data` and `--metadata` are repeatable, one flag per file. `--config` defaults to
`configs/docker.toml`, `--steps` to 3 and `--seed` to 42; `urithiru run --help` lists
every option with its default.

Inputs can be CSV, TSV, Parquet, XLSX or XLS; the agent interprets workbook sheets.
Metadata is optional UTF-8 text, passed intact without benchmark parsing. The
runtime comes from the profile — there is no `--runtime` flag.

The CLI prints `run=<directory>` and then one JSON event per line: `stage_started`,
`container_started`, `proposals_ready`, `hypothesis_selected`,
`hypothesis_evaluated`, `run_finished`. Pipe through `jq -r .message` for a plain
progress log. Model calls and the agent CLI use their configured account quota;
this command is not an offline check.

```sh
uv run urithiru status /absolute/path/runs/RUN_ID
uv run urithiru cancel /absolute/path/runs/RUN_ID
uv run urithiru resume /absolute/path/runs/RUN_ID
uv run urithiru export /absolute/path/runs/RUN_ID --output /absolute/path/new-export
```

## Steps and time

`--steps` is how many hypotheses to evaluate. The profile's `[budget]` section states
every wall-clock and size limit explicitly — stage minutes, grace, the agent's
tool-turn cap, the generated-script timeout, the model output cap, download caps in
MiB and the retry count. There are no timeout constants anywhere else in the code.

`--proposal-minutes`, `--verification-minutes` and `--external-minutes` override the
corresponding profile value for a single run:

```sh
uv run urithiru run --data /absolute/path/data.csv --steps 5 --external-minutes 25
```

The run record stores the resolved values, so a `resume` cannot silently change the
limits the run started under.

## Behaviour

Resume loads the original run configuration and checkpoint. Start a new run to
change data, models, budget or scientific settings. A failed workspace is retained
as `<goal>_previous_<hex>`; a valid completed result is reused. A transient stage
failure retries up to the budget's attempt limit before the run fails, and siblings
that already succeeded are committed to the checkpoint first.

Export requires a new destination and includes original inputs, generated code,
structured metrics, source captures and logs. Stop or finish a run before export.
Treat the evidence directory as private until reviewed. Model beliefs are elicited
assessments, not calibrated statistical confidence.
