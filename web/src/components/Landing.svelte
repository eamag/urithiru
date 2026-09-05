<script lang="ts">
  import { onMount } from "svelte";
  import { leadFinding, loadIndex, moved, opposed, runName } from "../lib/run";
  import type { IndexEntry } from "../lib/types";

  const STAGES = [
    { key: "prior", saw: "no evidence" },
    { key: "literature", saw: "data-blind" },
    { key: "experiment", saw: "seed data" },
    { key: "external", saw: "agent-reported" },
  ] as const;

  interface Step {
    number: string;
    label: string;
    title: string;
    body: string;
    lanes?: { name: string; saw: string }[];
  }

  const STEPS: Step[] = [
    {
      number: "01",
      label: "PROPOSE",
      title: "Write a falsifiable claim",
      body: "An agent reads the tables and proposes one. Near-duplicates never enter the tree.",
    },
    {
      number: "02",
      label: "SEPARATE",
      title: "Answer it twice, blind",
      body: "Two agents answer at once, each prepared without the other's evidence.",
      lanes: [
        { name: "Literature", saw: "no tables in its workspace" },
        { name: "Experiment", saw: "no literature verdict" },
      ],
    },
    {
      number: "03",
      label: "CHALLENGE",
      title: "Spend effort on surprise",
      body: "Where those answers diverge, a fourth agent searches for a compatible external dataset and tests the claim again.",
    },
    {
      number: "04",
      label: "UPDATE",
      title: "Grow the search tree",
      body: "MCTS scores the branch and picks where the next experiment is worth the compute.",
    },
  ];

  let entries = $state<IndexEntry[]>([]);
  let ready = $state(false);
  let lead = $derived(leadFinding(entries));
  let others = $derived(
    entries
      .filter((entry) => entry.id !== lead?.entry.id)
      .sort((a, b) => (b.published_at ?? b.updated_at).localeCompare(a.published_at ?? a.updated_at)),
  );

  onMount(() => {
    void loadIndex().then((found) => (entries = found)).finally(() => (ready = true));
  });
</script>

<svelte:head>
  <link rel="canonical" href="https://urithiru.eamag.me/" />
</svelte:head>

