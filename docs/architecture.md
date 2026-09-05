# Architecture

A run is a Monte Carlo tree search over hypotheses. Each step can use four agent stages
on one claim.

## System Overview & Scientific Workflow

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion & Proposal"]
        Data["Tabular Data (CSV/TSV/Parquet/Excel)<br/>+ Domain Notes (Markdown)"] --> Engine["UrithiruEngine (MCTS)"]
        Engine --> Proposal["Proposal Agent<br/>(Gemini 3.7 Flash + Data Inspection)"]
        Proposal --> Claims["Raw Hypothesis Candidates"]
        Claims --> Selector["CandidateSelector<br/>(text-embedding-005 Diversity + Flash Lite Dedup)"]
        Selector --> Prior["Parametric Prior Elicitation<br/>P_param = Beta(0.5, 0.5) 30-Vote Posterior"]
    end

    subgraph SplitSandbox["2. Concurrent Evidence Separation"]
        Prior --> Fork{"Concurrent Execution"}
        Fork -->|Data-Blind Goal| Search["Literature Search Agent (P_search)<br/>OpenAlex / PubMed / Grounded Search<br/>*NO DATA IN WORKSPACE*"]
        Fork -->|Data-Visible Goal| Code["Experiment Code Agent (P_code)<br/>Python / Pandas / Statsmodels / Scipy<br/>*BLIND TO LITERATURE*"]
    end

    subgraph SurprisalBlock["3. Bayesian Surprisal & Divergence"]
        Search --> Analysis["BeliefAnalysis & Surprisal<br/>KL(P_code || P_search) in nats<br/>Normalized R_ICE Score"]
        Code --> Analysis
    end

    subgraph ExternalBlock["4. External Dataset Challenge"]
        Analysis -->|Surprising Divergence?| Check{"Is Surprising?"}
        Check -->|Yes| External["External Verification Agent (P_external)<br/>Searches Zenodo / Dryad / Repositories<br/>Separately Collected Data"]
        Check -->|No| Skip["Skip External Check<br/>(Abstain to Conserve Budget)"]
        External --> Synthesis["Consolidated Evaluation"]
        Skip --> Synthesis
    end

    subgraph MCTS["5. Tree Update & Persistence"]
        Synthesis --> Backprop["Tree Backpropagation & UCT Scoring"]
        Backprop --> Tree["MCTSTree State (mcts_state.json)"]
        Tree --> Checkpoint["Atomic Checkpoint & Generation Precondition"]
        Tree --> Extend{"Extend Budget?<br/>(resume --steps)"}
    end
```

## Cloud Infrastructure & Data Flow

```mermaid
flowchart LR
    subgraph Registry["Artifact Registry"]
        Image["docker.pkg.dev/.../analysis:latest<br/>(Pre-baked Python + Scientific Packages)"]
    end

    subgraph CloudRunEnv["Google Cloud Run"]
        Job["Cloud Run Job<br/>(Urithiru Orchestrator Process)"]
        Sub1["Goal Workspace 1<br/>(dedicated path + private HOME)"]
        Sub2["Goal Workspace 2<br/>(dedicated path + private HOME)"]
        Job -.->|Spawns Agent Stages| Sub1
        Job -.->|Spawns Agent Stages| Sub2
    end

    subgraph GoogleAI["Google Gemini APIs"]
        GeminiPro["Gemini 3.7 Flash<br/>(Reasoning & Code)"]
        GeminiLite["Gemini 3.5 Flash Lite<br/>(Candidate Dedup)"]
        Embeddings["text-embedding-005<br/>(Candidate Diversity)"]
    end

    subgraph Storage["Google Cloud Storage"]
        Bucket["gs://bucket/urithiru/<run-id>/<br/>├── run_config.json<br/>├── mcts_state.json<br/>├── events.jsonl<br/>├── candidate_audits.json<br/>├── inputs/<br/>├── artifacts/<br/>├── evaluations/<br/>├── sandbox_artifacts/<br/>├── status.json (catalog summary)<br/>└── label.txt (optional title)"]
    end

    subgraph Presentation["Delivery & Observability"]
        CLI["Antigravity CLI / Operator Terminal<br/>(urithiru status / logs / resume / export)"]
        Web["Static Visualizer (Astro + Svelte 5)<br/>(Tree View, Belief Chains, Plots & Reports)"]
    end

    Registry -->|Pulls Image| Job
    Job <-->|LLM Reasoning & Embeddings| GoogleAI
    Job -->|Continuous Atomic Uploads| Storage
    Storage -->|Stream Telemetry| CLI
    Storage -->|Read Static Snapshots| Web
    CLI -->|Resume / Cancel Commands| Job
