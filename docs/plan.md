<https://allthingsagentichackathon.devpost.com/> How can I productionize this to fix for a hackathon above?

> **Upload a scientific dataset → Urithiru autonomously discovers, empirically tests, independently cross-checks, and ranks non-obvious scientific hypotheses.**

That is an unusually strong Taskmaster submission because the agent does real work rather than producing text.

## 1. The hackathon version of Urithiru

Call the product something understandable such as **Urithiru — Autonomous Research Analyst**.

The user experience should be only:

1. Upload CSV/Parquet.
2. Optionally enter 1–2 sentences describing the dataset.
3. Choose a small research budget: `Fast / Standard / Deep`.
4. Click **Start Discovery**.
5. Leave the page if desired.
6. Come back to a run showing:

   * dataset health check
   * hypotheses proposed
   * analysis code executed
   * empirical evidence
   * literature/search belief
   * independent external verification where available
   * ranked discoveries
   * downloadable evidence/artifacts

The differentiating sentence should be:

> **Most AI research assistants suggest hypotheses. Urithiru actually executes the experiments and attempts to falsify surprising results against independent data.**

That maps directly onto the Taskmaster requirement for completing a complicated workflow rather than behaving as a chatbot. ([All Things Agentic Hackathon][1])

---

# 2. Change the architecture, not the scientific core

Your current architecture already contains most of the interesting backend logic:

* autonomous EDA
* candidate generation/deduplication
* MCTS
* empirical code verification
* `P_param → P_search → P_code → P_external`
* external-data search
* checkpointing
* bounded parallelism
* recovery
* structured evidence artifacts

Those are useful hackathon features.

What should disappear from the hackathon story is:

* AutoDiscovery parity
* paper reproduction
* H21/H24/H26/H41/H49 terminology
* benchmark ablations
* target belief modes
* scientific-paper arguments about whether KL is the right reward
* legacy evaluation runners

A judge should not need to know any of this.

---

# 3. Replace the local runtime with this

```text
                         ┌───────────────────────┐
                         │       Web UI          │
                         │ upload + live results │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │ Cloud Run API         │
                         │ create/status run     │
                         └───────┬───────┬───────┘
                                 │       │
                           files │       │ state
                                 ▼       ▼
                     ┌──────────────┐  ┌───────────┐
                     │Cloud Storage │  │ Firestore │
                     └──────────────┘  └─────▲─────┘
                                              │
                              start run       │ progress
                                     ▼        │
                      ┌────────────────────────────┐
                      │ Cloud Run Job              │
                      │ Urithiru orchestrator      │
                      │                            │
                      │ Google ADK                 │
                      │ Gemini 3.5 / Vertex AI     │
                      │ MCTS                       │
                      └────────────┬───────────────┘
                                   │
                      sibling hypothesis evaluations
                                   │
                   ┌───────────────┼───────────────┐
                   ▼               ▼               ▼
             ┌───────────┐   ┌───────────┐   ┌───────────┐
             │Cloud Run  │   │Cloud Run  │   │Cloud Run  │
             │Verifier   │   │Verifier   │   │Verifier   │
             │Job        │   │Job        │   │Job        │
             └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
                   │               │               │
                   └───────────────┼───────────────┘
                                   ▼
                      Gemini + empirical execution
                      + optional external evidence
                                   │
                                   ▼
                        Firestore / Cloud Storage
```

This is far stronger for the hackathon than your current:

```text
Python process
  ↓
local Docker / OrbStack
  ↓
AGY container
```

Cloud Run Jobs are particularly appropriate because they are explicitly designed for run-to-completion workloads, support retries/timeouts, parallel tasks, and Cloud Logging. ([Google Cloud][2])

---

# 4. I would use Google ADK even if AGY already qualifies

The hackathon mandates all three:

* Gemini 3.5+ via Gemini API or Vertex AI
* Google ADK, GenAI SDK, Antigravity SDK, or GenKit
* Google Cloud infrastructure. ([All Things Agentic Hackathon][3])

