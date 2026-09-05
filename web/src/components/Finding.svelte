<script lang="ts">
  import { formatNats, verdict } from "../lib/run";
  import type { CheckpointNode } from "../lib/types";
  import Beliefs from "./Beliefs.svelte";

  let { node, rank }: { node: CheckpointNode; rank: number } = $props();

  let evaluation = $derived(node.evaluation!);
  let found = $derived(evaluation.literature.findings.all_papers_found);
  let papers = $derived(Array.isArray(found) ? (found as Record<string, unknown>[]) : []);
  let rawMetrics = $derived(evaluation.experiment.metrics);
  let metrics = $derived(Object.entries(rawMetrics));

  interface PlotItem {
    name: string;
    src: string;
  }

  let plots = $derived.by<PlotItem[]>(() => {
    const list: PlotItem[] = [];
    for (const [k, v] of metrics) {
      if (typeof v === "string") {
        if (v.startsWith("data:image/") || /\.(png|jpe?g|svg|webp)$/i.test(v)) {
          list.push({ name: k.replace(/_/g, " "), src: v });
        }
      } else if (Array.isArray(v)) {
        for (const item of v) {
          if (typeof item === "string" && (item.startsWith("data:image/") || /\.(png|jpe?g|svg|webp)$/i.test(item))) {
            list.push({ name: k.replace(/_/g, " "), src: item });
          }
        }
      }
    }
    return list;
  });

  let selectedPlot = $state<PlotItem | null>(null);

  function round(value: unknown): string {
    if (typeof value === "number") {
      if (value !== 0 && (Math.abs(value) < 1e-3 || Math.abs(value) >= 1e6)) return value.toExponential(2);
      return String(Math.round(value * 1e4) / 1e4);
    }
    return value !== null && typeof value === "object" ? JSON.stringify(value) : String(value);
  }
</script>