```

## Checkpoints and outputs

```text
run_config.json             resolved settings, original input hashes and metadata
mcts_state.json             authoritative tree, RNG, pending/completed IDs and status
events.jsonl                every event in order; what to read to follow a live run
candidate_audits.json       raw proposals, duplicate decisions and selection evidence
inputs/                     original datasets
artifacts/                  embedding and merge caches (embeddings.json, dedupe_llm_decisions.json)
evaluations/                completed evaluations, reusable after interruption
sandbox_artifacts/          analysis code, source captures and execution logs
status.json                 lightweight progress summary for fast bucket catalog listing
label.txt                   optional human-readable title attached by operator
```

`mcts_state.json` says where a run got to; `events.jsonl` says what it did on the way.
Both live at the run prefix in the bucket, so any external reader can follow a run
without touching Cloud Logging. `status.json` allows the catalog and static index builder to list
bucket runs in $O(1)$ without downloading megabyte checkpoint trees. They are written
on different schedules: the checkpoint is uploaded under a generation precondition
whenever the tree changes, while the event log is mirrored as each line is written. A stage takes minutes, so a log that only moved
at checkpoints would leave a reader watching nothing for most of a step.

### What an agent leaves behind

`sandbox_artifacts/<goal-id>/` is the agent's own working directory. Docker
bind-mounts it at `/workspace`. On Cloud Run it is bind-mounted at `/workspace`
when the sandbox binary is present; otherwise the agent runs in place at the
resolved path with container-level isolation and a `sandbox_unavailable` warning
is emitted. Nothing prescribes what goes in it. The agent decides how
many scripts to write and how many experiments to run, and the retained tree is uploaded:

```text
sandbox_artifacts/code_node_000001/
    goal.txt                      what we asked
    agent.log                     the agent's own stdout and stderr
    explore_columns.py            whatever it decided to write, at any depth
    fit_baseline.py
    check_autocorrelation.py
    sensitivity_leave_one_site_out.py
    figures/residuals.png
    intermediate/cleaned.parquet
    result.json                   the one file the harness insists on
```

The agent's interpreter is `/opt/analysis`, a scientific Python built into the image
from `deploy/analysis-requirements.txt` and put on PATH at launch. It has pandas, numpy,
scipy, statsmodels, scikit-learn, pyarrow, the spreadsheet readers, matplotlib and the
HTTP/PDF/HTML parsers, so an agent starts working instead of installing.

`upload_directory` sends every regular file under the workspace and excludes exactly
three things: dot-directories (the agent's own session cache), symlinks, and the
`inputs/` copy of the seed data, which already lives once at the run prefix. Docker
cleanup additionally removes symlinks and any `.env` file from the retained workspace,
and the cloud upload skips dot-files for the same reason, so agent credentials never
persist in run artifacts. There is
no file count limit and no naming convention — `result.json` is the only path the
harness reads, and it exists so the run has a machine-readable verdict, not to stand
in for the work.

Note that Cloud Run's filesystem is in memory and counts against the job's memory
limit, shared by every concurrent agent. A `code` agent writing large intermediates or
an `external` agent downloading a large candidate dataset is bounded by that, not by
disk.

Every wall-clock and size limit lives in the profile's `[budget]` section, stated in
minutes and MiB, one `<stage>_minutes` per stage; there are no timeout constants
elsewhere.

## The page

`web/` is a static Astro site with a public explainer at `/` and the run workspace
at `/workspace`. `urithiru publish` copies `mcts_state.json`, `events.jsonl` and
a trimmed `run.json` out of a run — local or in a bucket — into
`web/public/runs/<id>/` before the site is built. The browser reads only those static,
sanitized files and never receives cloud credentials. Runs are launched, resumed and
cancelled through the CLI, not the web page.

It renders those files as written rather than a shape assembled for it: the tree comes
from the checkpoint's nodes, each hypothesis's four probabilities are recomputed in the
browser from the same category counts the engine stored, and the log is the event file
line for line. `run.json` is the one exception, and it exists to take something away —
the run profile names the project, bucket and service account, and publishing a run
should not publish where it ran.

## Scientific details

The five-category representation, 30 pseudovotes and Beta(0.5, 0.5) conversion match
the research calculation. Seed reward is `tanh(KL(P_code || P_search))`; external
reward retains the information-minus-cost calculation.

One evaluation reports six numbers, one per question, all in nats over the same five
categories so they are directly comparable:

| | |
| --- | --- |
| `kl_search_param` | what the literature search added to the naked model prior |
| `kl_code_search` | what running the experiment added to the literature — this drives reward |
| `kl_code_param` | what the evaluation added in total |
| `r_ice_norm` | the share of that information which came from data rather than literature |
| `belief_change` | the same move as a readable probability delta |
| `is_surprising` | whether that was enough to spend an agent turn looking for external data |

Negative evidence is retained; terminal nodes are excluded from retrieval. The external
agent is instructed to preserve the literal claim and use a non-overlapping population,
with abstention allowed and unrewarded. The host validates the returned structure but
does not independently verify that provenance, recompute the reported analysis or certify
the agent's validity flags. Those artifacts are retained so an operator can do that review.
