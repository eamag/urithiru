<script lang="ts">
  import { Maximize2, Minus, Plus } from "lucide-svelte";
  import type { TreeNode } from "../lib/types";

  export let nodes: TreeNode[];
  export let selectedId: string;
  export let onselect: (id: string) => void;

  let zoom = 1;
  const nodeWidth = 166;
  const nodeHeight = 62;
  const horizontalGap = 76;

  type Position = { x: number; y: number };
  let positions = new Map<string, Position>();
  let canvasWidth = 920;
  let canvasHeight = 470;

  $: {
    const maxDepth = Math.max(0, ...nodes.map((node) => node.depth));
    canvasWidth = Math.max(920, 58 + (maxDepth + 1) * (nodeWidth + horizontalGap));
    const grouped = new Map<number, TreeNode[]>();
    nodes.forEach((node) => grouped.set(node.depth, [...(grouped.get(node.depth) ?? []), node]));
    const largestLayer = Math.max(1, ...Array.from(grouped.values()).map((group) => group.length));
    canvasHeight = Math.max(470, 78 + largestLayer * 112);
    positions = new Map();
    grouped.forEach((group, depth) => {
      group.forEach((node, index) => {
        const spacing = canvasHeight / (group.length + 1);
        positions.set(node.id, { x: 48 + depth * (nodeWidth + horizontalGap), y: spacing * (index + 1) - nodeHeight / 2 });
      });
    });
  }

  function edgePath(node: TreeNode): string {
    const from = positions.get(node.parentId ?? "");
    const to = positions.get(node.id);
    if (!from || !to) return "";
    const x1 = from.x + nodeWidth;
    const y1 = from.y + nodeHeight / 2;
    const x2 = to.x;
    const y2 = to.y + nodeHeight / 2;
    const bend = (x2 - x1) * 0.48;
    return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
  }

  function truncate(value: string, length = 23) {
    return value.length > length ? `${value.slice(0, length - 1)}…` : value;
  }
</script>

