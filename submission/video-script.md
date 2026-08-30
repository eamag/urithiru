# Four-minute demo script

**Format:** one continuous screen recording, no cuts. Terminal on the left, browser on the
right at `urithiru.eamag.me`. A single unbroken take is itself the argument that this is
live — take advantage of that and never cut away.

Target 3:40–3:55. Record at 1440p or higher, export 1080p. Terminal font large, browser
zoom 100%, cursor slow.

Every figure below is real, from run `68943881` (seed 11). Only the two `[…]` marks need
filling once the 30-step run lands.

---

## Before you hit record

- Have the nine NHANES files ready in a Finder window to drag in, but the terminal fresh so
  the download runs on camera.
- Log in to the console once beforehand so the token is already in the tab — or type it on
  camera, the field is masked.
- Ask me to raise `URITHIRU_LAUNCH_LIMIT` first: the deployed service allows 4 launches an
  hour, and several takes will exhaust it.
- Have the 30-step discovery open in a second browser tab, ready to switch to.

---

## 0:00–0:30 — the data arrives, on camera

**Left:** `uv run python scripts/prepare_nhanes_demo.py`. Let it download from `cdc.gov`
live. Talk over it. When it finishes, `ls` the directory and `head -3 demographics.csv`.

**Narration:**

> This is pulling the U.S. health survey straight from the CDC — eight tables, about twelve
> thousand people, plus the official codebook. It's public domain, and it's the only thing
> the system is about to get. No analysis plan, no suggested variables, no hint about what
> to look for.

## 0:30–1:05 — launch it

**Right:** the console. Drag the nine files in, give it a name, leave the budget at three,
enter the token, launch. It appears in the list, queued.

**Narration:**

> I hand it the files and ask for three hypotheses. That's the whole interface. It stages
> the inputs, starts a job on Google Cloud, and hands the page back — the run continues
> whether or not I'm watching.

## 1:05–1:25 — prove it's actually on Google Cloud

**Left:** `gcloud run jobs executions list --region us-central1`. The new execution is at
the top, running.

**Narration:**

> There it is as a Cloud Run execution. The orchestrator, the four agents, and every
> sandbox all live in that one job.

## 1:25–2:10 — switch to the deep run and explain the machine

**Right:** second tab, the 30-step discovery. Show the tree. Open a node mid-flight so the
parallel literature and experiment stages are both visible.

**Narration:**

> While that one warms up, here's the same thing after thirty hypotheses. Each node is one
> claim, tested four ways.
>
> The part that matters is the split. The literature agent gets the schema and never the
> data. The experiment agent gets the data and never the literature's conclusion. Separate
> sandboxes, separate home directories, no shared state — so when they disagree, that's two
> independent readings of the world conflicting, not one model agreeing with itself.
>
> And when the disagreement is worth spending on, a fourth agent goes looking for a dataset
> somebody else collected, and tries to prove the finding wrong.

## 2:10–3:10 — the finding

**Right:** node 2. Sit on the belief chart. Then open the external panel with the DOI. Open
the experiment metrics briefly.

**Narration:**

> Here's one. *Vigorous exercise weakens the link between sitting time and depression.*
>
> Before any evidence: 0.70. The published literature agrees — 0.73. Then the agent writes
> and runs its own analysis on the NHANES data: five and a half thousand complete cases,
> interaction coefficient minus 0.017, p equals 0.015. That agrees too — 0.72.
>
> Then the external agent goes and finds an independent survey on Harvard Dataverse. Seven
> hundred and ninety-six people, collected by someone else, nobody pointed it there. Same
> interaction: plus 0.012, p equals 0.63. No moderation at all. The belief drops to 0.19.
>
> Three sources agreed. The fourth disagreed — and that's the one that would have cost a
> researcher a month to find.

## 3:10–3:35 — back to the live run, and deepening

**Right:** first tab. The new run now has proposals, or a first node evaluating.

**Narration:**

> The run I started four minutes ago has already proposed its hypotheses and started
> testing. Everything it produces is kept as plain files — the inputs, the checkpoint, the
> code the agent actually wrote, one immutable record per finding. And a finished run isn't
> finished: raise its budget and it continues from the checkpoint instead of starting over.
> That thirty-step tree began as a three-step run and grew with one command.

## 3:35–3:50 — close

**Right:** the completed tree.

**Narration:**

> Urithiru doesn't just propose hypotheses. It builds two independent views of each one,
> spends real compute on their disagreement, and then goes looking for the evidence that
> would prove itself wrong.

---

## Recording checklist

- One take, no cuts. If the download or launch is slow, keep talking — dead air is
  cheaper than losing the "this is live" argument.
- The Cloud Run executions list must appear on screen. The rules ask for proof it runs on
  Google Cloud, not just that it runs.
- Keep `sandbox_unavailable · isolation=container` visible in the log, or say it out loud.
  Preview gVisor is not enabled and the video must not imply otherwise.
- Never on camera: `.env`, `configs/google.local.toml`, ADC files, the launch token in
  plain text, signed bucket URLs, raw agent logs. The console's own pages are safe —
  published artifacts name no project and no bucket.
- Fill the two `[…]` marks after the 30-step run lands: final node count, and whether any
  later finding replicated rather than contradicted.
- Finish under four minutes. If you're over, cut the isolation explanation down to one
  sentence — never cut the live launch or the finding.
