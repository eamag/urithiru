<script lang="ts">
  import {
    Activity,
    ArrowLeft,
    Beaker,
    Check,
    ChevronRight,
    CircleSlash2,
    Clipboard,
    Clock3,
    Cloud,
    Code2,
    Database,
    Download,
    ExternalLink,
    FileArchive,
    GitBranch,
    ListTree,
    MoreHorizontal,
    Pause,
    SearchCheck,
    Sparkles,
  } from "lucide-svelte";
  import type { DiscoveryRun, TreeNode } from "../lib/types";
  import NodeInspector from "./NodeInspector.svelte";
  import StatusPill from "./StatusPill.svelte";
  import TreeView from "./TreeView.svelte";

  export let run: DiscoveryRun;
  export let onback: () => void;

  let tab: "tree" | "findings" | "activity" = "tree";
  let selectedNodeId = run.nodes.find((node) => node.status === "running")?.id ?? run.nodes[1]?.id ?? "root";
  let copied = false;

  $: if (!run.nodes.some((node) => node.id === selectedNodeId)) selectedNodeId = run.nodes[0]?.id ?? "root";
  $: selectedNode = run.nodes.find((node) => node.id === selectedNodeId) ?? run.nodes[0];
  $: findings = run.nodes.filter((node) => ["supported", "refuted", "inconclusive"].includes(node.status));

  async function copyId() {
    await navigator.clipboard?.writeText(run.id);
    copied = true;
    setTimeout(() => copied = false, 1600);
  }

  function exportRun() {
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${run.id}-evidence.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function verdictIcon(node: TreeNode) {
    return node.status === "supported" ? Check : CircleSlash2;
  }
</script>

<section class="run-page">
  <header class="run-header">
    <div class="run-header-main">
      <button type="button" class="back-icon-button" aria-label="Back to overview" onclick={onback}><ArrowLeft size={17} /></button>
      <div class="run-dataset-mark"><Database size={19} strokeWidth={1.7} /></div>
      <div class="run-heading-copy">
        <div class="run-id-row">
          <span>{run.id}</span>
          <button type="button" aria-label="Copy run ID" title="Copy run ID" onclick={copyId}>{#if copied}<Check size={12} />{:else}<Clipboard size={12} />{/if}</button>
          <StatusPill status={run.status} compact />
        </div>
        <h1>{run.name}</h1>
        <p>{run.datasetName} <span>·</span> {run.datasetSize} <span>·</span> {run.rows} rows <span>·</span> {run.columns || "—"} variables</p>
      </div>
    </div>
    <div class="run-header-actions">
      {#if run.status === "running"}<button type="button" class="secondary-button"><Pause size={15} /> Pause</button>{/if}
      <button type="button" class="secondary-button" onclick={exportRun}><Download size={15} /> Export</button>
      <button type="button" class="icon-button" aria-label="More actions"><MoreHorizontal size={17} /></button>
    </div>
  </header>

  {#if run.status === "running"}
    <div class="live-run-strip">
      <div class="live-orb"><span></span></div>
      <div class="live-run-copy"><strong>{run.currentAction}</strong><span>{run.stage} · {run.completeNodes} of {run.totalNodes} complete</span></div>
      <div class="live-run-progress"><div><span style={`width:${run.progress}%`}></span></div><strong>{run.progress}%</strong></div>
      <div class="cloud-worker-label"><Cloud size={14} /> {run.region}</div>
    </div>
  {/if}

  <div class="run-summary-bar">
    <div><span class="summary-icon violet"><Sparkles size={15} /></span><small>Candidates</small><strong>{run.candidates}</strong></div>
    <div><span class="summary-icon slate"><SearchCheck size={15} /></span><small>Duplicates removed</small><strong>{run.duplicates}</strong></div>
    <div><span class="summary-icon blue"><Beaker size={15} /></span><small>Evaluated</small><strong>{run.completeNodes}</strong></div>
    <div><span class="summary-icon green"><Check size={15} /></span><small>Supported</small><strong>{run.verified}</strong></div>
    <div><span class="summary-icon amber"><ExternalLink size={15} /></span><small>Budget</small><strong class="capitalize">{run.budget}</strong></div>
  </div>

  <div class="run-tabs">
    <button type="button" class:active={tab === "tree"} onclick={() => tab = "tree"}><ListTree size={15} /> Search tree <span>{run.nodes.length - 1}</span></button>
    <button type="button" class:active={tab === "findings"} onclick={() => tab = "findings"}><FileArchive size={15} /> Findings <span>{findings.length}</span></button>
    <button type="button" class:active={tab === "activity"} onclick={() => tab = "activity"}><Activity size={15} /> Activity <span>{run.events.length}</span></button>
  </div>

  {#if tab === "tree"}
    <div class="tree-workspace">
      <div class="tree-panel">
        <div class="panel-heading">
          <div><span class="panel-kicker">MONTE CARLO TREE SEARCH</span><h2>Hypothesis search tree</h2></div>
          <div class="uct-note"><GitBranch size={13} /> node size fixed · color shows outcome</div>
        </div>
        <div class="tree-component-wrap">
          <TreeView nodes={run.nodes} selectedId={selectedNodeId} onselect={(id) => selectedNodeId = id} />
        </div>
      </div>
      {#if selectedNode}<NodeInspector node={selectedNode} />{/if}
    </div>
  {:else if tab === "findings"}
    <div class="content-tab-view findings-view">
      <div class="content-view-heading">
        <div><span class="panel-kicker">RANKED BY INFORMATION VALUE</span><h2>{findings.length} evaluated hypotheses</h2><p>Results include negative and contradictory evidence.</p></div>
        <button type="button" class="secondary-button" onclick={exportRun}><Download size={15} /> Download evidence</button>
      </div>
      <div class="findings-list">
        {#each findings.sort((a, b) => (b.reward ?? 0) - (a.reward ?? 0)) as node, index}
          {@const VerdictIcon = verdictIcon(node)}
          <button type="button" class="finding-card" onclick={() => { selectedNodeId = node.id; tab = "tree"; }}>
            <span class="finding-rank">{String(index + 1).padStart(2, "0")}</span>
            <div class="finding-main">
              <div class="finding-tags"><span class="node-state {node.status}"><VerdictIcon size={12} /> {node.status}</span>{#if node.verdict}<span class="finding-verdict">External: {node.verdict}</span>{/if}</div>
              <h3>{node.claim}</h3>
              <p>{node.summary}</p>
              <div class="finding-beliefs">
                <span>Literature <strong>{node.belief ? Math.round(node.belief.literature * 100) : "—"}%</strong></span>
                <span>Seed data <strong>{node.belief?.seed !== undefined ? Math.round(node.belief.seed * 100) : "—"}%</strong></span>
                <span>Reward <strong>{node.reward?.toFixed(2) ?? "—"}</strong></span>
              </div>
            </div>
            <ChevronRight class="finding-arrow" size={18} />
          </button>
        {/each}
      </div>
    </div>
  {:else}
    <div class="content-tab-view activity-view">
      <div class="content-view-heading">
        <div><span class="panel-kicker">STRUCTURED RUN EVENTS</span><h2>Activity log</h2><p>Progress emitted by the orchestrator and verification workers.</p></div>
        <span class="cloud-log-chip"><Code2 size={13} /> Cloud Logging</span>
      </div>
      <div class="activity-layout">
        <div class="activity-timeline">
          {#each run.events as event}
            <article class="timeline-event {event.status}">
              <span class="timeline-dot">{#if event.status === "complete"}<Check size={11} />{:else if event.status === "warning"}<span>!</span>{:else if event.status === "active"}<span class="tiny-spinner"></span>{:else}<Clock3 size={11} />{/if}</span>
              <div><strong>{event.title}</strong><p>{event.detail}</p></div>
              <time>{event.time}</time>
            </article>
          {/each}
        </div>
        <aside class="run-context-card">
          <span class="panel-kicker">RUN CONTEXT</span>
          <dl>
            <div><dt>Run ID</dt><dd>{run.id}</dd></div>
            <div><dt>Region</dt><dd>{run.region}</dd></div>
            <div><dt>Budget</dt><dd class="capitalize">{run.budget}</dd></div>
            <div><dt>Started</dt><dd>{run.startedAt}</dd></div>
            <div><dt>Dataset</dt><dd>{run.datasetName}</dd></div>
          </dl>
        </aside>
      </div>
    </div>
  {/if}
</section>