You already have Vertex/Gemini.

Your AGY setup may correspond to Antigravity, but I would **make Google ADK explicit in the architecture** rather than leave any eligibility ambiguity.

You do not need to rewrite Urithiru around ADK.

Make an ADK root agent/orchestrator whose tools call your existing components:

```text
ResearchAgent
├── inspect_dataset()
├── propose_hypotheses()
├── verify_hypothesis()
├── search_external_evidence()
└── summarize_discoveries()
```

Behind those tools, retain your existing Python.

This gives judges an obvious:

> **Google ADK orchestrates Gemini-powered scientific agents; Urithiru supplies the search and verification engine.**

---

# 5. Most important refactor: kill nested Docker

This is currently your biggest productionization problem.

Your `agent.py` starts separate Docker/OrbStack containers.

Don't try Docker-in-Docker on Cloud Run.

Instead:

### Current

```text
engine.py
    ↓
launch Docker
    ↓
AGY worker
    ↓
result.json
```

### Hackathon

```text
engine.py
    ↓
submit Cloud Run verification job
    ↓
worker.py --run-id=X --hypothesis-id=Y
    ↓
result.json → GCS/Firestore
```

You actually preserve the nice security story:

> Each scientific experiment executes in an isolated ephemeral Cloud Run container.

And that directly addresses the judging criterion asking whether tools are isolated and appropriately scoped. ([All Things Agentic Hackathon][1])

---

# 6. Add only three persistence objects

Don't port the entire current output directory abstraction.

### Firestore

`runs/{run_id}`

```json
{
  "status": "running",
  "stage": "verifying",
  "dataset_name": "...",
  "started_at": "...",
  "hypotheses_total": 8,
  "hypotheses_completed": 5
}
```

`runs/{run_id}/hypotheses/{id}`

```json
{
  "claim": "...",
  "status": "complete",
  "p_search": 0.31,
  "p_code": 0.86,
  "p_external": 0.72,
  "reward": 0.48,
  "empirical_support": true
}
```

### Cloud Storage

```text
runs/<run_id>/
    input/dataset.csv
    hypotheses/<id>/analysis.py
    hypotheses/<id>/metrics.json
    hypotheses/<id>/external/
    report.json
```

### Cloud Logging

Every step:

```text
run=123 agent=eda event=started
run=123 hypothesis=H3 event=verification_started
run=123 hypothesis=H3 event=code_executed
run=123 hypothesis=H3 event=external_dataset_found
```

This gives you excellent screenshots/video material.

---

# 7. Build a very small UI

Do **not** build a research IDE.

One screen is sufficient.

### Top

```text
URITHIRU

Turn a dataset into independently tested scientific discoveries.

[ Upload dataset.csv ]

Dataset description
[ Measurements of urban particulate pollution ... ]

Discovery budget
[ Fast: 3 hypotheses ▼ ]

[ Run autonomous discovery ]
```

### During execution

```text
Discovery running                            4 / 6 complete

✓ Dataset validated
✓ 17 candidate hypotheses generated
✓ 9 duplicates removed
● Testing H4
● Searching independent evidence for H2

─────────────────────────────────────────────

H2  Copper/Mo ratio tracks non-exhaust traffic emissions

Literature prior              34%
Seed data                     87%
Independent dataset           76%

✓ empirically supported
✓ independently testable

View experiment →
```

### Final

```text
3 discoveries worth investigating

1. ...
   Seed evidence       Strong
   External evidence   Replicated

2. ...
   Seed evidence       Strong
   External evidence   Contradicted

3. ...
   Seed evidence       Moderate
   External evidence   No suitable independent data
```

The **contradicted** outcome is important. It makes the system look like verification rather than an AI hype generator.

---

# 8. The demo matters more than another experiment

The hackathon organizers explicitly say judges may never execute the project themselves, and 30% of the score is demo/production readiness. ([All Things Agentic Hackathon][4])

