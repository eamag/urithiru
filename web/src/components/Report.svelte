<script lang="ts">
  import { chain, ranked, runName, shortName, verdict } from "../lib/run";
  import type { CheckpointNode, Run } from "../lib/types";
  import Beliefs from "./Beliefs.svelte";

  let {
    run,
    onselectNode,
  }: {
    run: Run;
    onselectNode: (id: string) => void;
  } = $props();

  let checkpoint = $derived(run.checkpoint);
  let order = $derived(ranked(checkpoint));
  let supportedCount = $derived(
    order.filter((n) => n.evaluation?.experiment.empirical_support).length,
  );
  let alignedCount = $derived(
    order.filter((n) => n.evaluation && verdict(n.evaluation) === "aligned").length,
  );
  let opposedCount = $derived(
    order.filter((n) => n.evaluation && verdict(n.evaluation) === "opposed").length,
  );
  let maxReward = $derived(
    order.length > 0
      ? Math.max(...order.map((n) => (n.evaluation?.reward ?? 0) + (n.evaluation?.external_value ?? 0)))
      : 0,
  );

</script>

<div class="report-container">
  <div class="report-header">
    <div class="summary-cards">
      <div class="card">
        <span class="card-label">Evaluated</span>
        <span class="card-value">{order.length}</span>
        <span class="card-sub">hypotheses</span>
      </div>
      <div class="card">
        <span class="card-label">Agent-Reported Support</span>
        <span class="card-value supported">{supportedCount}</span>
        <span class="card-sub">{order.length ? Math.round((supportedCount / order.length) * 100) : 0}% reported</span>
      </div>
      <div class="card">
        <span class="card-label">External Results</span>
        <span class="card-value">{alignedCount} / {order.length}</span>
        <span class="card-sub">{alignedCount} aligned · {opposedCount} opposed</span>
      </div>
      <div class="card">
        <span class="card-label">Top Reward</span>
        <span class="card-value reward">{maxReward.toFixed(3)}</span>
        <span class="card-sub">information gain</span>
      </div>
    </div>

  </div>

  {#if order.length === 0}
    <p class="empty">No evaluated hypotheses in this run yet.</p>
  {:else}
    <div class="findings-list">
      {#each order as node, idx}
        {@const ev = node.evaluation!}
        {@const totalReward = ev.reward + ev.external_value}
        <article class="finding-card">
          <header class="finding-header">
            <span class="finding-rank">{String(idx + 1).padStart(2, "0")}</span>
            <div class="finding-title-wrap">
              <h3 class="finding-claim">{node.claim}</h3>
              <div class="finding-badges">
                <span class="tag" class:yes={ev.experiment.empirical_support}>
                  {ev.experiment.empirical_support ? "agent reported support" : "agent reported refutation"}
                </span>
                <span class="tag quiet">{verdict(ev)}</span>
                <span class="tag quiet">reward {totalReward.toFixed(3)}</span>
                <button
                  type="button"
                  class="inspect-link"
                  onclick={() => onselectNode(node.id)}
                >
                  Inspect tree node ({node.id}) →
                </button>
              </div>
            </div>
          </header>

          <div class="finding-body">
            <Beliefs evaluation={ev} />
            <p class="finding-summary">{ev.experiment.summary}</p>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<style>
  .report-container { display: flex; flex-direction: column; gap: 24px; }
  .report-header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    padding: 20px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 7px;
  }
  .summary-cards { display: flex; flex-wrap: wrap; gap: 14px; }
  .card {
    display: flex;
    flex-direction: column;
    padding: 10px 14px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    min-width: 120px;
  }
  .card-label { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--faint); font-family: var(--mono); }
  .card-value { font-size: 20px; font-weight: 600; margin: 4px 0 2px; color: var(--text); }
  .card-value.supported { color: var(--green); }
  .card-value.reward { color: var(--violet); }
  .card-sub { font-size: 11px; color: var(--dim); }


  .empty { padding: 40px 10px; color: var(--dim); font-size: 13px; text-align: center; }
  .findings-list { display: flex; flex-direction: column; gap: 16px; }

  .finding-card {
    padding: 20px;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--panel);
    transition: border-color 0.15s ease;
  }
  .finding-card:hover { border-color: var(--dim); }
  .finding-header { display: flex; gap: 16px; align-items: flex-start; }
  .finding-rank {
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 500;
    color: var(--violet);
    padding-top: 2px;
    flex: none;
  }
  .finding-title-wrap { flex: 1; min-width: 0; }
  .finding-claim { margin: 0 0 8px; font-size: 15px; font-weight: 500; line-height: 1.5; color: var(--text); }
  .finding-badges { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
  .tag {
    font-size: 11px;
    padding: 2px 8px;
    border: 1px solid var(--red);
    border-radius: 100px;
    color: var(--red);
  }
  .tag.yes { border-color: var(--green); color: var(--green); }
  .tag.quiet { border-color: var(--line); color: var(--dim); }
  .inspect-link {
    background: transparent;
    border: 0;
    padding: 0;
    color: var(--faint);
    cursor: pointer;
    font-size: 11.5px;
    font-family: var(--mono);
    margin-left: auto;
  }
  .inspect-link:hover { color: var(--violet); }

  .finding-body { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }
  .finding-summary { margin: 12px 0 0; font-size: 12.5px; line-height: 1.65; color: var(--dim); }
</style>
