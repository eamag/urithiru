<script lang="ts">
  import { Activity, LayoutDashboard, Plus } from "lucide-svelte";
  import { onMount } from "svelte";
  import { apiConfigured, createRun, listRuns } from "../lib/api";
  import { createDemoRun, formatBytes, getDemoRuns } from "../lib/demo";
  import type { DiscoveryRun, NewRunInput, View } from "../lib/types";
  import NewDiscovery from "./NewDiscovery.svelte";
  import Overview from "./Overview.svelte";
  import RunWorkspace from "./RunWorkspace.svelte";
  import Sidebar from "./Sidebar.svelte";

  let runs: DiscoveryRun[] = getDemoRuns();
  let view: View = "overview";
  let selectedRunId: string | null = runs[0]?.id ?? null;

  $: selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0];

  function navigate(next: View) {
    view = next;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectRun(id: string) {
    selectedRunId = id;
    navigate("run");
  }

  onMount(() => {
    if (!apiConfigured) return;
    let stopped = false;
    const refresh = async () => {
      try {
        const remoteRuns = await listRuns();
        if (!stopped) runs = remoteRuns;
      } catch (error) {
        console.warn("Could not refresh Urithiru runs", error);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5_000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  });

  async function launch(input: NewRunInput) {
    if (apiConfigured) {
      const run = await createRun(input);
      runs = [run, ...runs.filter((item) => item.id !== run.id)];
      selectedRunId = run.id;
      navigate("run");
      return;
    }
    const totalBytes = input.files.reduce((total, file) => total + file.size, 0);
    const label = input.files.length === 1 ? input.files[0].name : `${input.files[0].name} + ${input.files.length - 1} files`;
    const run = createDemoRun(label, formatBytes(totalBytes), input.title, input.budget);
    runs = [run, ...runs];
    selectedRunId = run.id;
    navigate("run");
  }
</script>

<div class="app-shell">
  <Sidebar
    {view}
    {runs}
    {selectedRunId}
    onnavigate={navigate}
    onselectrun={selectRun}
  />

  <main class="app-main">
    {#if view === "overview"}
      <Overview {runs} onnew={() => navigate("new")} onselectrun={selectRun} />
    {:else if view === "new"}
      <NewDiscovery onback={() => navigate("overview")} onlaunch={launch} />
    {:else if selectedRun}
      <RunWorkspace run={selectedRun} onback={() => navigate("overview")} />
    {/if}
  </main>

  <nav class="mobile-nav" aria-label="Mobile navigation">
    <button type="button" class:active={view === "overview"} onclick={() => navigate("overview")}><LayoutDashboard size={18} /><span>Overview</span></button>
    <button type="button" class="mobile-new" onclick={() => navigate("new")}><Plus size={20} /><span>New</span></button>
    <button type="button" class:active={view === "run"} onclick={() => selectedRunId && selectRun(selectedRunId)}><Activity size={18} /><span>Workspace</span></button>
  </nav>
</div>