Design a **demo mode**:

```bash
DISCOVERY_BUDGET=3
CANDIDATES_PER_STEP=3
EXTERNAL_VERIFICATION_LIMIT=1
```

Aim for an actual cloud execution sufficiently short to show live.

Use one dataset you've already tested and know produces comprehensible discoveries.

I would probably use **Medellín PM2.5**, because:

* domain is immediately understandable;
* hypotheses sound scientific;
* you already have external-verification machinery;
* “found independent evidence / couldn't find independent evidence” is visually understandable.

Do not show a 30-node MCTS.

For the hackathon:

> three completed experiments beat fifty invisible nodes.

---

# 9. Four-minute video

I would script it almost exactly like this.

### 0:00–0:25 — friction

> Scientific datasets contain potential discoveries, but exploring one properly means inspecting the data, developing hypotheses, writing analyses, checking the literature, running statistical tests, and then determining whether a result survives independent evidence.

Show this as a simple workflow diagram.

### 0:25–0:40 — solution

> Urithiru is an autonomous scientific discovery agent. Give it a dataset and it carries out that workflow itself.

### 0:40–2:20 — live proof of action

Upload dataset.

Click Run.

Show:

```text
Dataset inspection
        ↓
Candidate generation
        ↓
Hypothesis selected
        ↓
Python experiment running
        ↓
Unexpected result
        ↓
Independent dataset search
        ↓
External test
```

Switch briefly to Cloud Run/Cloud Logging so they can visibly see it is executing in Google Cloud.

The rules specifically require evidence of the backend running on Google Cloud in the video. ([All Things Agentic Hackathon][3])

### 2:20–3:10 — result

Open one hypothesis.

Show:

```text
P_search    0.29
P_code      0.84
P_external  0.71
```

Then open the generated analysis/evidence.

### 3:10–3:40 — architecture

Show the architecture above:

```text
ADK
  ↓
Gemini 3.5
  ↓
Cloud Run orchestration
  ↓
isolated Cloud Run experiment workers
  ↓
Firestore + Cloud Storage
```

Mention retry/resume/isolation.

### 3:40–4:00 — punchline

> Urithiru doesn't just brainstorm scientific hypotheses. It spends compute testing them and actively searches for evidence that could prove itself wrong.

End.

---

# 10. What I would change in your repository

Something roughly like:

```text
src/urithiru/
    core/
        engine.py
        tree.py
        beliefs.py
        models.py

    agents/
        adk_agent.py
        eda.py
        verifier.py
        external.py

    cloud/
        orchestrator.py
        worker.py
        firestore.py
        storage.py

    api/
        main.py

web/
    ...

Dockerfile.api
Dockerfile.worker
cloudbuild.yaml
deploy.sh
```

And add:

```bash
uv run urithiru serve
uv run urithiru worker --run-id ...
```

Ironically, your README currently identifies the lack of a public CLI as a weakness.  For the hackathon I'd add the CLI, but only because it makes local reproduction trivial—not because the product itself needs one.

---

# 11. Do not spend time on these

Before August 31, I would explicitly **not** do:

| Work                             | Hackathon value |
| -------------------------------- | --------------: |
| More NeurIPS benchmark runs      |        Very low |
| AutoDiscovery parity             |            Zero |
| More belief representations      |            Zero |
| Better MCTS reward               |             Low |
| Full H49 census integration      |             Low |
| Remote arbitrary dataset catalog |             Low |
| Mem0/ICL baseline port           |            Zero |
| Perfect external cost policy     |             Low |
| Web UI                           |   **Very high** |
| Cloud Run deployment             |    **Critical** |
| ADK integration                  |    **Critical** |
| Live progress/state              |        **High** |
| Architecture diagram             |    **Critical** |
| Excellent 4-minute demo          |    **Critical** |
| One reliable end-to-end example  |    **Critical** |

Your own current project description correctly labels several of those research features as incomplete.  None of them need fixing for Devpost.

