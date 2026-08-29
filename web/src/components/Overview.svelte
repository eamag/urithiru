<script lang="ts">
  import {
    ArrowRight,
    Beaker,
    CheckCircle2,
    ChevronRight,
    CircleDot,
    Clock3,
    Database,
    ExternalLink,
    GitBranch,
    Play,
    Plus,
    Sparkles,
  } from "lucide-svelte";
  import type { DiscoveryRun } from "../lib/types";
  import StatusPill from "./StatusPill.svelte";

  export let runs: DiscoveryRun[];
  export let onnew: () => void;
  export let onselectrun: (id: string) => void;

  $: activeRuns = runs.filter((run) => run.status === "running");
  $: completedRuns = runs.filter((run) => run.status === "completed");
  $: evaluated = runs.reduce((total, run) => total + run.completeNodes, 0);
  $: verified = runs.reduce((total, run) => total + run.verified, 0);
</script>

<section class="page overview-page">
  <header class="page-header overview-header">
    <div>
      <div class="eyebrow"><span class="eyebrow-dot"></span> AUTONOMOUS SCIENTIFIC DISCOVERY</div>
      <h1>Turn datasets into<br /><em>tested discoveries.</em></h1>
      <p>Urithiru proposes hypotheses, writes and executes analyses, then looks for evidence that could prove itself wrong.</p>
    </div>
    <button type="button" class="primary-button hero-cta" onclick={onnew}>
      <Plus size={18} strokeWidth={2} />
      Start a discovery
    </button>
  </header>

  <div class="metric-grid">
    <article class="metric-card">
      <div class="metric-icon violet"><CircleDot size={18} strokeWidth={1.8} /></div>
      <div class="metric-label">Active runs <span>Live</span></div>
      <div class="metric-value">{activeRuns.length}</div>
      <div class="metric-detail">{activeRuns.length ? `${activeRuns[0].completeNodes} hypotheses completed so far` : "No workers active"}</div>
    </article>
    <article class="metric-card">
      <div class="metric-icon blue"><GitBranch size={18} strokeWidth={1.8} /></div>
      <div class="metric-label">Evaluated hypotheses</div>
      <div class="metric-value">{evaluated}</div>
      <div class="metric-detail">Across {runs.length} discovery runs</div>
    </article>
    <article class="metric-card">
      <div class="metric-icon green"><CheckCircle2 size={18} strokeWidth={1.8} /></div>
      <div class="metric-label">Empirically supported</div>
      <div class="metric-value">{verified}</div>
      <div class="metric-detail">{evaluated ? Math.round((verified / evaluated) * 100) : 0}% survived seed-data tests</div>
    </article>
    <article class="metric-card">
      <div class="metric-icon amber"><ExternalLink size={18} strokeWidth={1.8} /></div>
      <div class="metric-label">Completed runs</div>
      <div class="metric-value">{completedRuns.length}</div>
      <div class="metric-detail">Evidence bundles ready to export</div>
    </article>
  </div>

  <section class="section-block">
    <div class="section-title-row">
      <div>
        <h2>Running now</h2>
        <p>Live orchestration and isolated hypothesis workers</p>
      </div>
      <span class="live-label"><span></span> Live</span>
    </div>

    {#if activeRuns.length}
      <div class="active-run-grid">
        {#each activeRuns as run}
          <button type="button" class="active-run-card" onclick={() => onselectrun(run.id)}>
            <div class="active-run-top">
              <div class="dataset-icon"><Database size={19} strokeWidth={1.7} /></div>
              <div class="active-run-title">
                <div><span class="mono-id">{run.id}</span><StatusPill status={run.status} compact /></div>
                <h3>{run.name}</h3>
                <p>{run.datasetName} · {run.datasetSize}</p>
              </div>
              <ChevronRight class="run-card-arrow" size={19} />
            </div>

            <div class="run-progress-copy">
              <span>{run.currentAction}</span>
              <strong>{run.progress}%</strong>
            </div>
            <div class="progress-track"><span style={`width: ${run.progress}%`}></span></div>

            <div class="active-run-stats">
              <span><Beaker size={14} /> <strong>{run.completeNodes}/{run.totalNodes}</strong> tested</span>
              <span><Sparkles size={14} /> <strong>{run.candidates}</strong> proposed</span>
              <span><Clock3 size={14} /> Started {run.startedAt}</span>
            </div>
          </button>
        {/each}
      </div>
    {:else}
      <div class="empty-state">
        <Play size={20} />
        <span>No discoveries are running.</span>
        <button type="button" onclick={onnew}>Launch one <ArrowRight size={14} /></button>
      </div>
    {/if}
  </section>

  <section class="section-block">
    <div class="section-title-row">
      <div>
        <h2>Discovery history</h2>
        <p>Completed and in-progress research runs</p>
      </div>
    </div>

    <div class="history-table-wrap">
      <table class="history-table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Status</th>
            <th>Budget</th>
            <th>Hypotheses</th>
            <th>Supported</th>
            <th>Started</th>
            <th><span class="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {#each runs as run}
            <tr onclick={() => onselectrun(run.id)}>
              <td>
                <button class="table-run-name" type="button" onclick={() => onselectrun(run.id)}>
                  <span class="table-dataset-icon"><Database size={15} /></span>
                  <span><strong>{run.name}</strong><small>{run.datasetName}</small></span>
                </button>
              </td>
              <td><StatusPill status={run.status} compact /></td>
              <td><span class="budget-label">{run.budget}</span></td>
              <td><span class="table-number">{run.completeNodes}/{run.totalNodes}</span></td>
              <td><span class="supported-number">{run.verified}</span></td>
              <td class="muted-cell">{run.startedAt}</td>
              <td><ChevronRight size={16} class="table-chevron" /></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
</section>
