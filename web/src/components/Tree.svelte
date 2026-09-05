<script lang="ts">
  import { belief, formatNats, nodeState, surprisal, surprisalStep, surprisalWidth, verdict } from "../lib/run";
  import type { Checkpoint, CheckpointNode } from "../lib/types";

  let { checkpoint, selectedId, onselect }: { checkpoint: Checkpoint; selectedId: string; onselect: (id: string) => void } = $props();

  const COLUMN = 172;
  const LEVEL = 134;
  const BOX = 156;
  const BOX_HEIGHT = 96;
  const PAD = 14;

  interface Placed {
    node: CheckpointNode;
    depth: number;
    column: number;
    parent: string | null;
  }

  function layout(nodes: CheckpointNode[]): Placed[] {
    const children = new Map<string | null, CheckpointNode[]>();
    for (const node of nodes) children.set(node.parent_id, [...(children.get(node.parent_id) ?? []), node]);
    const placed: Placed[] = [];
    let next = 0;
    const visit = (node: CheckpointNode, depth: number): number => {
      const below = children.get(node.id) ?? [];
      const columns = below.map((child) => visit(child, depth + 1));
      const column = columns.length ? (columns[0] + columns[columns.length - 1]) / 2 : next++;
      placed.push({ node, depth, column, parent: node.parent_id });
      return column;
    };
    for (const root of children.get(null) ?? []) visit(root, 0);
    return placed;
  }

  let placed = $derived(layout(checkpoint.nodes));
  let byId = $derived(new Map(placed.map((item) => [item.node.id, item])));
  let depth = $derived(Math.max(0, ...placed.map((item) => item.depth)));
  let columns = $derived(Math.max(1, ...placed.map((item) => item.column + 1)));
  let width = $derived(columns * COLUMN + PAD * 2);
  let height = $derived(depth * LEVEL + BOX_HEIGHT + PAD * 2);
  let pending = $derived(new Set(checkpoint.pending));

  let boxes: Record<string, HTMLButtonElement | undefined> = {};

  $effect(() => {
    const gentle = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    boxes[selectedId]?.scrollIntoView({
      behavior: gentle ? "smooth" : "auto",
      block: "nearest",
      inline: "center",
    });
  });

  function x(item: Placed): number {
    return PAD + item.column * COLUMN;
  }

  function y(item: Placed): number {
    return PAD + item.depth * LEVEL;
  }

  function edge(parent: Placed, child: Placed): string {
    const x1 = x(parent) + BOX / 2;
    const y1 = y(parent) + BOX_HEIGHT;
    const x2 = x(child) + BOX / 2;
    const y2 = y(child);
    const mid = y1 + (y2 - y1) / 2;
    return `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
  }

  const state = (node: CheckpointNode) => nodeState(node, pending);

  function label(node: CheckpointNode): string {
    if (node.parent_id !== null) return node.claim;
    const duplicates = node.candidates.filter((candidate) => candidate.duplicate_of).length;
    return `${node.candidates.length} proposed · ${duplicates} duplicate`;
  }

  function describe(node: CheckpointNode): string {
    if (node.parent_id === null) return "Proposal round";
    const nats = surprisal(node);
    if (nats === null) return node.claim;
    const lines = [
      node.claim,
      "",
      `Surprisal ${formatNats(nats)} — how far the data ended up from the literature. Higher is more surprising.`,
    ];
    const external = node.evaluation && belief(node.evaluation.external);
    const code = node.evaluation && belief(node.evaluation.experiment);
    if (external !== null && external !== undefined && code !== null && code !== undefined) {
      lines.push(
        `The agent-reported external result was ${verdict(node.evaluation!)}: ${code.toFixed(2)} → ${external.toFixed(2)}.`,
      );
    }
    return lines.join("\n");
  }
</script>

<div class="canvas" style={`width:${width}px;height:${height}px`}>
  <svg {width} {height} aria-hidden="true">
    {#each placed as item (item.node.id)}
      {#if item.parent && byId.has(item.parent)}
        <path class="edge" d={edge(byId.get(item.parent)!, item)} />
      {/if}
    {/each}
  </svg>

  {#each placed as item (item.node.id)}
    {@const nats = surprisal(item.node)}
    <button
      type="button"
      bind:this={boxes[item.node.id]}
      class="node {state(item.node)}"
      class:selected={selectedId === item.node.id}
      style={`left:${x(item)}px;top:${y(item)}px`}
      title={describe(item.node)}
      onclick={() => onselect(item.node.id)}
    >
      <span class="head">
        <span class="dot"></span>
        <span class="state">{item.node.parent_id === null ? "root" : state(item.node)}</span>
        {#if item.node.visits}<span class="visits">N{item.node.visits}</span>{/if}
      </span>
      <span class="claim">{label(item.node)}</span>
      {#if nats !== null}
        <span class="surprisal">
          <span class="rail">
            <span
              class="fill"
              style={`width:${(surprisalWidth(nats) * 100).toFixed(1)}%;background:var(--kl-${surprisalStep(nats)})`}
            ></span>
          </span>
          <span class="nats">{formatNats(nats)}</span>
        </span>
      {/if}
    </button>
  {/each}
</div>

<style>
  .canvas { position: relative; }
  svg { position: absolute; inset: 0; overflow: visible; }
  .edge { fill: none; stroke: var(--edge); stroke-width: 1.5; }

  .node {
    position: absolute;
    width: 156px;
    height: 96px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 9px 10px;
    border: 1px solid var(--line);
    border-radius: 6px;
    color: inherit;
    background: var(--panel);
    cursor: pointer;
    text-align: left;
    font: inherit;
  }
  .node:hover { border-color: var(--accent-edge); }
  .node.selected { border-color: var(--violet); box-shadow: 0 0 0 1px var(--violet); }

  .head { display: flex; align-items: center; gap: 5px; }
  .dot { width: 6px; height: 6px; flex: none; border-radius: 50%; background: var(--faint); }
  .state { color: var(--faint); font: 9px var(--mono); letter-spacing: .06em; text-transform: uppercase; }
  .visits { margin-left: auto; color: var(--faint); font: 9px var(--mono); }

  .claim {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
    font-size: 11px;
    line-height: 1.42;
  }

  .surprisal { display: flex; align-items: center; gap: 6px; margin-top: auto; }
  .rail { flex: 1; height: 4px; min-width: 0; border-radius: 2px; background: var(--line); overflow: hidden; }
  .fill { display: block; height: 100%; border-radius: 2px; }
  .nats { flex: none; color: var(--dim); font: 9px var(--mono); }

  .root .dot, .root .state { color: var(--dim); background: var(--dim); }
  .root .state { background: none; }
  .agent-supported .dot { background: var(--green); }
  .agent-supported .state { color: var(--green); }
  .agent-refuted .dot { background: var(--red); }
  .agent-refuted .state { color: var(--red); }
  .external-opposed .dot { background: var(--kl-4); }
  .external-opposed .state { color: var(--kl-4); }
  .running .dot { background: var(--violet); animation: pulse 1.6s ease-in-out infinite; }
  .running .state { color: var(--violet); }
  @keyframes pulse { 50% { opacity: 0.25; } }

  @media (prefers-reduced-motion: reduce) {
    .running .dot { animation: none; }
  }
</style>
