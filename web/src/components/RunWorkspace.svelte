<script lang="ts">
  import { activeStages, ranked, runName, running, shortName } from "../lib/run";
  import type { CheckpointNode, Run } from "../lib/types";
  import NodeInspector from "./NodeInspector.svelte";
  import Report from "./Report.svelte";
  import SurprisalLegend from "./SurprisalLegend.svelte";
  import Tree from "./Tree.svelte";

  let {
    run,
    picked,
    onback,
    onpick,
  }: {
    run: Run;
    picked: string | null;
    onback: () => void;
    onpick: (id: string) => void;
  } = $props();

  const LOG_LINES = 120;

  let tab = $state<"tree" | "report">("tree");

  let checkpoint = $derived(run.checkpoint);
  let nodes = $derived(checkpoint?.nodes ?? []);
  let order = $derived(ranked(checkpoint));
  let selected = $derived<CheckpointNode | null>(
    nodes.find((node) => node.id === picked) ?? order[0] ?? nodes[0] ?? null,
  );
  let rank = $derived(selected ? order.findIndex((node) => node.id === selected.id) + 1 : 0);
  let live = $derived(activeStages(run.events));
  let log = $derived(run.events.slice(-LOG_LINES).reverse());
  let alive = $derived(running(run.entry.status));
  let currentRequested = $derived(run.entry.requested ?? run.config?.steps ?? 1);

  let detail: HTMLElement | undefined = $state();

  function pick(id: string) {
    onpick(id);
    const gentle = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    detail?.scrollIntoView({ behavior: gentle ? "smooth" : "auto", block: "nearest" });
  }

</script>

