<script lang="ts">
  import { SURPRISAL_STEPS } from "../lib/run";

  const steps = [0, ...SURPRISAL_STEPS];
</script>

<span class="legend">
  <span class="caption">data vs. literature</span>
  <span class="ramp">
    {#each steps as lower, index}
      <span
        class="step"
        style={`background:var(--kl-${index + 1})`}
        title={index === steps.length - 1
          ? `${lower} nats and above — the data and the literature disagreed most here`
          : `${lower} to ${SURPRISAL_STEPS[index]} nats`}
      ></span>
    {/each}
  </span>
  <span class="scale">agreed → disagreed</span>
</span>

<style>
  .legend { display: inline-flex; align-items: center; gap: 8px; margin-left: auto; }
  .caption { color: var(--faint); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
  .ramp { display: inline-flex; gap: 2px; }
  .step { width: 16px; height: 6px; border-radius: 1px; }
  .scale { color: var(--faint); font: 10px var(--mono); letter-spacing: 0; text-transform: none; }
</style>
