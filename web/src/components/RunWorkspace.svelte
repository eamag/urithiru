<script lang="ts">
  import { activeStages, ranked, runName, running, shortName } from "../lib/run";
  import type { CheckpointNode, Run } from "../lib/types";
  import NodeInspector from "./NodeInspector.svelte";
  import Tree from "./Tree.svelte";

  let { run, onback, oncancel }: { run: Run; onback: () => void; oncancel: () => Promise<void> } = $props();

  const LOG_LINES = 120;

  let picked = $state<string | null>(null);
  let cancelling = $state(false);
  let error = $state("");

  let checkpoint = $derived(run.checkpoint);
  let nodes = $derived(checkpoint?.nodes ?? []);
  let order = $derived(ranked(checkpoint));
  // Until something is picked, show the strongest finding, else the root.
  let selected = $derived<CheckpointNode | null>(
    nodes.find((node) => node.id === picked) ?? order[0] ?? nodes[0] ?? null,
  );
  let rank = $derived(selected ? order.findIndex((node) => node.id === selected.id) + 1 : 0);
  let live = $derived(activeStages(run.events));
  let log = $derived(run.events.slice(-LOG_LINES).reverse());
  let alive = $derived(running(run.entry.status));

  async function stop() {
    cancelling = true;
    error = "";
    try {
      await oncancel();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      cancelling = false;
    }
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
      {#if alive}
        <button type="button" class="cancel" disabled={cancelling} onclick={() => void stop()}>
          {cancelling ? "Cancelling…" : "Cancel run"}
        </button>
      {/if}
    </div>

    <p class="facts">
      <span class="status" class:live={alive}>{run.entry.status}</span>
      · {run.entry.completed ?? 0} of {run.entry.requested ?? 0} hypotheses
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
    {#if error}<p class="error">{error}</p>{/if}
  </header>

  {#if checkpoint}
    <section class="panel tree-panel">
      <h2>search tree <span>{nodes.length} nodes · {order.length} evaluated</span></h2>
      <div class="scroller">
        <Tree {checkpoint} selectedId={selected?.id ?? ""} onselect={(id) => (picked = id)} />
      </div>
    </section>

    <section class="panel">
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

  <section class="panel">
    <h2>event log <span>{run.events.length} events</span></h2>
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
  </section>
</section>

<style>
  .workspace { max-width: 1280px; margin: 0 auto; padding: 34px 42px 100px; }
  .back { margin-bottom: 20px; border: 0; padding: 0; color: var(--faint); background: transparent; cursor: pointer; font: 11px var(--mono); }
  .back:hover { color: var(--dim); }
  .title { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
  h1 { margin: 0; font-size: 25px; font-weight: 520; letter-spacing: -.02em; line-height: 1.3; }
  .dataset { margin: 7px 0 0; color: var(--dim); font-size: 12px; }
  .cancel { flex: none; height: 32px; padding: 0 13px; border: 1px solid var(--danger-line); border-radius: 5px; color: var(--danger-text); background: transparent; cursor: pointer; font-size: 12px; }
  .cancel:disabled { opacity: .5; cursor: default; }
  .facts { margin: 14px 0 0; color: var(--dim); font-size: 12px; }
  .facts .status { color: var(--text); }
  .facts .status.live { color: var(--violet); }
  .stages { margin: 10px 0 0; color: var(--faint); font-size: 12px; }
  .stages span { margin-right: 6px; padding: 1px 6px; border: 1px solid var(--line); border-radius: 3px; color: var(--violet); font: 400 11px var(--mono); }
  .error { margin: 12px 0 0; color: var(--red); font-size: 12px; }
  .panel { min-width: 0; margin-top: 16px; padding: 18px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel); }
  .panel:first-of-type { margin-top: 34px; }
  /* The tree lays out on a fixed grid, so it scrolls inside the panel rather than
     reflowing; the page itself never scrolls sideways. */
  .scroller { overflow: auto; max-height: 62vh; padding-bottom: 4px; }
  h2 { margin: 0 0 14px; padding: 0 10px; color: var(--faint); font-size: 11px; font-weight: 500; letter-spacing: .11em; text-transform: uppercase; }
  h2 span { margin-left: 8px; color: var(--faint); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
  .none { margin: 0; padding: 0 10px; color: var(--dim); font-size: 12.5px; }
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
