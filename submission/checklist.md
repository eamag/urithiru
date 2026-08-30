# Submission checklist

Deadline: **31 August 2026, 5:00 PM PDT**. Judging 1 Sep – 1 Oct.

Scored on Innovation & Operational Utility (40%), Architectural Discipline & Tech Stack
(30%), Demo & Production Readiness (30%), plus up to 0.6 bonus points. Final score 1–6.

Required stack, all already satisfied — say so explicitly in the description:

| Requirement | What we use |
| --- | --- |
| Gemini 3.5 or newer | `gemini-3.7-flash` (agents, priors), `gemini-3.5-flash-lite` (dedup) |
| A Google agent framework | Antigravity CLI (`agy`) in every sandbox, Google GenAI SDK for priors/embeddings |
| A Google Cloud service | Cloud Run Jobs, Cloud Storage, Cloud Build, Artifact Registry |

---

## 0. Decisions to take first

- [x] **Category: The Taskmaster.** "Complete workflows with autonomous action, not just
      chatbots" is a description of this project. Collaborative Partner is a bad fit (no
      human in the loop by design) and Fortified Enterprise Fleet wants institutional
      fleets. One project can win one prize, but the category choice does not stop the
      judges considering it for Best Architectural Design or Individual/Hobbyist.
- [x] **What the hosted URL points at** — option B: public viewer, token-gated launcher.
      Deployed to Cloud Run; `urithiru.eamag.me` is mapped and waiting on one DNS record.
- [x] **Keep the aviation demo.** Two unrelated datasets through one unchanged engine is
      the cheapest possible evidence that the engine is not tuned to its demo. Keep
      `scripts/prepare_tsb_demo.py` and `submission/demo-tsb-context.md`, and say in the
      description that both ran without a line of domain code.

## 1. Hard requirements

Each of these is named in the rules. A missing one is a hole in the submission.

- [ ] **Category selected** on Devpost.
- [x] **Hosted project URL or functional demo access.** Cloud Run service `urithiru-console`:
      public viewer, token-gated launcher. Awaiting the CNAME for the custom domain.
- [ ] **Demo video, 4 minutes or less.** Must show live execution and proof it runs on
      Google Cloud, in English or subtitled. `submission/video-script.md` exists but is
      written around the aviation demo — rewrite for NHANES.
- [ ] **Repository with testing access.** Private is allowed, but the judges must be able
      to get in. Two commits are unpushed (`42fda34`, `a0f61b1`). Decide public vs.
      private-plus-invite, then push.
- [x] **README with step-by-step setup.** Currently wrong in at least one place — see §3.
- [x] **Architecture diagram.** `docs/architecture.md` is prose. Judges want a picture:
      render one (Mermaid → PNG is fine) showing goal → proposal → parallel
      search/code → external, and the Cloud Run / Storage / Artifact Registry path.
- [x] **Text description** with features, technologies, data sources and learnings.
      `submission/devpost.md` exists but is entirely aviation-framed — rewrite.
- [x] **LICENSE file.** The rules talk about licence compliance and there is none in the
      repo. Apache-2.0 or MIT, decided now, not at 4:55 PM.

## 2. Hosting and auth

**The problem.** `web/src/pages/api/runs.ts` handles `POST` by spawning
`uv run urithiru run --config configs/google.local.toml` on the host. That config names
the project, the private bucket and the orchestrator job, and the host authenticates by
ADC. Deployed publicly as it stands, any visitor could upload 100 MiB, start a
twelve-step Cloud Run job billed to us, run agent-authored code with outbound network in
our project, and cancel our runs through `DELETE`. So yes: a hosted launcher needs auth.
A hosted *viewer* needs none, because the run detail pages are static files.

Three ways to satisfy "hosted project URL", cheapest first:

- **A. Read-only viewer (recommended first move, ~1–2 h).** `web/public/runs/` already
  holds the published checkpoints and event logs. Build the site static and serve it from
  Cloud Run or Firebase Hosting. Only two things stand in the way: `listRuns()` calls
  `/api/runs`, so it needs a fallback to `/runs/index.json`, and the run titles live in
  `.work/web/labels.json` on this machine, so they must be baked into the index at build
  time. No credentials leave the laptop and there is nothing to abuse.
- **B. Viewer plus token-gated launcher (~half a day on top of A).** Keep `GET` public;
  require a bearer token on `POST`/`DELETE`, read from `URITHIRU_LAUNCH_TOKEN`, with
  launching disabled outright when the variable is unset — so the default for any
  deployment is safe. Also needs the web image to carry the Python CLI (or the route
  rewritten to call the Cloud Run Jobs API directly instead of spawning `uv`), plus a
  per-IP rate limit and a much smaller upload cap than 100 MiB.
- **C. Full app behind Google sign-in / IAP.** The most defensible and the most work: IAP
  wants a load balancer, and judges then need to be allow-listed one by one. Not worth it
  before the deadline.

Recommendation: ship **A** today so the URL exists and can't be abused, then add **B** if
there is time. The video can show the launcher running locally against Cloud Run either
way — the rules ask for proof it runs on Google Cloud, not that strangers can start jobs.

## 3. Fix before anything is published

- [x] **The event log leaks the private bucket.** Every line of `events.jsonl` carries
      `"run": "gs://urithiru-<project number>/urithiru/<id>"`, and `publish_once` copies
      that file verbatim into `web/public/runs/`. `run.json` deliberately omits the
      project and bucket ("publishing a run should not publish where it ran"); the event
      log undoes that. Strip or redact the `run` field on publish.