---

# 12. Priority order from now to submission

Given the **August 31, 5:00 PM PDT** deadline, I would do it in exactly this order. ([All Things Agentic Hackathon][1])

**P0 — get eligible**

1. Verify git provenance against August 3.
2. Add explicit Google ADK integration.
3. Ensure Gemini 3.5+ model configuration.
4. Deploy one component to Google Cloud.

**P1 — make it actually run**
5. Make one Cloud Run Job execute one existing Urithiru run.
6. Replace nested Docker verifier with Cloud Run worker.
7. Store run state in Firestore.
8. Store dataset/artifacts in GCS.

**P2 — make it judgeable**
9. Add `POST /runs`.
10. Add `GET /runs/{id}`.
11. Build tiny web UI.
12. Run one known-good end-to-end example.

**P3 — make it look productionized**
13. retries
14. timeout handling
15. explicit run states
16. error states
17. per-run isolation
18. Cloud Logging
19. clean README
20. architecture diagram

**P4 — submission**
21. Record video.
22. Devpost description.
23. public repo/frozen submission branch.
24. reproducible setup instructions.
25. screenshots.

Only after all that would I touch the science.

---

## One thing I would be careful about

The rules say:

> projects must be newly created during the August 3–31 Submission Period, while pre-existing incorporated work must be disclosed. ([All Things Agentic Hackathon][5])

So don't frame the submission as:

> “I built Urithiru, my scientific discovery engine.”

unless the relevant code genuinely dates from the contest period.

The safer and probably stronger framing where needed is:

> **“For the All Things Agentic Hackathon, I built the production agent application and Google Cloud architecture that turns my research components into an autonomous end-to-end scientific discovery workflow.”**

Then explicitly disclose whatever existed beforehand.

---

### The target

If you get to this state:

```text
CSV upload
  ↓
Cloud-hosted asynchronous run
  ↓
Gemini/ADK generates hypotheses
  ↓
real Python analyses execute in isolated workers
  ↓
independent data is searched/tested
  ↓
live UI updates
  ↓
ranked evidence-backed discoveries
```

I think Urithiru becomes a **very credible Taskmaster / Best Architectural Design submission**. It matches the hackathon unusually well; the missing work is mostly **product surface + cloud execution**, not more research. The organizers are explicitly weighting Innovation/Utility 40%, Architecture 30%, and Demo/Production Readiness 30%. ([All Things Agentic Hackathon][1])

Also do the easy bonus points after the core submission: a short public build post and a LinkedIn/X post are worth up to **+0.4 combined**; additional Google AI models can add more, but I would not add Gemma until the core demo is reliable. ([All Things Agentic Hackathon][1])

[1]: https://allthingsagentichackathon.devpost.com/rules?utm_source=chatgpt.com "All Things Agentic Hackathon: Ready, Set, Agent! Build next-generation agents that run in the background, handle the heavy lifting of massive datasets, and automate complex workflows asynchronously. - Devpost"
[2]: https://cloud.google.com/run/docs/create-jobs?utm_source=chatgpt.com "Create jobs  |  Cloud Run  |  Google Cloud"
[3]: https://allthingsagentichackathon.devpost.com/ "All Things Agentic Hackathon: Ready, Set, Agent! Build next-generation agents that run in the background, handle the heavy lifting of massive datasets, and automate complex workflows asynchronously. - Devpost"
[4]: https://allthingsagentichackathon.devpost.com/updates?utm_source=chatgpt.com "All Things Agentic Hackathon: Ready, Set, Agent! Build next-generation agents that run in the background, handle the heavy lifting of massive datasets, and automate complex workflows asynchronously. - Devpost"
[5]: https://allthingsagentichackathon.devpost.com/rules "All Things Agentic Hackathon: Ready, Set, Agent! Build next-generation agents that run in the background, handle the heavy lifting of massive datasets, and automate complex workflows asynchronously. - Devpost"
