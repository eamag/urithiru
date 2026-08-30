<script lang="ts">
  import type { Checkpoint, CheckpointNode } from "../lib/types";

  let { checkpoint, selectedId, onselect }: { checkpoint: Checkpoint; selectedId: string; onselect: (id: string) => void } = $props();

  // Node boxes are laid out on a grid and the edges drawn behind them, so the claims stay
  // real wrapping text instead of SVG <text> that cannot reflow.
  const COLUMN = 176;
  const ROW = 92;
  const BOX = 148;
  const PAD = 14;

  interface Placed {
    node: CheckpointNode;
    depth: number;
    row: number;
    parent: string | null;
  }

  /** Depth sets the column; each leaf takes the next row and a parent centres on its children. */
  function layout(nodes: CheckpointNode[]): Placed[] {
    const children = new Map<string | null, CheckpointNode[]>();
    for (const node of nodes) children.set(node.parent_id, [...(children.get(node.parent_id) ?? []), node]);
    const placed: Placed[] = [];
    let next = 0;
    const visit = (node: CheckpointNode, depth: number): number => {
      const below = children.get(node.id) ?? [];
      const rows = below.map((child) => visit(child, depth + 1));
      const row = rows.length ? (rows[0] + rows[rows.length - 1]) / 2 : next++;
      placed.push({ node, depth, row, parent: node.parent_id });
      return row;
    };
    for (const root of children.get(null) ?? []) visit(root, 0);
    return placed;
  }

  let placed = $derived(layout(checkpoint.nodes));
  let byId = $derived(new Map(placed.map((item) => [item.node.id, item])));
  let depth = $derived(Math.max(0, ...placed.map((item) => item.depth)));
  let rows = $derived(Math.max(1, ...placed.map((item) => item.row + 1)));
  let width = $derived(depth * COLUMN + BOX + PAD * 2);
  let height = $derived(rows * ROW + PAD * 2);
  let pending = $derived(new Set(checkpoint.pending));

  function x(item: Placed): number {
    return PAD + item.depth * COLUMN;
  }

  function y(item: Placed): number {
    return PAD + item.row * ROW;
  }

  /** An elbow with rounded corners reads as a tree branch at any column spacing. */
  function edge(parent: Placed, child: Placed): string {
    const x1 = x(parent) + BOX;
    const y1 = y(parent) + ROW / 2 - PAD;
    const x2 = x(child);
    const y2 = y(child) + ROW / 2 - PAD;
    const mid = x1 + (x2 - x1) / 2;
    return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
  }

  function state(node: CheckpointNode): string {
    if (node.parent_id === null) return "root";
    if (node.evaluation) return node.evaluation.experiment.empirical_support ? "supported" : "refuted";
    if (pending.has(node.id)) return "running";
    return node.terminal ? "exhausted" : "queued";
  }

  function label(node: CheckpointNode): string {
    if (node.parent_id !== null) return node.claim;
    const duplicates = node.candidates.filter((candidate) => candidate.duplicate_of).length;
    return `${node.candidates.length} proposed · ${duplicates} duplicate`;
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
    <button
      type="button"
      class="node {state(item.node)}"
      class:selected={selectedId === item.node.id}
      style={`left:${x(item)}px;top:${y(item)}px`}
      title={item.node.parent_id === null ? "Proposal round" : item.node.claim}
      onclick={() => onselect(item.node.id)}
    >
      <span class="head">
        <span class="dot"></span>
        <span class="state">{item.node.parent_id === null ? "root" : state(item.node)}</span>
        {#if item.node.visits}<span class="visits">N{item.node.visits}</span>{/if}
      </span>
      <span class="claim">{label(item.node)}</span>
    </button>
  {/each}
</div>

<style>
  .canvas { position: relative; }
  svg { position: absolute; inset: 0; overflow: visible; }
  .edge { fill: none; stroke: var(--edge); stroke-width: 1.5; }

  .node {
    position: absolute;
    width: 148px;
    height: 78px;
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

  .root .dot, .root .state { color: var(--dim); background: var(--dim); }
  .root .state { background: none; }
  .supported .dot { background: var(--green); }
  .supported .state { color: var(--green); }
  .refuted .dot { background: var(--red); }
  .refuted .state { color: var(--red); }
  .running .dot { background: var(--violet); animation: pulse 1.6s ease-in-out infinite; }
  .running .state { color: var(--violet); }
  @keyframes pulse { 50% { opacity: 0.25; } }
</style>