<article class="finding">
  <header>
    <span class="rank">{String(rank).padStart(2, "0")}</span>
    <h3>{node.claim}</h3>
  </header>

  <div class="verdicts">
    <span class="tag" class:yes={evaluation.experiment.empirical_support}>
      {evaluation.experiment.empirical_support ? "agent reported support" : "agent reported refutation"}
    </span>
    <span class="tag quiet">{verdict(evaluation)}</span>
    <span class="tag quiet">reward {(evaluation.reward + evaluation.external_value).toFixed(3)}</span>
  </div>

  <Beliefs {evaluation} />

  <p class="summary">{evaluation.experiment.summary}</p>

  {#if plots.length > 0}
    <div class="plots-container">
      <h4>Experimental Plots & Visualizations</h4>
      <div class="plots-grid">
        {#each plots as plot}
          <button
            type="button"
            class="plot-card"
            onclick={() => (selectedPlot = plot)}
          >
            <img src={plot.src} alt={plot.name} class="plot-img" />
            <figcaption class="plot-caption">{plot.name}</figcaption>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if selectedPlot}
    <div
      class="modal-backdrop"
      role="button"
      tabindex="0"
      onclick={() => (selectedPlot = null)}
      onkeydown={(e) => e.key === "Escape" && (selectedPlot = null)}
    >
      <div class="modal-content" role="document">
        <button
          type="button"
          class="modal-close"
          onclick={() => (selectedPlot = null)}
        >
          ✕ Close
        </button>
        <img src={selectedPlot.src} alt={selectedPlot.name} class="modal-img" />
        <p class="modal-title">{selectedPlot.name}</p>
      </div>
    </div>
  {/if}

  <details>
    <summary>literature · {papers.length} papers, never saw the data</summary>
    <p>{evaluation.literature.rationale}</p>
    <ul class="papers">
      {#each papers as paper}
        <li>
          <span>{paper.title ?? "untitled"}</span>
          <small>{paper.journal ?? ""} {paper.year ?? ""} {paper.doi ? `· ${paper.doi}` : ""}</small>
        </li>
      {/each}
    </ul>
  </details>

  <details open={plots.length === 0}>
    <summary>experiment · {metrics.length} metrics, wrote and ran its own analysis</summary>
    <p>{evaluation.experiment.rationale}</p>
    <dl class="metrics">
      {#each metrics as [name, value]}
        <div><dt title={name}>{name.replace(/_/g, " ")}</dt><dd>{round(value)}</dd></div>
      {/each}
    </dl>
    {#if evaluation.experiment.stdout}<pre>{evaluation.experiment.stdout}</pre>{/if}
  </details>

  <details>
    <summary>
      external result · {evaluation.external ? evaluation.external.source : "did not answer"}
    </summary>
    {#if evaluation.external}
      <p>{evaluation.external.rationale}</p>
    {:else}
      <p class="dim">{evaluation.external_error ?? "The belief did not move enough to be worth checking."}</p>
    {/if}
  </details>

  <details>
    <summary>surprisal · how far the data moved the belief, higher is more surprising</summary>
    <dl class="metrics">
      <div>
        <dt title="KL(code ‖ search), in nats">surprisal — data vs literature</dt>
        <dd>{formatNats(evaluation.surprisal.kl_code_search)}</dd>
      </div>
      <div>
        <dt title="KL(search ‖ prior), in nats">literature vs no evidence</dt>
        <dd>{formatNats(evaluation.surprisal.kl_search_param)}</dd>
      </div>
      <div>
        <dt title="KL(code ‖ prior), in nats">data vs no evidence</dt>
        <dd>{formatNats(evaluation.surprisal.kl_code_param)}</dd>
      </div>
      <div>
        <dt title="Normalised R_ICE">how novel, 0 to 1</dt>
        <dd>{evaluation.surprisal.r_ice_norm.toFixed(2)}</dd>
      </div>
      <div>
        <dt>how far the belief moved</dt>
        <dd>{evaluation.surprisal.belief_change.toFixed(2)}</dd>
      </div>
      <div>
        <dt>surprising enough to seek external data</dt>
        <dd>{evaluation.surprisal.is_surprising ? "yes" : "no"}</dd>
      </div>
    </dl>
  </details>
</article>

<style>
  .finding { border-top: 1px solid var(--line); padding: 26px 0 6px; }
  header { display: flex; gap: 12px; align-items: baseline; }
  .rank { font: 400 11px var(--mono); color: var(--faint); padding-top: 3px; }
  h3 { margin: 0; font-size: 15px; font-weight: 500; line-height: 1.5; }
  .verdicts { display: flex; flex-wrap: wrap; gap: 7px; margin: 12px 0 20px 30px; }
  .tag {
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid var(--red);
    border-radius: 100px;
    color: var(--red);
  }
  .tag.yes { border-color: var(--green); color: var(--green); }
  .tag.quiet { border-color: var(--line); color: var(--dim); }
  .summary { margin: 18px 0 14px; color: var(--dim); font-size: 13px; line-height: 1.6; }

  .plots-container {
    margin: 18px 0;
    padding: 16px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 6px;
  }
  .plots-container h4 {
    margin: 0 0 12px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--violet);
    font-family: var(--mono);
  }
  .plots-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 14px;
  }
  .plot-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 8px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
  }
  .plot-card:hover { border-color: var(--violet); transform: translateY(-1px); }
  .plot-img {
    width: 100%;
    height: 140px;
    object-fit: cover;
    border-radius: 3px;
    background: #000;
  }
  .plot-caption {
    margin-top: 6px;
    font-size: 11px;
    color: var(--dim);
    font-family: var(--mono);
    text-transform: capitalize;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .modal-content {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 20px;
    max-width: 90vw;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }
  .modal-close {
    align-self: flex-end;
    background: transparent;
    border: 0;
    color: var(--dim);
    cursor: pointer;
    font-family: var(--mono);
    font-size: 12px;
  }
  .modal-close:hover { color: var(--text); }
  .modal-img {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
    border-radius: 4px;
  }
  .modal-title { margin: 0; font-size: 13px; color: var(--text); font-family: var(--mono); }

  details { border-top: 1px solid var(--line); }
  details summary {
    cursor: pointer;
    padding: 9px 0;
    font-size: 12px;
    color: var(--dim);
    list-style: none;
  }
  details summary::-webkit-details-marker { display: none; }
  details summary::before { content: "+ "; color: var(--faint); }
  details[open] summary::before { content: "− "; }
  details summary:hover { color: var(--text); }
  details p { margin: 0 0 14px; font-size: 12.5px; line-height: 1.7; color: var(--dim); }
  details p.dim { color: var(--faint); }
  .papers { list-style: none; margin: 0 0 14px; padding: 0; }
  .papers li { padding: 5px 0; border-top: 1px solid var(--line); font-size: 12px; }
  .papers span { display: block; }
  .papers small { color: var(--faint); font: 400 11px var(--mono); }
  .metrics {
    margin: 0 0 14px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0 22px;
  }
  .metrics div {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    min-width: 0;
    padding: 4px 0;
    border-top: 1px solid var(--line);
  }
  dt { min-width: 0; overflow-wrap: anywhere; font-size: 11.5px; color: var(--dim); }
  dd { flex: none; margin: 0; font: 400 11.5px var(--mono); white-space: nowrap; }
  pre {
    margin: 0 0 14px;
    padding: 12px;
    background: var(--panel);
    border: 1px solid var(--line);
    overflow-x: auto;
    font: 400 11px/1.6 var(--mono);
    color: var(--dim);
    white-space: pre-wrap;
  }
</style>