- [x] **README claims the web app is static and needs no server.** It is an Astro SSR app
      with a Node adapter and an API route that shells out to the CLI. Fix the claim and
      the setup steps around it.
- [x] **Do not commit `2026-08-29-220346-…txt`** — a full session transcript, untracked
      and *not* gitignored. Add it to `.gitignore` before any `git add -A`.
- [x] **Re-read `.gcloudignore` and `.dockerignore`** (both new/modified) before pushing,
      and confirm `.env`, `configs/*.local.toml`, `.work/`, `runs/` are still ignored.
- [x] **Grep the docs for the project id and bucket** before the repo goes public.

## 4. Architectural Discipline & Tech Stack — 30%

The single biggest gap: **there is no test suite at all**, and this criterion explicitly
names engineering decisions, decoupling and state management. A judge who clones the repo
and finds no tests has to take the architecture on faith.

- [x] **Tests.** Not exhaustive, just the load-bearing parts: belief arithmetic and the
      30-vote posterior, deduplication and diversity selection, UCT selection and
      backpropagation, checkpoint round-trip including the new budget-growth guard,
      `safe_path` against traversal, config validation rejecting placeholders and
      non-positive budgets, and the sandbox argument construction for both runtimes
      (which is pure and needs no Docker).
- [x] **CI.** A GitHub Actions workflow running `ruff check`, `ruff format --check`,
      `pytest`, and `bun run check` in `web/`. Visible green checks are cheap credibility.
- [x] **Type checking.** `pyright` will not spawn through `uv run` (nodeenv), and outside
      the venv it reports twelve false import errors. Either pin it properly in the dev
      dependencies or drop the claim.
- [x] **Write the isolation guarantee as a testable claim.** The literature agent never
      sees the data because `DATA_STAGES` excludes it, each goal gets its own workspace
      *and* its own `HOME`, and `trustedWorkspaces` names only that one workspace. That is
      the most distinctive thing in the codebase and it deserves a test and a paragraph.
- [x] **Say plainly that the gVisor sandbox is unavailable** and the run falls back to
      in-container isolation, emitting `sandbox_unavailable`. Disclosed, it reads as
      engineering judgement; discovered by a judge, it reads as a hole.

## 5. Innovation & Operational Utility — 40%

- [x] **Land a clean 3/3 run** on NHANES. Run `68943881`, seed 11: three hypotheses
      evaluated, three external checks run, not a single stage failure.
- [x] **Then extend it rather than restart it.** Run `68943881` was extended from 3 to 30
      steps with one command and continued from its checkpoint. `urithiru resume <run> --steps 6` now
      grows a finished run's budget and continues from the checkpoint, reusing every
      completed evaluation. A run that deepens on demand is a better story than a run that
      starts over, and it is one command in the video.
- [ ] **Lead the description with the friction being removed:** a hypothesis is proposed,
      independently checked against the literature and against the data by two agents that
      cannot see each other's work, and only surprising results are sent for external
      verification. No human in the loop at any point.
- [ ] **Use the abstention as evidence, not as a failure.** On the last run the external
      agent searched Zenodo, Dryad, Figshare, Harvard Dataverse, OSF, OpenAlex and Europe
      PMC and then declined to confirm, because no open dataset carries weekday/weekend
      sleep, lab HbA1c and sedentary time together. An agent that reports "I could not
      verify this" instead of inventing a confirmation is the point.
- [ ] **Quantify the operational claim:** hypotheses evaluated per run, wall-clock, cost.

## 6. Demo & Production Readiness — 30%

- [x] **Rewrite `submission/video-script.md`** for NHANES — done, built around node 2
      (0.70 → 0.73 → 0.72 → 0.19, contradicted by a Harvard Dataverse survey).
      Originally: Beats: the dataset and what the
      agents are *not* told → launch from the UI → live parallel stages → the tree filling
      in → one finding with its four beliefs → the external agent abstaining → `gcloud run
      jobs executions list` as Cloud Run proof → resume with a larger budget. Under four
      minutes means roughly 600 words of narration; cut the architecture explanation
      before cutting live execution.
- [ ] **Never on camera:** `.env`, `configs/google.local.toml`, ADC files, signed bucket
      URLs, unreviewed agent logs.
- [ ] **Clone-to-run in one page.** Prerequisites, `uv sync`, the config to copy, the
      demo-data script, one command. Someone must be able to follow it without asking.
- [ ] **Keep `docs/offline-verification.md` current** — reproducing a finding from the
      published artifacts is exactly the "execution proof" this criterion asks for.
- [ ] **Document the failure handling** that already exists: per-stage retries with a
      clean home, cancellation, checkpoint after every node, resume that reuses completed
      evaluations.

## 7. Bonus points — up to 0.6

- [ ] **Published content, max 0.2.** One blog post on the independence design (separate
      sandboxes, separate homes, no shared data) would take an hour and is reusable as the
      Devpost description.
- [ ] **Social post, max 0.2.** One post with the tree screenshot and the demo URL.
- [ ] **An additional Google AI model.** Already using three (`gemini-3.7-flash`,
      `gemini-3.5-flash-lite`, `text-embedding-005`) — make sure the description lists
      them, since the points are for the integration being visible.

## 8. If time remains

- [x] **Extend button in the run view**, calling `resume --steps`. The CLI supports it as
      of today; the UI does not.
- [x] **Report view** in the web app for `report.md` / `report.json`, so a finished run
      ends somewhere other than a node inspector.
- [x] **Best Multimodal UX** is a separate prize and the app is text-only. Rendering the
      experiment agent's own plots in the finding panel would be the cheapest way in.
