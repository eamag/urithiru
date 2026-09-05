<script lang="ts">
  import type { CheckpointNode } from "../lib/types";
  import Finding from "./Finding.svelte";

  let { node, rank, pending }: { node: CheckpointNode; rank: number; pending: boolean } = $props();

  let duplicates = $derived(node.candidates.filter((candidate) => candidate.duplicate_of));
  let rejected = $derived(node.candidates.filter((candidate) => candidate.rejection_reason));
</script>

<section class="inspector">
  {#if node.evaluation}
    <Finding {node} {rank} />
  {:else}
    <article class="waiting">
      <header>
        <span class="state">{node.parent_id === null ? "root" : pending ? "running" : node.terminal ? "exhausted" : "queued"}</span>
        <h3>{node.parent_id === null ? "Proposal round" : node.claim}</h3>
      </header>
      <p class="explain">
        {#if node.parent_id === null}
          The root holds every claim the proposal agent wrote for this dataset, before selection.
        {:else if pending}
          The literature and experiment agents are working on this claim right now, in separate
          workspaces. Neither can see the other's answer.
        {:else if node.terminal}
          This branch produced no further claim worth testing.
        {:else}
          Selected, not started. The search will expand it when a slot frees up.
        {/if}
      </p>
    </article>
  {/if}

  {#if node.candidates.length}
    <details class="candidates" open={!node.evaluation}>
      <summary>
        candidates · {node.candidates.length} proposed, {duplicates.length} duplicate, {rejected.length} rejected
      </summary>
      <ol>
        {#each node.candidates as candidate}
          <li class:muted={candidate.duplicate_of !== null || candidate.rejection_reason !== null}>
            <span>{candidate.claim}</span>
            {#if candidate.duplicate_of}
              <small>duplicate of “{candidate.duplicate_of}”</small>
            {:else if candidate.rejection_reason}
              <small>{candidate.rejection_reason}</small>
            {/if}
          </li>
        {/each}
      </ol>
    </details>
  {/if}
</section>

<style>
  .inspector { min-width: 0; }
  .waiting { padding: 22px; border: 1px solid var(--line); border-radius: 7px; background: var(--panel); }
  .waiting header { display: flex; align-items: baseline; gap: 12px; }
  .state {
    flex: none;
    padding: 1px 7px;
    border: 1px solid var(--line);
    border-radius: 3px;
    color: var(--violet);
    font: 10px var(--mono);
    text-transform: uppercase;
  }
  .waiting h3 { margin: 0; font-size: 15px; font-weight: 500; line-height: 1.5; }
  .explain { margin: 14px 0 0; color: var(--dim); font-size: 12.5px; line-height: 1.7; }
  .candidates { margin-top: 18px; border-top: 1px solid var(--line); padding-top: 14px; }
  summary { color: var(--faint); cursor: pointer; font: 11px var(--mono); text-transform: uppercase; }
  ol { margin: 14px 0 0; padding-left: 22px; }
  li { margin-bottom: 12px; font-size: 12.5px; line-height: 1.6; }
  li.muted { color: var(--faint); }
  small { display: block; margin-top: 3px; color: var(--faint); font: 11px var(--mono); }
</style>
