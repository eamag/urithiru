<script lang="ts">
  import { Activity, FlaskConical, LayoutDashboard, Plus, Search, Sparkles } from "lucide-svelte";
  import type { DiscoveryRun, View } from "../lib/types";

  export let view: View;
  export let runs: DiscoveryRun[];
  export let selectedRunId: string | null;
  export let onnavigate: (view: View) => void;
  export let onselectrun: (id: string) => void;

  let query = "";
  $: visibleRuns = runs
    .filter((run) => run.name.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 5);
</script>

<aside class="sidebar">
  <div class="brand" aria-label="Urithiru home">
    <div class="brand-mark"><Sparkles size={18} strokeWidth={1.8} /></div>
    <div>
      <div class="brand-name">URITHIRU</div>
      <div class="brand-subtitle">Discovery engine</div>
    </div>
  </div>

  <button class="new-run-button" type="button" onclick={() => onnavigate("new")}>
    <Plus size={17} strokeWidth={2.1} />
    New discovery
  </button>

  <nav class="primary-nav" aria-label="Primary navigation">
    <button
      type="button"
      class:active={view === "overview"}
      aria-current={view === "overview" ? "page" : undefined}
      onclick={() => onnavigate("overview")}
    >
      <LayoutDashboard size={17} strokeWidth={1.8} />
      Overview
    </button>
    <button
      type="button"
      class:active={view === "run" && selectedRunId !== null}
      aria-current={view === "run" ? "page" : undefined}
      onclick={() => runs[0] && onselectrun(runs[0].id)}
    >
      <Activity size={17} strokeWidth={1.8} />
      Live workspace
      {#if runs.some((run) => run.status === "running")}
        <span class="nav-live-dot" aria-label="Active run"></span>
      {/if}
    </button>
  </nav>

  <div class="sidebar-section-heading">
    <span>Recent runs</span>
    <span>{runs.length}</span>
  </div>

  <label class="sidebar-search">
    <Search size={14} strokeWidth={1.8} />
    <span class="sr-only">Search runs</span>
    <input bind:value={query} placeholder="Find a run…" />
  </label>

  <div class="recent-runs">
    {#each visibleRuns as run}
      <button
        type="button"
        class="recent-run"
        class:selected={view === "run" && selectedRunId === run.id}
        onclick={() => onselectrun(run.id)}
      >
        <span class:running={run.status === "running"} class="run-status-mark"></span>
        <span class="recent-run-copy">
          <span>{run.name}</span>
          <small>{run.startedAt}</small>
        </span>
      </button>
    {/each}
  </div>

  <div class="sidebar-spacer"></div>

  <div class="cloud-card">
    <div class="cloud-card-icon"><FlaskConical size={16} strokeWidth={1.8} /></div>
    <div>
      <strong>Demo workspace</strong>
      <span>Google Cloud · europe-west1</span>
    </div>
    <span class="healthy-dot" title="Healthy"></span>
  </div>
</aside>
