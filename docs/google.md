# Google Cloud setup and deployment

Live Cloud Run execution, Application Default Credentials, Gemini model access and
Cloud Storage checkpoint/event transport were exercised on 2026-08-29. The accepted
run is recorded below. Cloud Run's Preview gVisor launcher was not available in the
project, so that run used the documented container-isolation fallback.

See [design.md](design.md), [architecture.md](architecture.md), [local.md](local.md),
[provenance.md](provenance.md), and [../sources/index.md](../sources/index.md).

## What gets created

One image, one bucket, one service account and one Cloud Run Job. The job runs the
same discovery loop as the local runtime and launches the same agent CLI. Each goal
gets a private workspace and `HOME`; when the Preview launcher is available it can
also run through a [Cloud Run sandbox](https://docs.cloud.google.com/run/docs/code-execution).
There is no second worker job, public endpoint, Firestore, Docker socket or API-key
secret: the run's checkpoint and event log in the bucket are its state.

```sh
gcloud auth login
gcloud auth application-default login
export PROJECT_ID=your-project-id
export REGION=us-central1
export BUCKET=your-globally-unique-private-run-bucket
gcloud config set project "$PROJECT_ID"
```

Generation defaults to `gemini-3.7-flash` in `global`; embeddings use
`text-embedding-005` in `us-central1`. Confirm model availability, quota and your
data-residency requirements first. There is no fallback to an older model.

## Provision

```sh
gcloud services enable run.googleapis.com aiplatform.googleapis.com storage.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com iam.googleapis.com
gcloud artifacts repositories create urithiru --repository-format=docker --location="$REGION"
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://$BUCKET" --public-access-prevention
gcloud iam service-accounts create urithiru
export SERVICE_ACCOUNT="urithiru@$PROJECT_ID.iam.gserviceaccount.com"
```

The agents and the GenAI SDK both use the job's Application Default Credentials; no
API key is created, injected or stored. The service account needs bucket objects and
model invocation, and nothing else. It
has no Owner/Editor, no token creation, no access to unrelated datasets, and no
permission to launch jobs:

```sh
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/storage.objectUser
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/aiplatform.user
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

The template sets one task, `maxRetries: 0`, eight CPUs and 16 GiB. Its
`sandboxLauncher: gvisor` line is deliberately commented because the Cloud Run API
rejects it until the project and region have Preview access. The job hosts every agent,
and each step runs its search and code agents at the same time, so size it for
`2 x search.parallelism` concurrent agents. Cloud Run's filesystem is in-memory and
counts against that 16 GiB together with pandas overhead, so keep `budget.input_mib`
well below it.

The orchestrator sets per-execution arguments and timeouts through the Jobs API, so
no deployment edit is needed per dataset.

## Isolation

Every goal gets its own workspace and private `HOME`; search and external never receive
the seed dataset, and no stage inherits another stage's CLI scratch files. In the
currently verified fallback, the agent runs directly in the job container and can reach
the metadata server, so generated Python can use the run's tightly scoped service
identity. This is a deployment for a trusted operator, not a hostile-tenant execution
service.

The `sandbox do` branch additionally withholds the parent environment and metadata
server, but ADC is also obtained from that metadata server. Do not enable that branch
until the Preview launcher is available and the agent has a supported credential path;
otherwise the isolation succeeds and model authentication fails.

Isolation also carries a scientific guarantee, not only a security one. The literature
agent's sandbox is given a workspace containing its goal and nothing else: the dataset
is never copied in, so its belief cannot have been informed by the data whatever the
agent does. `search_<node>/` in the bucket's `sandbox_artifacts/` is the audit trail —
if a data file ever appears there, that belief is not data-blind.

Cloud Run sandboxes are a Preview feature, so the orchestrator checks for
`/usr/local/gcp/bin/sandbox` at startup. When it is missing the run does not fail:
the agent runs directly in this container, and a `sandbox_unavailable` warning with
`isolation=container` is logged once. Generated code then shares the job's identity
and can reach the metadata server, so it is bounded only by the service account's own
permissions — the bucket and Vertex predict, nothing else.

To depend on the stronger boundary, confirm `sandboxLauncher` is accepted in your
region, that the binary is present in a running task, and that the non-root `worker`
user can launch a sandbox; if not, run the job as root or grant the necessary
capability. Check the log line before treating a run as isolated.

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

To watch a run on the web page, keep a copy of its checkpoint and log beside the page.
This reads the bucket from your own credentials, so the bucket stays private:

```sh
uv run urithiru publish gs://BUCKET/urithiru/RUN_ID --watch
cd web && bun run dev
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

## Acceptance before real use

### Live acceptance recorded 2026-08-29

Run `ea189cd9bccd4cb6b7da9998d2e12bda` completed one hypothesis in 7 minutes 24
seconds with no run error. Proposal, code, literature and external stages all returned
successfully. Code and literature started concurrently under different goal IDs; the
event object in Cloud Storage advanced while the checkpoint timestamp was unchanged;
and the external stage tested independent Sanbao and Hulu Cave records rather than
reusing the seed experiment. The run logged `sandbox_unavailable` and
`isolation=container`, so this verifies the fallback, not gVisor.

The local Docker runtime, Preview gVisor path, live cancellation/resume, IAM denial
checks and artifact secret review remain separate acceptance items.

After separately authorizing costs, run one small dataset end to end. Inspect the
generated code, source captures, metrics and any external abstention. Exercise a
cancellation and a resume, and confirm the root visit count equals the number of
completed evaluations. Verify the bucket is private and that the service account
cannot launch jobs. Review artifacts for secrets before sharing. Preserve a backend
execution screenshot and log, and disclose the pre-existing research work.