<section class="workspace">
  <header>
    <button type="button" class="back" onclick={onback}>← All runs</button>
    <div class="title">
      <div>
        <h1>{runName(run.entry)}</h1>
        <p class="dataset">{run.entry.dataset.map(shortName).join(" · ")}</p>
      </div>

    </div>

    <p class="facts">
      <span class="status" class:live={alive}>{run.entry.status}</span>
      · {run.entry.completed ?? 0} of {currentRequested} hypotheses
      {#if run.config}· seed {run.config.seed} · {run.config.models.agent}{/if}
      · <code>{run.entry.id.slice(0, 8)}</code>
    </p>

    {#if live.length}
      <p class="stages">
        {#each live as stage}<span>{stage}</span>{/each}
        {live.length > 1 ? "running in parallel, in separate workspaces" : "running"}
      </p>
    {/if}
    {#if run.entry.error}<p class="error">{run.entry.error}</p>{/if}

    <nav class="view-tabs">
      <button
        type="button"
        class="tab-btn"
        class:active={tab === "tree"}
        onclick={() => (tab = "tree")}
      >
        Search Tree & Inspector ({nodes.length})
      </button>
      <button
        type="button"
        class="tab-btn"
        class:active={tab === "report"}
        onclick={() => (tab = "report")}
      >
        Exploration Report ({order.length})
      </button>
    </nav>
  </header>

  {#if tab === "report"}
    <section class="panel report-panel">
      <Report
        {run}
        onselectNode={(id) => {
          onpick(id);
          tab = "tree";
        }}
      />
    </section>
  {:else}
    {#if checkpoint}
      <section class="panel tree-panel">
        <h2>
          search tree <span>{nodes.length} nodes · {order.length} evaluated</span>
          <SurprisalLegend />
        </h2>
        <div class="scroller">
          <Tree {checkpoint} selectedId={selected?.id ?? ""} onselect={pick} />
        </div>
      </section>

      <section class="panel" bind:this={detail}>
        <h2>node <span>{selected ? selected.id : "none"}</span></h2>
        {#if selected}
          <NodeInspector node={selected} {rank} pending={checkpoint.pending.includes(selected.id)} />
        {:else}
          <p class="none">The tree is empty until the first proposal round returns.</p>
        {/if}
      </section>
    {:else}
      <p class="none">Waiting for the first checkpoint.</p>
    {/if}
  {/if}

  <section class="panel">
    <details class="log-details" open={alive}>
      <summary>event log <span>{run.events.length} events</span></summary>
      <ol class="log">
        {#each log as event}
          <li class={event.severity.toLowerCase()}>
            <time>{event.time.slice(11, 19)}</time>
            <span>{event.message}</span>
          </li>
        {:else}
          <li class="info"><span>No events yet.</span></li>
        {/each}
      </ol>
    </details>
  </section>
</section>

<style>
  .workspace { max-width: 1280px; margin: 0 auto; padding: 34px 42px 100px; }
  .back { margin-bottom: 20px; border: 0; padding: 0; color: var(--faint); background: transparent; cursor: pointer; font: 11px var(--mono); }
  .back:hover { color: var(--dim); }
  .title { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
  h1 { margin: 0; font-size: 25px; font-weight: 520; letter-spacing: -.02em; line-height: 1.3; }
  .dataset { margin: 7px 0 0; color: var(--dim); font-size: 12px; }


  .facts { margin: 14px 0 0; color: var(--dim); font-size: 12px; }
  .facts .status { color: var(--text); }
  .facts .status.live { color: var(--violet); }
  .stages { margin: 10px 0 0; color: var(--faint); font-size: 12px; }
  .stages span { margin-right: 6px; padding: 1px 6px; border: 1px solid var(--line); border-radius: 3px; color: var(--violet); font: 400 11px var(--mono); }
  .error { margin: 12px 0 0; color: var(--red); font-size: 12px; }

  .view-tabs {
    display: flex;
    gap: 8px;
    margin-top: 24px;
    border-bottom: 1px solid var(--line);
    padding-bottom: 8px;
  }
  .tab-btn {
    background: transparent;
    border: 0;
    padding: 6px 12px;
    font-size: 12.5px;
    font-family: var(--mono);
    color: var(--dim);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .tab-btn:hover { color: var(--text); background: var(--panel); }
  .tab-btn.active { color: var(--text); background: var(--line); font-weight: 500; }

  .panel { min-width: 0; margin-top: 16px; padding: 18px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel); }
  .panel:first-of-type { margin-top: 20px; }
  .report-panel { background: var(--panel); }
  .scroller { overflow: auto; max-height: 62vh; padding-bottom: 4px; scroll-padding: 16px; }
  h2 { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; padding: 0 10px; color: var(--faint); font-size: 11px; font-weight: 500; letter-spacing: .11em; text-transform: uppercase; }
  h2 span { color: var(--faint); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
  .none { margin: 0; padding: 0 10px; color: var(--dim); font-size: 12.5px; }
  .log-details > summary {
    list-style: none;
    cursor: pointer;
    padding: 0 10px;
    color: var(--faint);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: .11em;
    text-transform: uppercase;
  }
  .log-details > summary::-webkit-details-marker { display: none; }
  .log-details > summary::before { content: "+ "; }
  .log-details[open] > summary::before { content: "\2212 "; }
  .log-details > summary span { margin-left: 8px; color: var(--faint); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
  .log-details[open] .log { margin-top: 14px; }
  .log { list-style: none; margin: 0; padding: 0 10px; max-height: 320px; overflow: auto; font: 400 11.5px/1.9 var(--mono); }
  .log li { display: flex; gap: 14px; color: var(--dim); }
  .log span { min-width: 0; overflow-wrap: anywhere; }
  .log li.warning span { color: var(--violet); }
  .log li.error span { color: var(--red); }
  time { flex: none; color: var(--faint); }
  code { padding: 2px 6px; border: 1px solid var(--line); border-radius: 3px; background: var(--bg); font: 400 11.5px var(--mono); }
  @media (max-width: 1000px) {
    .workspace { padding: 26px 20px 80px; }
    .scroller { max-height: 44vh; }
  }
</style>
