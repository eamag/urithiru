<script lang="ts">
  import { onMount } from "svelte";
  import { cancelRun, launchRun } from "../lib/api";
  import { loadIndex, loadRun } from "../lib/run";
  import type { IndexEntry, LaunchInput, Run, View } from "../lib/types";
  import NewDiscovery from "./NewDiscovery.svelte";
  import Overview from "./Overview.svelte";
  import RunWorkspace from "./RunWorkspace.svelte";
  import Sidebar from "./Sidebar.svelte";

  const POLL_MS = 3000;

  let entries = $state<IndexEntry[]>([]);
  let loaded = $state<Run | null>(null);
  let ready = $state(false);
  let view = $state<View>("runs");
  let chosen = $state<string | null>(null);

  let entry = $derived(entries.find((item) => item.id === chosen) ?? null);
  // Never pair one run's header with another's tree while a switch is in flight.
  let run = $derived(loaded && entry && loaded.entry.id === entry.id ? loaded : null);

  async function refresh() {
    entries = await loadIndex();
    const wanted = entry;
    if (
      wanted &&
      (loaded?.entry.id !== wanted.id ||
        loaded.entry.updated_at !== wanted.updated_at ||
        loaded.entry.published_at !== wanted.published_at)
    ) {
      loaded = await loadRun(wanted);
    }
    ready = true;
  }

  /** The URL is the address of a view, so a reload and the back button both land right. */
  function apply(next: View, id: string | null) {
    view = next;
    chosen = id;
    const query = next === "run" && id ? `?run=${id}` : next === "launch" ? "?view=launch" : "";
    history.pushState({ view: next, id }, "", `${location.pathname}${query}`);
  }

  function read() {
    const parameters = new URLSearchParams(location.search);
    const id = parameters.get("run");
    chosen = id;
    view = id ? "run" : parameters.get("view") === "launch" ? "launch" : "runs";
  }

  onMount(() => {
    read();
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    const back = () => {
      read();
      void refresh();
    };
    addEventListener("popstate", back);
    return () => {
      clearInterval(timer);
      removeEventListener("popstate", back);
    };
  });

  function select(id: string) {
    apply("run", id);
    void refresh();
  }

  async function launch(input: LaunchInput) {
    const result = await launchRun(input);
    await refresh();
    select(result.id);
  }

  async function cancel() {
    if (!run) return;
    await cancelRun(run.entry.run);
    await refresh();
  }
</script>

<div class="shell">
  <Sidebar
    {entries}
    {view}
    {chosen}
    onruns={() => apply("runs", null)}
    onlaunch={() => apply("launch", null)}
    onselect={select}
  />

  <main>
    {#if view === "launch"}
      <NewDiscovery onback={() => apply("runs", null)} onlaunch={launch} />
    {:else if view === "run"}
      {#if run}
        <RunWorkspace {run} onback={() => apply("runs", null)} oncancel={cancel} />
      {:else}
        <p class="waiting">{ready && !entry ? "That run is not published here." : "Loading run…"}</p>
      {/if}
    {:else if !ready}
      <p class="waiting">Loading…</p>
    {:else}
      <Overview {entries} onlaunch={() => apply("launch", null)} onselect={select} />
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
