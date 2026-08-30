<script lang="ts">
  import { groupByDataset, runName, running } from "../lib/run";
  import type { IndexEntry, View } from "../lib/types";

  let {
    entries,
    view,
    chosen,
    onruns,
    onlaunch,
    onselect,
  }: {
    entries: IndexEntry[];
    view: View;
    chosen: string | null;
    onruns: () => void;
    onlaunch: () => void;
    onselect: (id: string) => void;
  } = $props();

  let query = $state("");
  let visible = $derived(
    entries.filter((entry) =>
      `${entry.title ?? ""} ${entry.dataset.join(" ")} ${entry.id}`.toLowerCase().includes(query.toLowerCase()),
    ),
  );
  let groups = $derived(groupByDataset(visible));
</script>

<aside class="sidebar">
  <button class="brand" type="button" onclick={onruns} aria-label="Urithiru runs">
    <span class="brand-mark"></span>
    <span><b>URITHIRU</b><small>discovery engine</small></span>
  </button>

  <button class="launch" type="button" onclick={onlaunch}>New discovery <span>+</span></button>

  <nav aria-label="Workspace">
    <button class:active={view === "runs"} type="button" onclick={onruns}>All discoveries <span>{entries.length}</span></button>
  </nav>

  <label class="search">
    <span class="sr-only">Search discoveries</span>
    <input bind:value={query} placeholder="Search discoveries" />
  </label>

  <div class="run-groups">
    {#each groups as group (group.key)}
      <section>
        <h2>{group.name} <span>{group.entries.length}</span></h2>
        {#each group.entries as entry (entry.id)}
          <button class:selected={chosen === entry.id && view === "run"} class="run-link" type="button" onclick={() => onselect(entry.id)}>
            <span class="status {entry.status}" class:live={running(entry.status)}></span>
            <span><b>{runName(entry)}</b><small>{entry.status} · {entry.completed ?? 0}/{entry.requested ?? 0}</small></span>
          </button>
        {/each}
      </section>
    {:else}
      <p class="none">No discoveries yet.</p>
    {/each}
  </div>

</aside>

<style>
  .sidebar { width: 248px; height: 100vh; position: sticky; top: 0; display: flex; flex-direction: column; border-right: 1px solid var(--line); background: var(--sidebar); }
  button { color: inherit; font: inherit; }
  .brand { height: 72px; display: flex; align-items: center; gap: 11px; padding: 0 20px; border: 0; background: transparent; text-align: left; cursor: pointer; }
  .brand-mark { width: 18px; height: 18px; position: relative; border: 1px solid var(--violet); border-radius: 50%; }
  .brand-mark::before, .brand-mark::after { content: ""; position: absolute; background: var(--violet); }
  .brand-mark::before { width: 4px; height: 4px; border-radius: 50%; inset: 6px; }
  .brand-mark::after { width: 1px; height: 26px; left: 8px; top: -5px; transform: rotate(45deg); opacity: .45; }
  .brand b { display: block; font-size: 12px; letter-spacing: .15em; }
  .brand small { display: block; color: var(--faint); font-size: 10px; margin-top: 2px; }
  .launch { margin: 4px 14px 18px; height: 38px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; border: 1px solid var(--accent-line); border-radius: 5px; background: var(--accent-bg); color: var(--accent-text); cursor: pointer; }
  .launch:hover { border-color: var(--violet); }
  .launch span { font-size: 18px; font-weight: 300; }
  nav { padding: 0 14px 14px; border-bottom: 1px solid var(--line); }
  nav button { width: 100%; height: 34px; display: flex; justify-content: space-between; align-items: center; padding: 0 9px; border: 0; border-radius: 4px; color: var(--dim); background: transparent; cursor: pointer; text-align: left; }
  nav button.active, nav button:hover { color: var(--text); background: var(--panel); }
  nav span, h2 span { color: var(--faint); font: 10px var(--mono); }
  .search { padding: 14px 14px 8px; }
  .search input { width: 100%; height: 32px; border: 1px solid var(--line); border-radius: 4px; padding: 0 9px; color: var(--text); background: var(--bg); font: 11px var(--mono); outline: 0; }
  .search input:focus { border-color: var(--accent-line); }
  .run-groups { min-height: 0; flex: 1; overflow-y: auto; padding: 0 10px 20px; }
  section { margin-top: 13px; }
  h2 { display: flex; justify-content: space-between; margin: 0 8px 6px; color: var(--faint); font-size: 9px; font-weight: 500; letter-spacing: .12em; text-transform: uppercase; }
  .run-link { width: 100%; min-height: 48px; display: grid; grid-template-columns: 8px minmax(0,1fr); gap: 8px; align-items: start; padding: 8px; border: 0; border-radius: 5px; background: transparent; cursor: pointer; text-align: left; }
  .run-link:hover, .run-link.selected { background: var(--panel); }
  .status { width: 5px; height: 5px; margin-top: 6px; border-radius: 50%; background: var(--green); }

  .status.failed, .status.cancelled { background: var(--red); }
  .status.live { background: var(--violet); animation: pulse 1.6s infinite; }
  .run-link b { display: block; overflow: hidden; color: var(--text-soft); font-size: 11px; font-weight: 450; text-overflow: ellipsis; white-space: nowrap; }
  .run-link small { display: block; margin-top: 3px; color: var(--faint); font: 9px var(--mono); }
  .none { margin: 12px 8px; color: var(--faint); font-size: 10px; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
  @keyframes pulse { 50% { opacity: .35; } }
  @media (max-width: 760px) { .sidebar { width: 100%; height: auto; position: static; border-right: 0; border-bottom: 1px solid var(--line); } .search, .run-groups, nav { display: none; } .brand { height: 54px; } .launch { position: absolute; top: 8px; right: 6px; width: 150px; margin: 0; } }
</style>
