# Four-minute demo script

Target length: 3:45–3:55. Record at 1440p or higher and export 1080p. Keep the cursor
slow, terminal text large and every browser zoom level at 100%.

## 0:00–0:25 — the problem

**Visual:** `assets/title.png`, then a quick sequence of the five Canadian TSB tables.

**Narration:**

> Aviation authorities publish thousands of coded incident records, but determining
> which apparent safety patterns are real—and whether they generalize beyond one
> country—still takes weeks of specialist work.

## 0:25–0:47 — the product

**Visual:** terminal with the single `urithiru run` command, then the returned `gs://`
run identifier and Cloud Run execution name.

**Narration:**

> Urithiru is an autonomous safety-signal discovery agent. I give it five linked
> Canadian occurrence tables and their dictionary. The CLI stages the immutable inputs,
> starts one Cloud Run Job, and returns while discovery continues in the background.

## 0:47–1:35 — real work, live

**Visual:** the minimal run page while proposal begins. Let the live log add at least
two lines without refreshing the page. Cut to `assets/cloud-run-execution.png`, showing
the Google project, region, execution name and running task.

**Narration:**

> This is not a fixture. The static page is reading the job's checkpoint and live event
> log. Proposal inspects 20,301 unique Canadian aviation occurrences from 2005 through
> 2024 and proposes falsifiable safety signals. The backend is running on Google Cloud;
> every line is mirrored to
> Cloud Storage as it happens, independently of the slower checkpoints.

## 1:35–2:18 — the core architectural idea

**Visual:** `assets/architecture.png`. Highlight literature, experiment, then external.

**Narration:**

> The important part is the split. Literature and experiment start simultaneously in
> different workspaces and with different private agent homes. Literature receives the
> schema but never the dataset. Experiment receives the dataset but never the literature
> conclusion. Their disagreement therefore measures a real evidence conflict, not one
> model rationalizing its previous answer. When that conflict is informative, a fourth
> agent crosses into the separate U.S. NTSB census and tries to prove the signal wrong.

## 2:18–3:12 — the finding

**Visual:** completed Canadian safety signal. Pause on the four-point belief chart, verdict,
plain-language summary and independent source. Expand the experiment metrics briefly.

**Narration template:**

> Here is the completed safety signal: **[insert the exact Canadian claim]**. The belief moves
> from **[prior]** with no evidence, to **[literature]** from published work, to
> **[experiment]** after code runs on the seed data, and finally **[external]** on an
> independent source. The system reports **[replicated / contradicted / no independent
> data]**. I can inspect the rationale, generated metrics, stdout, papers and external
> dataset rather than trusting a summary.

## 3:12–3:38 — audit and reliability

**Visual:** bucket artifact listing, then the page's tree and final `run_finished` line.

**Narration:**

> Everything is retained as plain files: original inputs, an atomic MCTS checkpoint,
> ordered JSONL events, generated code, source captures and one immutable evaluation per
> finding. If the process stops, it resumes from the checkpoint instead of repeating
> completed model calls.

## 3:38–3:55 — close

**Visual:** return to the architecture title or completed finding.

**Narration:**

> Urithiru does not just generate hypotheses. It creates two independent views of a
> claim, spends compute testing their disagreement, and then searches for evidence that
> could prove itself wrong.

## Recording checklist

- Show the final Canadian TSB execution in Google Cloud, not only local UI.
- Keep `sandbox_unavailable · isolation=container` visible or mention it; do not imply
  Preview gVisor was enabled.
- Never show project credentials, `.env`, ADC files, private bucket URLs with signed
  query parameters, or unreviewed full agent logs.
- Replace all bracketed finding placeholders after the Canadian run completes.
- End below four minutes; do not speed up speech to fit.
