# Google Cloud setup and deployment

See [architecture.md](architecture.md), [local.md](local.md)

## What gets created

One image, one bucket, one service account and one Cloud Run Job. The job runs the
same discovery loop as the local runtime and launches the same agent CLI. Each goal
gets a private workspace and `HOME`; when the Cloud Run sandbox binary is present
it can also run through a [Cloud Run sandbox](https://docs.cloud.google.com/run/docs/code-execution).

```sh
gcloud auth login
gcloud auth application-default login
export PROJECT_ID=your-project-id
export REGION=us-central1
export BUCKET=your-globally-unique-private-run-bucket
gcloud config set project "$PROJECT_ID"
```

Generation defaults to `gemini-3.7-flash` in `global`; embeddings use
`text-embedding-005` in `us-central1`. 

## Provision

```sh
gcloud services enable run.googleapis.com aiplatform.googleapis.com storage.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com
gcloud artifacts repositories create urithiru --repository-format=docker --location="$REGION"
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://$BUCKET" --public-access-prevention
gcloud iam service-accounts create urithiru
export SERVICE_ACCOUNT="urithiru@$PROJECT_ID.iam.gserviceaccount.com"

# Grant the orchestrator access to Cloud Storage, Vertex AI, and Cloud Logging
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/storage.objectUser"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/logging.logWriter"
```

## Build

The image installs the agent CLI from its official installer; this repository
redistributes no agent binary and no credentials.

It also builds `/opt/analysis`, the scientific Python the agents get, from
[`deploy/analysis-requirements.txt`](../deploy/analysis-requirements.txt). Add
packages there and rebuild to give every agent something new. This environment is
separate from the orchestrator's own and is owned by `worker`, so an agent can also
`pip install` into it at run time; it just costs the agent turns. A Cloud Run sandbox
inherits no environment, so `runtime/sandbox.py` puts `/opt/analysis/bin` on PATH when
it launches an agent — without that the agent would get the bare system interpreter.

Build with Cloud Build so an Apple Silicon image is never deployed to Cloud Run:

```sh
export IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/urithiru/urithiru:v0.1.0"
gcloud builds submit --tag "$IMAGE_URI" .
```

A production deployment should replace that tag with the pushed digest
(`REGION-docker.pkg.dev/PROJECT/urithiru/urithiru@sha256:DIGEST`) and record it with
the run's model and configuration provenance; a mutable tag makes a rerun
unattributable to a known build.

## Deploy

Substitution writes YAML only and never contacts Google Cloud:

```sh
sed -e "s|\${IMAGE_URI}|$IMAGE_URI|" -e "s|\${SERVICE_ACCOUNT}|$SERVICE_ACCOUNT|" \
  deploy/job.yaml.template > /tmp/urithiru-job.yaml
gcloud run jobs replace /tmp/urithiru-job.yaml --region="$REGION"
```

The template sets one task, `maxRetries: 0`, eight CPUs and 16 GiB. Agent
isolation is decided at runtime, not at deploy time: when the Cloud Run sandbox
binary (`/usr/local/gcp/bin/sandbox`) is present, each agent runs sandboxed with
its workspace bind-mounted at `/workspace` and a private `HOME`; otherwise the
orchestrator falls back to container-level isolation and emits a
`sandbox_unavailable` warning event, so the downgrade is visible in the log.
The job hosts every agent, and each step runs its search and code agents at the
same time, so size it for `2 x search.parallelism` concurrent agents. Cloud Run's filesystem is in-memory and
counts against that 16 GiB together with pandas overhead, so keep `budget.input_mib`
well below it.

The orchestrator sets per-execution arguments and timeouts through the Jobs API, so
no deployment edit is needed per dataset.

## Configure and submit

Copy `configs/google.toml` to a private operator configuration and replace project
and bucket. Configuration holds identifiers and limits, never keys.

```sh
uv run urithiru run --config /absolute/path/google.toml \
  --data /absolute/path/dataset.xlsx --metadata /absolute/path/context.md --steps 3
```

The CLI uploads the original files and the immutable configuration, starts the job,
and returns a `gs://bucket/prefix/run-id` reference. Closing the terminal does not
stop cloud work.

```sh
uv run urithiru status gs://BUCKET/urithiru/RUN_ID
uv run urithiru logs   gs://BUCKET/urithiru/RUN_ID --follow
uv run urithiru cancel gs://BUCKET/urithiru/RUN_ID
uv run urithiru resume gs://BUCKET/urithiru/RUN_ID
uv run urithiru export gs://BUCKET/urithiru/RUN_ID --output /absolute/path/cloud-evidence
```

Operator bucket commands (inspecting without downloading full run trees):

```sh
# List all runs in the bucket with status and top findings
uv run urithiru catalog --config configs/google.local.toml

# Set a descriptive title for a run in the bucket
uv run urithiru label --run RUN_ID --title "NHANES Cardiorespiratory Analysis" --config configs/google.local.toml

# Read a single sanitized artifact straight from the bucket (run.json, mcts_state.json, events.jsonl)
uv run urithiru artifact --run RUN_ID --name run.json --config configs/google.local.toml
```

`status` reports the checkpoint **and** whether a Cloud Run execution is still alive.
A status of `running` with `"execution": null` means the job died without writing a
final checkpoint — the one failure the checkpoint alone cannot tell you about.

Use Cloud Run executions and Cloud Logging for task startup, resource exhaustion and
API errors; the engine emits one JSON line per event, which Cloud Logging parses
natively. The same lines are appended to `gs://BUCKET/PREFIX/RUN_ID/events.jsonl`,
which is uploaded as each line is written rather than at checkpoints, so anything with
read access to the bucket follows a run in order without Cloud Logging permissions and
without waiting out a stage. `status` reports the durable checkpoint, whose timestamp
may be stale after a hard crash; it never invents completion from a submitted job.

To inspect a reviewed run on the static web page, publish its sanitized checkpoint and
event log, then build the site. This reads the bucket from your own credentials, so the
bucket stays private:

```sh
uv run urithiru publish gs://BUCKET/urithiru/RUN_ID
(cd web && bun run build && bun run preview)
```

Remove the published copy from the repository root when done:

```sh
uv run urithiru unpublish gs://BUCKET/urithiru/RUN_ID
```

## Resume

The cloud orchestrator uses the same JSON checkpoints as the local engine, downloading
them at startup and uploading them after each save. Resume reuses completed
evaluations and the saved tree and RNG state. Work beyond the last uploaded checkpoint
may need repeating after an abrupt termination.

Keep one orchestrator per run; the CLI checks for an active execution before
submitting. Checkpoint uploads carry a Cloud Storage generation precondition, so a
second orchestrator writing the same run fails loudly instead of clobbering it. Do not
enable Cloud Run automatic retries. Job launch RPCs are never retried automatically:
if a launch outcome is uncertain, inspect Cloud Run before submitting again.
