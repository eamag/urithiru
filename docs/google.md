# Google Cloud setup and deployment

**Live cloud execution is unverified.** No resources were provisioned and no cloud
model calls were made. These instructions describe actions an authorized operator can
take; they incur infrastructure and model charges.

See [design.md](design.md), [architecture.md](architecture.md), [local.md](local.md),
[provenance.md](provenance.md), and [../sources/index.md](../sources/index.md).

## What gets created

One image, one bucket, one service account, one Cloud Run Job, one secret. The job
runs the same discovery loop as the local runtime and launches the same agent CLI;
the only difference is that generated code is isolated by a
[Cloud Run sandbox](https://docs.cloud.google.com/run/docs/code-execution) instead of
a Docker container. There is no second worker job, no public endpoint, no Firestore
and no Docker socket.

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
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com iam.googleapis.com
gcloud artifacts repositories create urithiru --repository-format=docker --location="$REGION"
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://$BUCKET" --public-access-prevention
gcloud iam service-accounts create urithiru
export SERVICE_ACCOUNT="urithiru@$PROJECT_ID.iam.gserviceaccount.com"
```

The agent CLI authenticates with a Gemini API key, not with this project's
credentials. Keep it in Secret Manager; it is never written to configuration or to
run artifacts:

```sh
printf %s "$GEMINI_API_KEY" | gcloud secrets create urithiru-gemini-api-key --data-file=-
gcloud secrets add-iam-policy-binding urithiru-gemini-api-key \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/secretmanager.secretAccessor
```

The service account needs bucket objects and model invocation, and nothing else. It
has no Owner/Editor, no token creation, no access to unrelated datasets, and no
permission to launch jobs:

```sh
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/storage.objectUser
gcloud iam roles create urithiruModelCaller --project="$PROJECT_ID" \
  --title="Urithiru model invocation" \
  --permissions=aiplatform.endpoints.predict,serviceusage.services.use --stage=GA
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role="projects/$PROJECT_ID/roles/urithiruModelCaller"
```

## Build

The image installs the agent CLI from its official installer; this repository
redistributes no agent binary and no credentials. Build with Cloud Build so an
Apple Silicon image is never deployed to Cloud Run:

```sh
export IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/urithiru/urithiru:v0.1.0"
gcloud builds submit --tag "$IMAGE_TAG" .
```

Resolve the pushed digest and set `IMAGE_URI` to that immutable reference
(`REGION-docker.pkg.dev/PROJECT/urithiru/urithiru@sha256:DIGEST`). Record it with the
run's model and configuration provenance; a mutable tag makes a rerun unattributable
to a known build.

## Deploy

Rendering writes YAML only and never contacts Google Cloud:

```sh
export SERVICE_ACCOUNT IMAGE_URI
uv run python deploy/render.py --output /tmp/urithiru-deployment
gcloud run jobs replace /tmp/urithiru-deployment/job.yaml --region="$REGION"
```

The template sets `sandboxLauncher: gvisor`, one task, `maxRetries: 0`, four CPUs and
8 GiB. The job hosts every parallel agent, so size it for `search.parallelism`
concurrent analyses. Cloud Run's filesystem is in-memory and counts against that
8 GiB together with pandas overhead, so keep `budget.input_mib` well below it.

The orchestrator sets per-execution arguments and timeouts through the Jobs API, so
no deployment edit is needed per dataset.

## Isolation

Generated code runs through `sandbox do`, which gives it the goal workspace, a
private home for the agent, the API key, and outbound network — but **not** this
job's environment variables and **not** the metadata server. Generated Python
therefore cannot mint tokens for the run's service identity. This is a deployment for
a trusted operator, not a hostile-tenant execution service.

Cloud Run sandboxes are a Preview feature. Confirm `sandboxLauncher` is accepted in
your region and that `/usr/local/gcp/bin/sandbox` exists in a running task before
depending on it. Confirm too that the non-root `worker` user can launch a sandbox; if
not, run the job as root or grant the necessary capability.

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
uv run urithiru cancel gs://BUCKET/urithiru/RUN_ID
uv run urithiru resume gs://BUCKET/urithiru/RUN_ID
uv run urithiru export gs://BUCKET/urithiru/RUN_ID --output /absolute/path/cloud-evidence
```

Use Cloud Run executions and Cloud Logging for task startup, resource exhaustion and
API errors; the engine emits one JSON line per event, which Cloud Logging parses
natively. `status` reports the durable checkpoint, whose timestamp may be stale after
a hard crash; it never invents completion from a submitted job.

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

After separately authorizing costs, run one small dataset end to end. Inspect the
generated code, source captures, metrics and any external abstention. Exercise a
cancellation and a resume, and confirm the root visit count equals the number of
completed evaluations. Verify the bucket is private and that the service account
cannot launch jobs. Review artifacts for secrets before sharing. Preserve a backend
execution screenshot and log, and disclose the pre-existing research work.
