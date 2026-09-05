<script lang="ts">
  import { groupByDataset, leadFinding, opposed, runName, running, shortName } from "../lib/run";
  import type { IndexEntry } from "../lib/types";

  let {
    entries,
    onselect,
  }: {
    entries: IndexEntry[];
    onselect: (id: string, node?: string) => void;
  } = $props();

  let groups = $derived(groupByDataset(entries));
  let active = $derived(entries.filter((entry) => running(entry.status)).length);

  let lead = $derived(leadFinding(entries));

  const STAGES = ["prior", "literature", "experiment", "external"] as const;
</script>

<section class="overview">
  <header>
    <div>
      <p class="eyebrow">AUTONOMOUS SCIENTIFIC EXPLORATION</p>
      <h1>Urithiru</h1>
      <p class="lede">
        Give it tables and nothing else. It proposes a hypothesis, checks the published
        literature and the data through goals prepared without the other evidence path,
        then asks an external agent to find a compatible dataset that could challenge the result.
      </p>
      <p class="lede">Metrics, validity flags and provenance are agent-reported and require review.</p>
    </div>
  </header>

  {#if lead}
    <button
      type="button"
      class="lead"
      style="--verdict: {opposed(lead.found) ? 'var(--red)' : 'var(--green)'}"
      onclick={() => onselect(lead.entry.id, lead.found.node)}
      aria-label="Open the finding whose external result opposed it most"
    >
      <p class="lead-label">
        <span class="rule"></span>{opposed(lead.found)
          ? "WHERE EXTERNAL DATA DISAGREED MOST"
          : "WHERE EXTERNAL DATA MOVED THE BELIEF MOST"}
      </p>
      <p class="claim">{lead.found.claim}</p>
      <div class="chain">
        {#each STAGES as stage, index}
          <div class="hop" class:last={index === STAGES.length - 1}>
            <span class="stage">{stage}</span>
            <span class="value">{lead.found[stage].toFixed(2)}</span>
            <span class="bar"><i style="width: {lead.found[stage] * 100}%"></i></span>
          </div>
        {/each}
      </div>
      <p class="read">
        {opposed(lead.found)
          ? "The literature and seed result agreed. The external stage reported a result in the opposite direction."
          : "The external stage reported a result in the same direction."}
        <span>Open this node →</span>
      </p>
    </button>
  {/if}

  {#if groups.length}
    <p class="tally">{groups.length} dataset group{groups.length === 1 ? "" : "s"} · {entries.length} run{entries.length === 1 ? "" : "s"} · {active} running</p>

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
      <p>No published runs yet.</p>
    </div>
  {/if}
</section>

<style>
  .overview { max-width: 1080px; margin: 0 auto; padding: 50px 42px 100px; }
  .lede { max-width: 62ch; line-height: 1.65; }

  .lead {
    width: 100%;
    display: block;
    margin: 32px 0 44px;
    border: 1px solid var(--accent-line);
    border-radius: 8px;
    padding: 22px 24px 20px;
    background: linear-gradient(160deg, var(--card-from), var(--card-to));
    color: inherit;
    cursor: pointer;
    text-align: left;
    font: inherit;
  }
  .lead:hover { border-color: var(--accent-edge); }
  .lead:focus-visible { outline: 2px solid var(--accent-edge); outline-offset: 2px; }
  .lead-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 12px;
    color: var(--violet);
    font: 10px var(--mono);
    letter-spacing: .1em;
  }
  .claim { margin: 0 0 20px; max-width: 70ch; font-size: 15px; line-height: 1.5; }
  .chain { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
  .hop { display: grid; gap: 5px; padding-right: 18px; border-right: 1px solid var(--line); }
  .hop.last { padding-right: 0; border-right: 0; }
  .stage { color: var(--faint); font: 10px var(--mono); text-transform: uppercase; letter-spacing: .07em; }
  .value { font-size: 21px; font-weight: 500; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
  .bar { height: 3px; border-radius: 2px; background: var(--line); }
  .bar i { display: block; height: 100%; border-radius: 2px; background: var(--violet); }
  .hop.last .value { color: var(--verdict); }
  .hop.last .bar i { background: var(--verdict); }
  .read { margin: 20px 0 0; color: var(--dim); font-size: 12.5px; }
  .read span { color: var(--accent-text); white-space: nowrap; }

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
    .chain { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
    .hop:nth-child(2n) { padding-right: 0; border-right: 0; }
    .runs button { grid-template-columns: 8px minmax(0, 1fr) 46px 18px; }
    .status { display: none; }
  }
</style>
