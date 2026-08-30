---
name: urithiru-discovery
description: >-
  Autonomous scientific discovery orchestration with Urithiru. Use when you need to
  frame research questions, launch Bayesian MCTS hypothesis searches, monitor and triage
  runs, debug agent analyses, extend discovery budgets, and synthesize ranked findings over
  tabular datasets (CSV, TSV, Parquet, Excel).
---

# Urithiru Autonomous Scientific Discovery Skill

This skill guides an autonomous AI agent to orchestrate scientific discovery over tabular datasets using **Urithiru**.

Urithiru conducts a Bayesian Monte Carlo Tree Search (MCTS) where each hypothesis undergoes 4 stages:
1. **Proposal**: Initial exploratory analysis and falsifiable claim generation.
2. **Deduplication & Diversity**: Semantic duplicate elimination and embedding-based novelty selection.
3. **Data-Blind Literature Search ($P_{\text{search}}$) & Empirical Code Analysis ($P_{\text{code}}$)**: Started concurrently in separate isolated containers with private `HOME` directories.
4. **Surprisal & Independent External Verification ($P_{\text{external}}$)**: If the literature and empirical findings diverge significantly, an external agent searches repositories (Zenodo, OpenAlex, Dryad, etc.) for independent data.

---

## 1. Dataset Preparation & Framing

Before launching a run:
1. **Inspect Data Files**: Identify formats (`.csv`, `.tsv`, `.parquet`, `.xlsx`, `.xls`), column names, and sample rows.
2. **Author High-Signal Domain Metadata (`notes.md` or `context.md`)**:
   - Provide domain context, definitions for cryptic column codes, units of measurement.
   - Describe prospective confounding variables, known baseline relationships, or clinical/physical thresholds.
   - Specify the research goals and areas of interest.
3. **Budget Planning**:
   - Small exploration / smoke test: `--steps 1` to `--steps 3`
   - Standard exploration: `--steps 5` to `--steps 8`
   - Stage timeouts: `--proposal-minutes 5 --search-minutes 8 --code-minutes 10 --external-minutes 10`

---

## 2. Launching Discovery

### Local Runtime (Docker)
Ensure Docker is running and `PROJECT_ID` / `VERTEX_API_KEY` are exported if needed:
```bash
uv run urithiru run \
  --data ./data/measurements.csv \
  --metadata ./data/context.md \
  --steps 3 \
  --seed 42
```

### Google Cloud Runtime (Cloud Run Jobs & Cloud Storage)
Use your configured profile:
```bash
uv run urithiru run \
  --config configs/google.toml \
  --data ./data/measurements.csv \
  --metadata ./data/context.md \
  --steps 5 \
  --seed 42
```
*Note: This prints a reference `gs://bucket/prefix/<run-id>`.*

---

## 3. Monitoring & Real-Time Telemetry

### Check Status
```bash
uv run urithiru status <RUN_REF>
```
Output reports status (`running`, `completed`, `exhausted`, `failed`), completed vs requested steps, error message, and live execution ID.

### Follow Live Events
```bash
uv run urithiru logs <RUN_REF> --follow
```
Events emitted:
- `stage_started` / `stage_completed` / `stage_failed`
- `proposals_ready`
- `hypothesis_selected`
- `hypothesis_evaluated` (reports 4-hop beliefs: `p_param`, `p_search`, `p_code`, `p_external`, reward, verdict)

### Publish to UI Visualizer
```bash
uv run urithiru publish <RUN_REF> --watch
```
Then view the interactive tree and findings at `http://localhost:4321` (`cd web && bun run dev`).

---

## 4. Anomaly Detection & Scientific Triage

### Audit the Run Programmatically
Run the built-in audit script:
```bash
python3 skills/urithiru-discovery/scripts/audit_run.py <RUN_DIR_OR_PATH>
```

### Key Diagnostic Heuristics

1. **Falsification is Valid Science, Not a Failure**:
   - If `empirical_support = false` and `direction_supported = false`, the data cleanly refuted the proposed hypothesis. This is high-value information that updates the Bayesian tree and guides subsequent branches.
2. **External Abstention is Honest Science**:
   - If the external stage reports `did not answer` or abstained without finding matching co-measured datasets across Zenodo/OpenAlex/Dryad, treat this as a signal of scientific rigor (not an error).
3. **Debugging Agent Analysis Failures**:
   - If `execution_success = false`, inspect `<run>/sandbox_artifacts/<goal_id>/agent.log` and `result.json`.
   - Common causes: Missing package in script, incorrect column name reference, unhandled `NaN` values in pandas, or timeout.
4. **Data Blindness Verification**:
   - Confirm `<run>/sandbox_artifacts/search_<node>/` contains only `goal.txt` and no data files.

---

## 5. Iterative Deepening (Extending a Run)

When promising discoveries emerge, **never restart from scratch**. Deepen the tree by raising `--steps`:
```bash
uv run urithiru resume <RUN_REF> --steps 6
```
- The engine loads the checkpoint, reuses all completed evaluations and caches, and spends the 3 new steps exploring deeper or more novel branches.
- *Rule: The budget can only grow (monotonically non-decreasing invariant).*

---

## 6. Synthesis & Report Export

Export the complete ranked Bayesian report and all experimental artifacts:
```bash
uv run urithiru export <RUN_REF> --output ./discovery-report
```

This generates:
- `report.md`: Markdown summary ranked by information gain reward.
- `report.json`: Machine-readable array of all findings with full metrics, diagnostics, and literature references.
- `sandbox_artifacts/`: Generated Python scripts, logs, intermediate files, and matplotlib figures.

### Presenting Findings to the User
When summarizing discoveries for the user, include:
1. **The Core Claim**: The exact falsifiable proposition tested.
2. **The 4-Hop Bayesian Move**: $P_{\text{param}} \to P_{\text{search}} \to P_{\text{code}} \to P_{\text{external}}$.
3. **Empirical Evidence**: Effect sizes, confidence intervals, p-values, sample sizes, and threat checks conducted.
4. **Literature & Independent Context**: Key citations, corroborating or contradicting external evidence.
5. **Next Steps**: Recommended branch extensions or follow-up analyses.
