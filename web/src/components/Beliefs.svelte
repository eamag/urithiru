<script lang="ts">
  import { chain } from "../lib/run";
  import type { Evaluation } from "../lib/types";

  let { evaluation }: { evaluation: Evaluation } = $props();

  const INSET = 4;
  let hops = $derived(chain(evaluation));
  let points = $derived(
    hops.map((hop, index) => ({
      ...hop,
      x: INSET + (index / (hops.length - 1)) * (100 - 2 * INSET),
      y: hop.value === null ? null : (1 - hop.value) * 100,
    })),
  );
  let path = $derived(
    points
      .filter((point) => point.y !== null)
      .map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`)
      .join(" "),
  );
</script>

<figure class="beliefs">
  <div class="chart">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d={path} />
    </svg>
    {#each points as point}
      {#if point.y !== null}
        <span class="dot {point.stage}" style={`left:${point.x}%;top:${point.y}%`}></span>
      {/if}
    {/each}
  </div>
  <figcaption>
    {#each hops as hop}
      <div class:absent={hop.value === null}>
        <b>{hop.value === null ? "—" : hop.value.toFixed(2)}</b>
        <span>{hop.stage}</span>
        <small>{hop.label}</small>
      </div>
    {/each}
  </figcaption>
</figure>

<style>
  .beliefs { margin: 0; }
  .chart {
    position: relative;
    height: 58px;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
  }
  .chart::before {
    content: "";
    position: absolute;
    inset: 50% 0 auto;
    border-top: 1px dashed var(--line);
  }
  svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
  path { fill: none; stroke: var(--dim); stroke-width: 1.25; vector-effect: non-scaling-stroke; }
  .dot {
    position: absolute;
    width: 7px;
    height: 7px;
    margin: -3.5px 0 0 -3.5px;
    border-radius: 50%;
    background: var(--dim);
  }
  .dot.experiment { background: var(--text); }
  .dot.external { background: var(--violet); }
  figcaption {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 11px;
  }
  figcaption div { display: flex; flex-direction: column; gap: 1px; }
  figcaption .absent { opacity: 0.4; }
  b { font: 400 15px/1.2 var(--mono); }
  @media (max-width: 560px) {
    figcaption { grid-template-columns: repeat(2, 1fr); gap: 12px 16px; }
  }
  span { font-size: 11px; color: var(--dim); }
  small { font-size: 10px; color: var(--faint); }
</style>
