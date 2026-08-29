<script lang="ts">
  import { Check, CircleDot, Clock3, TriangleAlert } from "lucide-svelte";
  import type { RunStatus } from "../lib/types";

  export let status: RunStatus;
  export let compact = false;
</script>

<span class:compact class="status-pill {status}">
  {#if status === "running"}
    <CircleDot size={compact ? 11 : 12} />
  {:else if status === "completed"}
    <Check size={compact ? 11 : 12} strokeWidth={2.4} />
  {:else if status === "failed"}
    <TriangleAlert size={compact ? 11 : 12} />
  {:else}
    <Clock3 size={compact ? 11 : 12} />
  {/if}
  {status}
</span>
