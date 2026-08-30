<script lang="ts">
  import { groupByDataset, runName, running, shortName } from "../lib/run";
  import type { IndexEntry } from "../lib/types";

  let { entries, onlaunch, onselect }: { entries: IndexEntry[]; onlaunch: () => void; onselect: (id: string) => void } = $props();

  let groups = $derived(groupByDataset(entries));
  let active = $derived(entries.filter((entry) => running(entry.status)).length);
</script>

<section class="overview">
  <header>
    <div>
      <p class="eyebrow">OPERATOR WORKSPACE</p>
      <h1>Discoveries</h1>
      <p>Each dataset is one discovery. Launch a new one, follow current work, and inspect every MCTS node.</p>
    </div>
    <button type="button" onclick={onlaunch}>New discovery +</button>
  </header>

  {#if groups.length}
    <p class="tally">{groups.length} discover{groups.length === 1 ? "y" : "ies"} · {entries.length} run{entries.length === 1 ? "" : "s"} · {active} running</p>

    {#each groups as group (group.key)}
      <section class="group">
        <h2><span class="rule"></span>{group.name}<span class="count">{group.entries.length}</span></h2>
        <p class="files">{group.entries[0].dataset.map(shortName).join(" · ")}</p>

        <div class="runs" role="list">
          {#each group.entries as entry (entry.id)}
            <button type="button" role="listitem" onclick={() => onselect(entry.id)}>
              <span class="state {entry.status}" class:live={running(entry.status)}></span>
              <span class="name">
                <b>{runName(entry)}</b>
                <small><code>{entry.id.slice(0, 8)}</code> · updated {entry.updated_at.slice(0, 16).replace("T", " ") || "—"}</small>
              </span>
              <span class="count-cell">{entry.completed ?? 0}/{entry.requested ?? 0}</span>
              <span class="status">{entry.status}</span>
              <span class="arrow">→</span>
            </button>
          {/each}
        </div>
      </section>
    {/each}
  {:else}
    <div class="empty">
      <p>No discoveries yet.</p>
      <button type="button" onclick={onlaunch}>Launch the first one</button>
    </div>
  {/if}
</section>

<style>
  .overview { max-width: 1080px; margin: 0 auto; padding: 50px 42px 100px; }
  header { display: flex; justify-content: space-between; align-items: flex-end; gap: 28px; margin-bottom: 14px; }
  .eyebrow { margin: 0 0 7px; color: var(--violet); font: 10px var(--mono); letter-spacing: .13em; }
  h1 { margin: 0; font-size: 32px; font-weight: 520; letter-spacing: -.03em; }
  header p:last-child { margin: 8px 0 0; color: var(--dim); }
  header button, .empty button {
    height: 38px;
    flex: none;
    padding: 0 14px;
    border: 1px solid var(--accent-edge);
    border-radius: 5px;
    color: var(--accent-text);
    background: var(--accent-fill);
    cursor: pointer;
  }
  .tally { margin: 0 0 40px; color: var(--faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .07em; }

  .group { margin-bottom: 40px; }
  h2 {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 4px;
    font-size: 12px;
    font-weight: 550;
    letter-spacing: .06em;
    text-transform: uppercase;
  }
  .rule { width: 22px; height: 1px; flex: none; background: var(--violet); }
  .count { color: var(--faint); font: 10px var(--mono); }
  .files {
    margin: 0 0 12px 32px;
    overflow: hidden;
    color: var(--faint);
    font: 10px var(--mono);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .runs { border-top: 1px solid var(--line); }
  .runs button {
    width: 100%;
    min-height: 62px;
    display: grid;
    grid-template-columns: 8px minmax(0, 1fr) 60px 92px 20px;
    gap: 12px;
    align-items: center;
    border: 0;
    border-bottom: 1px solid var(--line);
    padding: 8px 6px;
    color: inherit;
    background: transparent;
    cursor: pointer;
    text-align: left;
    font: inherit;
  }
  .runs button:hover { background: var(--panel); }
  .state { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }
  .state.failed, .state.cancelled { background: var(--red); }
  .state.live { background: var(--violet); animation: pulse 1.6s infinite; }
  .name { min-width: 0; }
  .name b { display: block; overflow: hidden; font-size: 12.5px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
  .name small { display: block; margin-top: 3px; color: var(--faint); font-size: 10px; }
  code { font: 10px var(--mono); }
  .count-cell, .status { color: var(--dim); font: 10px var(--mono); text-transform: uppercase; }
  .arrow { color: var(--faint); }
  .empty { padding: 38px; border: 1px dashed var(--line); border-radius: 6px; color: var(--dim); text-align: center; }
  .empty button { margin-top: 14px; }
  @keyframes pulse { 50% { opacity: .35; } }
  @media (max-width: 700px) {
    .overview { padding: 30px 20px 80px; }
    header { align-items: stretch; flex-direction: column; }
    .runs button { grid-template-columns: 8px minmax(0, 1fr) 46px 18px; }
    .status { display: none; }
  }
</style>