<div class="landing">
  <nav class="topbar" aria-label="Main navigation">
    <a class="wordmark" href="#top" aria-label="Urithiru home">
      <span class="mark" aria-hidden="true"></span>
      <span>URITHIRU<small>exploration engine</small></span>
    </a>
    <div class="nav-links">
      <a href="#method">How it works</a>
      <a href="#evidence">Evidence</a>
      <a class="workspace-link" href="/workspace">Open workspace <span aria-hidden="true">↗</span></a>
    </div>
  </nav>

  <main id="top">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow"><span></span>BAYESIAN SURPRISE IN MONTE CARLO SEARCH TREES</p>
        <h1>Agentic AI autoresearch grounded in your datasets.</h1>
        <p class="intro">
          It proposes the hypothesis, writes and runs the experiment, then searches for
          external data that could challenge the result.
        </p>
        <div class="hero-actions">
          <a class="primary" href="/workspace">Explore published runs <span aria-hidden="true">→</span></a>
          <a class="secondary" href="#method">How it works <span aria-hidden="true">↓</span></a>
        </div>
      </div>

      <figure class="search-visual">
        <figcaption>
          <span>MONTE CARLO SEARCH TREE</span>
          <span>SCHEMATIC</span>
        </figcaption>
        <div class="tree-field" aria-hidden="true">
          <svg viewBox="0 0 620 400" role="presentation" preserveAspectRatio="none">
            <path class="edge" d="M310 48 L124 152" />
            <path class="edge" d="M310 48 L298 160" />
            <path class="edge hot" d="M310 48 L490 144" />
            <path class="edge dim" d="M124 152 L74 264" />
            <path class="edge dim" d="M124 152 L186 264" />
            <path class="edge dim" d="M298 160 L273 272" />
            <path class="edge hot" d="M490 144 L508 256" />
            <path class="edge hot" d="M508 256 L434 352" />
            <path class="edge dim" d="M508 256 L570 352" />
          </svg>
          <div class="node root" style="--x:50%;--y:12%"><b>ROOT</b><small>tables</small></div>
          <div class="node" style="--x:20%;--y:38%"><b>H₁</b><small>0.18</small></div>
          <div class="node" style="--x:48%;--y:40%"><b>H₂</b><small>0.64</small></div>
          <div class="node picked" style="--x:79%;--y:36%"><b>H₃</b><small>1.25</small></div>
          <div class="node tiny" style="--x:12%;--y:66%"><b>H₄</b></div>
          <div class="node tiny" style="--x:30%;--y:66%"><b>H₅</b></div>
          <div class="node tiny" style="--x:44%;--y:68%"><b>H₆</b></div>
          <div class="node overturned" style="--x:82%;--y:64%"><b>H₇</b><small>opposed</small></div>
          <div class="node tiny picked" style="--x:70%;--y:88%"><b>H₈</b></div>
          <div class="node tiny" style="--x:92%;--y:88%"><b>H₉</b></div>
        </div>
      </figure>
    </section>

    <section class="method" id="method">
      <header class="section-head">
        <p class="eyebrow"><span></span>THE SEARCH LOOP</p>
        <h2>Test a claim from several evidence paths.</h2>
      </header>

      <div class="steps">
        {#each STEPS as step (step.number)}
          <article>
            <p class="step-top"><span>{step.number}</span>{step.label}</p>
            <h3>{step.title}</h3>
            <p class="step-body">{step.body}</p>
            {#if step.lanes}
              <div class="lanes">
                {#each step.lanes as lane (lane.name)}
                  <p><b>{lane.name}</b><span>{lane.saw}</span></p>
                {/each}
              </div>
            {/if}
          </article>
        {/each}
      </div>
    </section>

    <section class="evidence" id="evidence">
      <header class="section-head">
        <p class="eyebrow"><span></span>LIVE EVIDENCE</p>
        <h2>The lead view is selected by a fixed rule, not editorially.</h2>
      </header>

      {#if lead}
        <a
          class="finding"
          style={`--result:${opposed(lead.found) ? "var(--red)" : "var(--green)"}`}
          href={`/workspace?run=${lead.entry.id}&node=${lead.found.node}`}
        >
          <p class="finding-top">
            <span class="verdict">{opposed(lead.found) ? "EXTERNAL RESULT OPPOSED IT" : "EXTERNAL RESULT ALIGNED"}</span>
            <span>{runName(lead.entry)} · {lead.found.node.replace("node_", "NODE ")}</span>
          </p>
          <h3>{lead.found.claim}</h3>
          <div class="chain">
            {#each STAGES as stage, index (stage.key)}
              <div class:final={index === STAGES.length - 1}>
                <span class="stage">{stage.key}</span>
                <b>{lead.found[stage.key].toFixed(2)}</b>
                <i><span style={`width:${lead.found[stage.key] * 100}%`}></span></i>
                <span class="saw">{stage.saw}</span>
              </div>
            {/each}
          </div>
          <p class="finding-foot">
            <span>The external result moved the belief by <b>{moved(lead.found).toFixed(2)}</b>.</span>
            <span class="open">Inspect this node →</span>
          </p>
        </a>
        <p class="caveat">
          Beliefs, metrics, validity flags and provenance are agent-reported assessments
          that require review, not calibrated statistical confidence.
        </p>
      {:else if !ready}
        <div class="finding loading">Loading published runs…</div>
      {:else}
        <div class="finding loading">
          No runs are published in this build yet. Use <code>urithiru publish</code>, then rebuild the site.
        </div>
      {/if}

      {#if others.length}
        <ul class="more">
          {#each others as entry (entry.id)}
            <li>
              <a href={`/workspace?run=${entry.id}${entry.highlight ? `&node=${entry.highlight.node}` : ""}`}>
                <b>{runName(entry)}</b>
                <span>{entry.completed ?? 0}/{entry.requested ?? 0} hypotheses</span>
                <i aria-hidden="true">→</i>
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </main>

  <footer>
    <a class="wordmark" href="#top">
      <span class="mark" aria-hidden="true"></span>
      <span>URITHIRU<small>exploration engine</small></span>
    </a>
    <p>Research prototype · inspect every artifact</p>
    <a class="workspace-link" href="/workspace">Open workspace <span aria-hidden="true">↗</span></a>
  </footer>
</div>

<style>
  :global(html) { scroll-behavior: smooth; }
  .landing { min-height: 100vh; overflow-x: clip; background: var(--bg); }
  .topbar, main, footer { width: min(1120px, calc(100% - 48px)); margin-inline: auto; }

  .topbar { height: 72px; display: flex; align-items: center; justify-content: space-between; }
  .wordmark { display: flex; align-items: center; gap: 10px; color: var(--text); text-decoration: none; }
  .wordmark > span:last-child { font-size: 11px; font-weight: 700; letter-spacing: .16em; }
  .wordmark small { display: block; margin-top: 2px; color: var(--faint); font-size: 8px; font-weight: 500; letter-spacing: .08em; }
  .mark { width: 18px; height: 18px; position: relative; display: block; border: 1px solid var(--violet); border-radius: 50%; }
  .mark::before { content: ""; width: 5px; height: 5px; position: absolute; inset: 6px; border-radius: 50%; background: var(--violet); }
  .nav-links { display: flex; align-items: center; gap: 24px; }
  .nav-links a { color: var(--dim); font-size: 13px; text-decoration: none; }
  .nav-links a:hover { color: var(--text); }
  .workspace-link { padding: 8px 12px; border: 1px solid var(--line); border-radius: 6px; }
  .workspace-link:hover { border-color: var(--edge); color: var(--text); }

  .eyebrow { display: flex; align-items: center; gap: 10px; margin: 0 0 18px; color: var(--violet); font: 10px var(--mono); letter-spacing: .13em; }
  .eyebrow span { width: 22px; height: 1px; background: currentColor; }

  .hero { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(380px, .8fr); gap: 60px; align-items: center; padding: 56px 0 84px; }
  h1 { margin: 0; color: var(--text); font-size: clamp(34px, 4vw, 48px); font-weight: 500; letter-spacing: -.035em; line-height: 1.12; text-wrap: balance; }
  .intro { max-width: 50ch; margin: 22px 0 0; color: var(--text-soft); font-size: 16px; line-height: 1.65; }
  .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }
  .hero-actions a { min-height: 42px; display: inline-flex; align-items: center; gap: 20px; padding: 0 16px; border-radius: 6px; font-size: 13px; text-decoration: none; }
  .primary { color: var(--bg); background: var(--violet); }
  .primary:hover { background: var(--accent-text); }
  .secondary { border: 1px solid var(--line); color: var(--text-soft); }
  .secondary:hover { border-color: var(--edge); }

  .search-visual { margin: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); overflow: hidden; }
  figcaption { height: 40px; display: flex; align-items: center; justify-content: space-between; padding: 0 14px; border-bottom: 1px solid var(--line); color: var(--faint); font: 9px var(--mono); letter-spacing: .1em; }
  .tree-field {
    height: 360px;
    position: relative;
    --grid: color-mix(in srgb, var(--line) 55%, var(--panel));
    background-image:
      linear-gradient(var(--grid) 1px, transparent 1px),
      linear-gradient(90deg, var(--grid) 1px, transparent 1px);
    background-size: 28px 28px;
  }
  .tree-field svg { position: absolute; inset: 0; width: 100%; height: 100%; }
  .edge { fill: none; stroke: var(--edge); stroke-width: 1.2; }
  .edge.dim { stroke: var(--line); }
  .edge.hot { stroke: var(--violet); stroke-width: 1.6; }
  .node {
    width: 48px; height: 48px;
    position: absolute; left: var(--x); top: var(--y);
    display: grid; place-content: center;
    transform: translate(-50%, -50%);
    border: 1px solid var(--edge); border-radius: 50%;
    color: var(--dim); background: var(--panel); text-align: center;
  }
  .node b { font: 10px var(--mono); font-weight: 500; }
  .node small { margin-top: 1px; color: var(--faint); font: 8px var(--mono); }
  .node.tiny { width: 36px; height: 36px; }
  .node.root { color: var(--text); }
  .node.picked { border-color: var(--violet); color: var(--violet); }
  .node.overturned { width: 62px; height: 62px; border-color: var(--red); color: var(--red); }

  .method, .evidence { padding: 76px 0; border-top: 1px solid var(--line); scroll-margin-top: 24px; }
  .section-head { margin-bottom: 40px; }
  .section-head h2 { max-width: 22ch; margin: 0; color: var(--text); font-size: clamp(26px, 3vw, 34px); font-weight: 500; letter-spacing: -.03em; line-height: 1.2; }

  .steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; border: 1px solid var(--line); border-radius: 6px; background: var(--line); overflow: hidden; }
  .steps article { padding: 20px; background: var(--panel); }
  .step-top { display: flex; justify-content: space-between; margin: 0 0 28px; color: var(--faint); font: 9px var(--mono); letter-spacing: .1em; }
  .steps h3 { margin: 0 0 8px; color: var(--text); font-size: 15px; font-weight: 600; letter-spacing: -.01em; }
  .step-body { margin: 0; color: var(--dim); font-size: 13px; line-height: 1.6; }
  .lanes { display: grid; gap: 10px; margin-top: 16px; padding-left: 12px; border-left: 1px solid var(--edge); }
  .lanes p { display: grid; gap: 1px; margin: 0; }
  .lanes b { color: var(--text); font-size: 12px; font-weight: 600; }
  .lanes span { color: var(--faint); font-size: 12px; }

  .finding { display: block; padding: 24px 26px; border: 1px solid var(--line); border-radius: 6px; color: var(--text); background: var(--panel); text-decoration: none; }
  .finding:hover { border-color: var(--edge); }
  .finding-top { display: flex; justify-content: space-between; gap: 18px; margin: 0; color: var(--faint); font: 9px var(--mono); letter-spacing: .08em; }
  .verdict { color: var(--result); }
  .finding h3 { max-width: 80ch; margin: 16px 0 26px; font-size: clamp(18px, 2vw, 22px); font-weight: 450; letter-spacing: -.02em; line-height: 1.45; }
  .chain { display: grid; grid-template-columns: repeat(4, 1fr); gap: 22px; }
  .chain > div { display: grid; gap: 5px; }
  .stage { color: var(--faint); font: 9px var(--mono); letter-spacing: .08em; text-transform: uppercase; }
  .chain b { font-size: 24px; font-weight: 450; font-variant-numeric: tabular-nums; }
  .chain i { height: 3px; border-radius: 2px; background: var(--line); }
  .chain i span { height: 100%; display: block; border-radius: 2px; background: var(--violet); }
  .saw { color: var(--faint); font-size: 11px; }
  .chain .final b { color: var(--result); }
  .chain .final i span { background: var(--result); }
  .finding-foot { display: flex; justify-content: space-between; align-items: baseline; gap: 20px; margin: 24px 0 0; padding-top: 16px; border-top: 1px solid var(--line); color: var(--dim); font-size: 13px; }
  .finding-foot b { color: var(--text); font-variant-numeric: tabular-nums; }
  .open { color: var(--violet); white-space: nowrap; }
  .loading { display: grid; place-items: center; min-height: 180px; color: var(--faint); font-size: 13px; }
  .caveat { margin: 12px 2px 0; color: var(--faint); font-size: 12px; }

  .more { display: grid; gap: 1px; margin: 24px 0 0; padding: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--line); list-style: none; overflow: hidden; }
  .more a { display: grid; grid-template-columns: 1fr auto auto; gap: 4px 16px; align-items: center; padding: 13px 16px; background: var(--panel); color: var(--text); text-decoration: none; }
  .more a:hover { background: var(--sidebar); }
  .more b { font-size: 13px; font-weight: 500; }
  .more span { color: var(--faint); font-size: 12px; }
  .more i { color: var(--dim); font-style: normal; }

  footer { min-height: 88px; display: flex; align-items: center; justify-content: space-between; gap: 20px; border-top: 1px solid var(--line); color: var(--faint); font-size: 12px; }
  footer p { margin: 0; }

  @media (max-width: 940px) {
    .hero { grid-template-columns: 1fr; gap: 44px; padding-bottom: 60px; }
    .search-visual { width: min(600px, 100%); }
    .steps { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 640px) {
    .topbar, main, footer { width: min(100% - 32px, 1120px); }
    .nav-links > a:not(.workspace-link) { display: none; }
    .eyebrow { font-size: 9px; letter-spacing: .1em; }
    .hero { padding: 40px 0 52px; }
    .tree-field { height: 300px; }
    .node { width: 40px; height: 40px; }
    .node.tiny { width: 30px; height: 30px; }
    .node.overturned { width: 52px; height: 52px; }
    .node small { font-size: 7px; }
    .method, .evidence { padding: 56px 0; }
    .steps { grid-template-columns: 1fr; }
    .finding { padding: 20px 18px; }
    .finding-top { flex-direction: column; gap: 6px; }
    .chain { grid-template-columns: 1fr 1fr; gap: 26px 18px; }
    .finding-foot { flex-direction: column; align-items: flex-start; gap: 10px; }
    .more a { grid-template-columns: 1fr auto; }
    .more i { grid-area: 1 / 2; }
    .more span { grid-area: 2 / 1 / 3 / -1; }
    footer { flex-direction: column; align-items: flex-start; padding: 26px 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    :global(html) { scroll-behavior: auto; }
  }
</style>
