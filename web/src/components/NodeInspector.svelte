<script lang="ts">
  import {
    Beaker,
    BookOpen,
    Check,
    ChevronRight,
    CircleSlash2,
    Clock3,
    Code2,
    Database,
    ExternalLink,
    FileJson,
    FlaskConical,
    Lightbulb,
    X,
  } from "lucide-svelte";
  import type { EvidenceSource, TreeNode } from "../lib/types";

  export let node: TreeNode;
  export let onclose: (() => void) | undefined = undefined;

  let tab: "overview" | "evidence" | "experiment" = "overview";
  $: if (node) tab = "overview";

  function percent(value: number | undefined) {
    return value === undefined ? "—" : `${Math.round(value * 100)}%`;
  }

  function sourceIcon(source: EvidenceSource) {
    return source.kind === "seed" ? Database : source.kind === "external" ? ExternalLink : BookOpen;
  }
</script>

<aside class="node-inspector">
  <header class="inspector-header">
    <div>
      <span class="inspector-kicker">NODE INSPECTOR</span>
      <strong>{node.label}</strong>
    </div>
    {#if onclose}<button type="button" aria-label="Close inspector" onclick={onclose}><X size={17} /></button>{/if}
  </header>

  <div class="inspector-tabs" role="tablist" aria-label="Node detail sections">
    <button type="button" class:active={tab === "overview"} onclick={() => tab = "overview"}>Overview</button>
    <button type="button" class:active={tab === "evidence"} onclick={() => tab = "evidence"}>Evidence</button>
    <button type="button" class:active={tab === "experiment"} onclick={() => tab = "experiment"}>Experiment</button>
  </div>

  <div class="inspector-scroll">
    {#if tab === "overview"}
      <section class="inspector-section claim-section">
        <div class="node-status-line">
          <span class="node-state {node.status}">
            {#if node.status === "supported"}<Check size={12} strokeWidth={2.5} /> supported
            {:else if node.status === "refuted"}<CircleSlash2 size={12} /> refuted
            {:else if node.status === "running"}<span class="tiny-spinner"></span> running
            {:else if node.status === "root"}<Database size={12} /> source
            {:else}<Clock3 size={12} /> queued{/if}
          </span>
          {#if node.reward !== undefined}<span class="reward-chip">reward {node.reward.toFixed(2)}</span>{/if}
        </div>
        <h3>{node.claim}</h3>
        <p>{node.summary}</p>
      </section>

      {#if node.belief}
        <section class="inspector-section">
          <div class="inspector-section-title"><span>Belief trajectory</span><small>elicited probability</small></div>
          <div class="belief-chart">
            <div class="belief-axis"><span>100</span><span>50</span><span>0</span></div>
            <div class="belief-columns">
              <div class="belief-column">
                <span class="belief-value">{percent(node.belief.prior)}</span>
                <div class="belief-bar"><i style={`height:${node.belief.prior * 100}%`}></i></div>
                <small>Prior</small>
              </div>
              <ChevronRight size={12} class="belief-arrow" />
              <div class="belief-column">
                <span class="belief-value">{percent(node.belief.literature)}</span>
                <div class="belief-bar literature"><i style={`height:${node.belief.literature * 100}%`}></i></div>
                <small>Literature</small>
              </div>
              <ChevronRight size={12} class="belief-arrow" />
              <div class="belief-column">
                <span class="belief-value">{percent(node.belief.seed)}</span>
                <div class="belief-bar seed"><i style={`height:${(node.belief.seed ?? 0) * 100}%`}></i></div>
                <small>Seed data</small>
              </div>
              {#if node.belief.external !== undefined}
                <ChevronRight size={12} class="belief-arrow" />
                <div class="belief-column">
                  <span class="belief-value">{percent(node.belief.external)}</span>
                  <div class="belief-bar external"><i style={`height:${node.belief.external * 100}%`}></i></div>
                  <small>External</small>
                </div>
              {/if}
            </div>
          </div>
          <p class="belief-disclaimer">Beliefs are model-elicited assessments, not calibrated confidence.</p>
        </section>
      {/if}

      {#if node.metrics?.length}
        <section class="inspector-section">
          <div class="inspector-section-title"><span>Key metrics</span></div>
          <div class="node-metrics">
            {#each node.metrics as metric}
              <div><small>{metric.label}</small><strong>{metric.value}</strong></div>
            {/each}
          </div>
        </section>
      {/if}

      {#if node.rationale}
        <section class="inspector-section">
          <div class="inspector-section-title"><span>Interpretation</span></div>
          <div class="rationale-card"><Lightbulb size={16} strokeWidth={1.7} /><p>{node.rationale}</p></div>
        </section>
      {/if}

      {#if node.verdict && node.verdict !== "pending"}
        <section class="inspector-section">
          <div class="inspector-section-title"><span>Independent check</span></div>
          <div class="verdict-card {node.verdict.replaceAll(' ', '-')}">
            <span class="verdict-icon">{#if node.verdict === "replicated"}<Check size={16} />{:else if node.verdict === "contradicted"}<CircleSlash2 size={16} />{:else}<ExternalLink size={16} />{/if}</span>
            <div><strong>{node.verdict}</strong><p>{node.verdict === "replicated" ? "The effect direction survived a qualifying independent dataset." : node.verdict === "contradicted" ? "Independent evidence points in the opposite direction." : "No sufficiently independent, comparable dataset was available."}</p></div>
          </div>
        </section>
      {/if}
    {:else if tab === "evidence"}
      <section class="inspector-section evidence-intro">
        <h3>Evidence trail</h3>
        <p>Every source and artifact used to judge this hypothesis.</p>
      </section>
      <section class="inspector-section">
        {#if node.sources?.length}
          <div class="source-list">
            {#each node.sources as source}
              {@const Icon = sourceIcon(source)}
              <article class="source-card">
                <span class="source-icon {source.kind}"><Icon size={15} strokeWidth={1.8} /></span>
                <div><span class="source-kind">{source.kind}</span><strong>{source.title}</strong><small>{source.source}</small><p>{source.note}</p></div>
              </article>
            {/each}
          </div>
        {:else}
          <div class="inspector-empty"><FileJson size={24} /><strong>No evidence yet</strong><p>Sources appear here once evaluation begins.</p></div>
        {/if}
      </section>
    {:else}
      <section class="inspector-section evidence-intro">
        <h3>Empirical experiment</h3>
        <p>Generated analysis executed inside the hypothesis sandbox.</p>
      </section>
      {#if node.code}
        <section class="inspector-section">
          <div class="code-header"><span><Code2 size={14} /> analysis.py</span><span>Python</span></div>
          <pre class="code-block"><code>{node.code}</code></pre>
          <div class="execution-note"><Check size={14} /><span><strong>Execution completed</strong> · test specification valid</span></div>
        </section>
      {:else}
        <div class="inspector-empty experiment-empty"><FlaskConical size={25} /><strong>{node.status === "running" ? "Experiment in progress" : "No experiment yet"}</strong><p>{node.status === "running" ? "The worker is writing and executing the analysis now." : "Code and execution logs appear after this node is selected."}</p></div>
      {/if}
    {/if}
  </div>
</aside>
