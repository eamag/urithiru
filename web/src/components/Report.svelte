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
  let replicatedCount = $derived(
    order.filter((n) => n.evaluation && verdict(n.evaluation) === "replicated").length,
  );
  let contradictedCount = $derived(
    order.filter((n) => n.evaluation && verdict(n.evaluation) === "contradicted").length,
  );
  let maxReward = $derived(
    order.length > 0
      ? Math.max(...order.map((n) => (n.evaluation?.reward ?? 0) + (n.evaluation?.external_value ?? 0)))
      : 0,
  );

  let copied = $state(false);

  function formatProb(val: number | null | undefined): string {
    return val === null || val === undefined ? "none" : val.toFixed(4);
  }

  function generateMarkdown(): string {
    const lines = [
      `# Discovery Report: ${runName(run.entry)}`,
      "",
      `**Run ID:** \`${run.entry.id}\`  `,
      `**Dataset:** ${run.entry.dataset.map(shortName).join(", ")}  `,
      `**Evaluated Hypotheses:** ${order.length} | **Supported:** ${supportedCount} | **Refuted:** ${order.length - supportedCount}  `,
      `**Independent Verification:** ${replicatedCount} replicated, ${contradictedCount} contradicted  `,
      "",
      "> *Beliefs are elicited Bayesian model assessments through 30 pseudovotes and Beta(0.5, 0.5) prior, not calibrated frequentist confidence.*",
      "",
      "---",
      "",
    ];

    order.forEach((node, index) => {
      const ev = node.evaluation!;
      const totalReward = ev.reward + ev.external_value;
      const c = chain(ev);
      lines.push(`## ${index + 1}. ${node.claim}`);
      lines.push("");
      lines.push(
        `- **Empirical Support:** ${ev.experiment.empirical_support ? "Supported" : "Refuted"}`,
      );
      lines.push(`- **Independent Verdict:** ${verdict(ev)}`);
      lines.push(
        `- **Reward:** ${totalReward.toFixed(4)} (seed: ${ev.reward.toFixed(4)}, external value: ${ev.external_value.toFixed(4)})`,
      );
      lines.push(
        `- **Belief Progression:** P_param=${formatProb(c[0].value)} → P_search=${formatProb(c[1].value)} → P_code=${formatProb(c[2].value)} → P_external=${formatProb(c[3].value)}`,
      );
      lines.push("");
      lines.push(`### Scientific Summary`);
      lines.push(ev.experiment.summary);
      lines.push("");
      if (ev.experiment.rationale) {
        lines.push(`**Method & Analysis:** ${ev.experiment.rationale}`);
        lines.push("");
      }
      lines.push("---");
      lines.push("");
    });

    return lines.join("\n");
  }

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(generateMarkdown());
      copied = true;
      setTimeout(() => (copied = false), 2500);
    } catch {
      // Fallback
    }
  }

  function downloadJson() {
    const reportData = {
      run_id: run.entry.id,
      title: runName(run.entry),
      dataset: run.entry.dataset,
      created_at: run.entry.updated_at || run.entry.published_at,
      summary: {
        total_evaluated: order.length,
        supported: supportedCount,
        refuted: order.length - supportedCount,
        replicated: replicatedCount,
        contradicted: contradictedCount,
        max_reward: maxReward,
      },
      findings: order.map((node, index) => ({
        rank: index + 1,
        id: node.id,
        claim: node.claim,
        empirical_support: node.evaluation!.experiment.empirical_support,
        verdict: verdict(node.evaluation!),
        reward: node.evaluation!.reward + node.evaluation!.external_value,
        seed_reward: node.evaluation!.reward,
        external_value: node.evaluation!.external_value,
        beliefs: {
          p_param: node.evaluation!.prior ? formatProb(chain(node.evaluation!)[0].value) : null,
          p_search: node.evaluation!.literature ? formatProb(chain(node.evaluation!)[1].value) : null,
          p_code: node.evaluation!.experiment ? formatProb(chain(node.evaluation!)[2].value) : null,
          p_external: node.evaluation!.external ? formatProb(chain(node.evaluation!)[3].value) : null,
        },
        experiment: node.evaluation!.experiment,
        literature: node.evaluation!.literature,
        external: node.evaluation!.external,
        diagnostics: node.evaluation!.surprisal,
      })),
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${run.entry.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
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
        <span class="card-label">Empirical Support</span>
        <span class="card-value supported">{supportedCount}</span>
        <span class="card-sub">{order.length ? Math.round((supportedCount / order.length) * 100) : 0}% supported</span>
      </div>
      <div class="card">
        <span class="card-label">Independent Check</span>
        <span class="card-value">{replicatedCount} / {order.length}</span>
        <span class="card-sub">{replicatedCount} rep · {contradictedCount} contra</span>
      </div>
      <div class="card">
        <span class="card-label">Top Reward</span>
        <span class="card-value reward">{maxReward.toFixed(3)}</span>
        <span class="card-sub">information gain</span>
      </div>
    </div>

    <div class="report-actions">
      <button type="button" class="btn action-btn" onclick={copyMarkdown}>
        {copied ? "✓ Copied Markdown" : "Copy report.md"}
      </button>
      <button type="button" class="btn action-btn" onclick={downloadJson}>
        Download report.json
      </button>
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
                  {ev.experiment.empirical_support ? "supported by data" : "refuted by data"}
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

  .report-actions { display: flex; gap: 10px; flex-wrap: wrap; }
  .action-btn {
    padding: 8px 14px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 5px;
    color: var(--text);
    cursor: pointer;
    font-size: 12px;
    font-family: var(--mono);
    transition: all 0.15s ease;
  }
  .action-btn:hover { background: var(--line); color: var(--text); }

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
