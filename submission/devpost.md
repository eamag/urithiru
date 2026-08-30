# Urithiru

**Tagline:** An autonomous aviation safety-signal engine that tests Canadian patterns
and then crosses the border to see which ones survive.

## Inspiration

Aviation authorities publish thousands of coded incident records, but determining
which apparent safety patterns are real—and whether they generalize beyond one
country—still takes weeks of specialist work. Generating a plausible explanation is
the easy part. The difficult part is keeping literature expectations separate from
empirical analysis, executing a valid test over messy linked tables, preserving the
audit trail, and checking whether the signal survives an independent reporting system.

Urithiru turns that workflow into one resumable background job.

## What it does

Give Urithiru CSV, TSV, Parquet or Excel files plus optional metadata. For each search
step it:

1. inspects the data and proposes falsifiable hypotheses;
2. removes duplicate candidates and elicits an evidence-free prior;
3. starts a literature agent and a Python experiment agent concurrently;
4. keeps the seed data out of the literature workspace and the literature conclusion
   out of the experiment workspace;
5. measures how far the empirical result moved the literature belief;
6. when the disagreement is informative, searches for independent data and tests the
   claim again; and
7. updates a Monte Carlo search tree and ranks completed safety signals.

The demo gives it five linked 2005-2024 tables from the Transportation Safety Board of
Canada: occurrences, aircraft, flight events/phases, injuries and survivability. The
U.S. NTSB aviation census is held out for the external stage; it is never part of the
seed bundle.

The result is not merely a paragraph. Every run retains its hypotheses, category-count
beliefs, generated code, stdout, metrics, cited sources, independent-data result,
checkpoints and ordered event log.

## How it is built

Urithiru is a Python 3.12 package with a deliberately small boundary:

- the Antigravity CLI performs the proposal, literature, experiment and external-data
  work;
- Gemini 3.7 Flash performs agent reasoning and prior elicitation, Gemini 3.5 Flash
  Lite assists deduplication, and `text-embedding-005` supplies semantic similarity;
- one Cloud Run Job owns the resumable discovery loop;
- Cloud Storage holds the original inputs, plain JSON checkpoints, live JSONL events
  and complete agent artifacts; and
- a static Astro/Svelte page renders those files directly, without a database, API
  server or browser-held cloud credentials.

The analysis image also includes `mdbtools`, allowing the external agent to extract the
NTSB's official Microsoft Access release rather than substituting a scraped mirror.

Search and experiment start at the same moment in separate workspaces and private CLI
homes. The separation is scientific, not cosmetic: their disagreement is meaningful
because neither process can inspect the other's answer.

The verified deployment authenticates through the Cloud Run service account using
Application Default Credentials. No Gemini API-key secret is injected. Cloud Run's
Preview gVisor launcher was unavailable in the project, so the accepted runs used the
documented container fallback and logged that weaker isolation explicitly.

## What was challenging

The most subtle failure was not statistical. The agent CLI stores scratch results under
its home directory. Initially all four stages shared one home, allowing a later agent to
see an earlier result even though the dataset was absent from its workspace. Urithiru
now assigns one home per goal as well as one workspace per goal.

Live progress had a similar two-layer trap. Uploading `events.jsonl` only with a
checkpoint left observers silent throughout a multi-minute agent stage. Mirroring each
line fixed the bucket, but the web page also had to invalidate its cached run when the
publisher advanced even if the checkpoint timestamp did not.

## Accomplishments

- A 77.70 MiB, five-table Canadian government dataset passes the real input boundary
  with 20,301 unique 2005-2024 occurrences and explicit table-grain validation.
- The official U.S. NTSB holdout was preflighted as a 95.6 MB download containing a
  555 MB Access database, and the deployed analysis image can extract it directly.
- Real Cloud Run discoveries completed proposal and concurrent literature/experiment;
  a separate accepted run also completed independent-data verification end to end.
- Live events reached Cloud Storage before the next checkpoint.
- The page recomputes the four displayed beliefs from the engine's stored category
  counts; its result matches the Python calculation to floating-point precision.
- Runs resume from ordinary JSON checkpoints and reuse completed evaluations, model
  decisions and embeddings.

## What we learned

Agent independence requires inspecting every state channel: files, prompts,
environment, credentials and tool-specific scratch space. It is not established by a
role description alone. We also learned that a plain-file architecture can provide a
strong audit trail when ownership, atomic checkpoints and live-event transport are
explicit.

## What's next

- qualify the Preview gVisor path once ADC can cross its sandbox boundary;
- exercise live cancellation/resume and negative IAM tests as routine acceptance;
- add more operator-reviewed demonstration datasets; and
- export each reviewed signal as a compact dossier for a safety analyst; and
- study how reliably belief movement predicts cross-country replication.

## Reproduction

```sh
git clone https://github.com/eamag/urithiru.git
cd urithiru
uv sync --locked
uv run urithiru --help
```

Google Cloud provisioning and the exact service-account boundary are documented in
`docs/google.md`. Local Docker operation is documented separately in `docs/local.md`.

## Links

- Source: https://github.com/eamag/urithiru
- Demo video: TODO

## Provenance disclosure

The scientific MCTS engine, belief analysis and prompt contracts predate the submission
period. The standalone package, split-agent execution, per-goal state isolation,
Google Cloud runtime, CLI, live event transport and static run viewer are the new
application work. The repository records this lineage in `docs/provenance.md` and Git
history. Third-party datasets remain under their original terms. The Canadian seed is
licensed under the Open Government Licence - Canada; the independent U.S. records come
from the National Transportation Safety Board.