<div class="tree-shell">
  <div class="tree-toolbar">
    <div class="tree-legend">
      <span><i class="supported"></i> Supported</span>
      <span><i class="refuted"></i> Refuted</span>
      <span><i class="running"></i> Running</span>
      <span><i class="queued"></i> Queued</span>
    </div>
    <div class="zoom-controls" aria-label="Tree zoom controls">
      <button type="button" aria-label="Zoom out" onclick={() => zoom = Math.max(0.7, zoom - 0.1)}><Minus size={14} /></button>
      <span>{Math.round(zoom * 100)}%</span>
      <button type="button" aria-label="Zoom in" onclick={() => zoom = Math.min(1.4, zoom + 0.1)}><Plus size={14} /></button>
      <button type="button" aria-label="Fit tree" onclick={() => zoom = 1}><Maximize2 size={14} /></button>
    </div>
  </div>

  <div class="tree-scroll">
    <svg
      class="tree-canvas"
      style={`width: ${canvasWidth * zoom}px; height: ${canvasHeight * zoom}px`}
      viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
      role="img"
      aria-label="Interactive Monte Carlo tree search"
    >
      <defs>
        <pattern id="dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,.055)" />
        </pattern>
        <filter id="node-shadow" x="-25%" y="-35%" width="150%" height="170%">
          <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#000" flood-opacity="0.28" />
        </filter>
      </defs>
      <rect width="100%" height="100%" fill="url(#dot-grid)" />

      <g class="tree-edges">
        {#each nodes.filter((node) => node.parentId) as node}
          <path d={edgePath(node)} class:active-edge={node.status === "running"} />
        {/each}
      </g>

      {#each nodes as node}
        {@const position = positions.get(node.id)}
        {#if position}
          <g
            class="tree-node {node.status}"
            class:selected={selectedId === node.id}
            transform={`translate(${position.x} ${position.y})`}
            role="button"
            tabindex="0"
            aria-label={`${node.label}: ${node.claim}`}
            onclick={() => onselect(node.id)}
            onkeydown={(event) => (event.key === "Enter" || event.key === " ") && onselect(node.id)}
          >
            <title>{node.claim}</title>
            <rect class="node-halo" x="-4" y="-4" width={nodeWidth + 8} height={nodeHeight + 8} rx="14" />
            <rect class="node-body" width={nodeWidth} height={nodeHeight} rx="11" filter="url(#node-shadow)" />
            <circle class="node-dot" cx="17" cy="18" r="4" />
            <text class="node-label" x="28" y="22">{node.label}</text>
            {#if node.status !== "root"}
              <text class="node-meta" x={nodeWidth - 12} y="22" text-anchor="end">N {node.visits}</text>
            {/if}
            <text class="node-claim" x="14" y="46">{truncate(node.claim)}</text>
            {#if node.status === "running"}<circle class="pulse-ring" cx="17" cy="18" r="7" />{/if}
          </g>
        {/if}
      {/each}
    </svg>
  </div>
</div>

<style>
  .tree-shell { height: 100%; min-height: 520px; display: flex; flex-direction: column; background: #111412; }
  .tree-toolbar { height: 47px; flex: 0 0 auto; padding: 0 14px 0 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .tree-legend { display: flex; align-items: center; gap: 17px; color: var(--text-3); font-size: 10px; letter-spacing: .02em; }
  .tree-legend span { display: flex; align-items: center; gap: 6px; }
  .tree-legend i { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .tree-legend i.supported { background: var(--green); }
  .tree-legend i.refuted { background: var(--red); }
  .tree-legend i.running { background: var(--violet); box-shadow: 0 0 0 3px rgba(170, 137, 255, .12); }
  .tree-legend i.queued { background: #747a75; }
  .zoom-controls { display: flex; align-items: center; gap: 1px; border: 1px solid var(--border); background: var(--surface-2); border-radius: 8px; padding: 2px; }
  .zoom-controls button { width: 27px; height: 25px; border: 0; border-radius: 5px; display: grid; place-items: center; background: transparent; color: var(--text-3); cursor: pointer; }
  .zoom-controls button:hover { background: var(--surface-3); color: var(--text-1); }
  .zoom-controls span { width: 43px; text-align: center; color: var(--text-3); font: 9px var(--font-mono); }
  .tree-scroll { flex: 1; overflow: auto; min-height: 0; overscroll-behavior: contain; }
  .tree-canvas { display: block; min-width: 760px; transition: width .18s ease, height .18s ease; }
  .tree-edges path { fill: none; stroke: #333834; stroke-width: 1.4; }
  .tree-edges path.active-edge { stroke: rgba(170, 137, 255, .5); stroke-dasharray: 6 5; animation: dash 1.2s linear infinite; }
  .tree-node { cursor: pointer; outline: none; }
  .tree-node .node-body { fill: #181b19; stroke: #363b37; stroke-width: 1; transition: stroke .15s ease, fill .15s ease; }
  .tree-node:hover .node-body { fill: #1c201d; stroke: #565c57; }
  .tree-node .node-halo { fill: transparent; stroke: transparent; stroke-width: 1.5; }
  .tree-node.selected .node-halo { stroke: rgba(202, 182, 255, .78); }
  .tree-node.selected .node-body { stroke: rgba(202, 182, 255, .32); }
  .tree-node .node-dot { fill: #747a75; }
  .tree-node.root .node-dot { fill: var(--blue); }
  .tree-node.supported .node-dot { fill: var(--green); }
  .tree-node.refuted .node-dot { fill: var(--red); }
  .tree-node.running .node-dot { fill: var(--violet); }
  .tree-node.running .node-body { stroke: rgba(170, 137, 255, .42); }
  .tree-node .pulse-ring { fill: none; stroke: var(--violet); opacity: .5; animation: pulse 1.8s ease-out infinite; }
  .node-label { fill: #d7dbd7; font: 600 9.5px var(--font-sans); letter-spacing: .03em; }
  .node-meta { fill: #6f766f; font: 8px var(--font-mono); }
  .node-claim { fill: #929991; font: 8.5px var(--font-sans); }
  @keyframes dash { to { stroke-dashoffset: -22; } }
  @keyframes pulse { 0% { transform: scale(.65); opacity: .7; } 80%, 100% { transform: scale(1.8); opacity: 0; } }
  @media (max-width: 700px) { .tree-legend span:nth-child(n+3) { display: none; } }
</style>
