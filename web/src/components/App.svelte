<script lang="ts">
  import { onMount } from "svelte";
  import { loadIndex, loadRun } from "../lib/run";
  import type { IndexEntry, Run, View } from "../lib/types";
  import Overview from "./Overview.svelte";
  import RunWorkspace from "./RunWorkspace.svelte";
  import Sidebar from "./Sidebar.svelte";

  let entries = $state<IndexEntry[]>([]);
  let loaded = $state<Run | null>(null);
  let ready = $state(false);
  let view = $state<View>("runs");
  let chosen = $state<string | null>(null);
  let node = $state<string | null>(null);

  let entry = $derived(entries.find((item) => item.id === chosen) ?? null);
  let run = $derived(loaded && entry && loaded.entry.id === entry.id ? loaded : null);

  // The runs shipped with this site are finished and immutable, so this reads
  // each one once instead of polling: nothing it could fetch again would differ.
  async function refresh() {
    if (!entries.length) entries = await loadIndex();
    const wanted = entry;
    if (wanted && loaded?.entry.id !== wanted.id) loaded = await loadRun(wanted);
    ready = true;
  }

  function apply(next: View, id: string | null, at: string | null = null) {
    view = next;
    chosen = id;
    node = at;
    const query = next === "run" && id ? `?run=${id}${at ? `&node=${at}` : ""}` : "";
    history.pushState({ view: next, id, node: at }, "", `${location.pathname}${query}`);
  }

  function read() {
    const parameters = new URLSearchParams(location.search);
    const id = parameters.get("run");
    chosen = id;
    node = id ? parameters.get("node") : null;
    view = id ? "run" : "runs";
  }

  onMount(() => {
    read();
    void refresh();
    const back = () => {
      read();
      void refresh();
    };
    addEventListener("popstate", back);
    return () => removeEventListener("popstate", back);
  });

  function select(id: string, at: string | null = null) {
    apply("run", id, at);
    void refresh();
  }
</script>

<div class="shell">
  <Sidebar {entries} {view} {chosen} onruns={() => apply("runs", null)} onselect={select} />

  <main>
    {#if view === "run"}
      {#if run}
        <RunWorkspace
          {run}
          picked={node}
          onback={() => apply("runs", null)}
          onpick={(id) => apply("run", chosen, id)}
        />
      {:else}
        <p class="waiting">{ready && !entry ? "That run is not published here." : "Loading run…"}</p>
      {/if}
    {:else if !ready}
      <p class="waiting">Loading…</p>
    {:else}
      <Overview {entries} onselect={select} />
    {/if}
  </main>
</div>

<style>
  .shell { min-height: 100vh; display: grid; grid-template-columns: 252px minmax(0, 1fr); }
  main { min-width: 0; }
  .waiting { margin: 0; padding: 60px 42px; color: var(--dim); font-size: 13px; }
  @media (max-width: 860px) {
    .shell { grid-template-columns: 1fr; }
  }
</style>
