import { CATEGORIES } from "./types";
import type { Belief, Checkpoint, CheckpointNode, Counts, Evaluation, Highlight, IndexEntry, Run, RunEvent } from "./types";

const BASE = (import.meta.env.PUBLIC_RUN_BASE ?? "/runs").replace(/\/$/, "");
const SCORES = [0, 0.25, 0.5, 0.75, 1];
const FINISHED = ["completed", "exhausted", "failed", "cancelled"];

// These files ship with the site and only change when it is rebuilt, so the
// A cache-busting query is unnecessary here: it would defeat the CDN edge
// cache on every page load for data that cannot have moved.
async function fetchJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${BASE}${path}`);
  return response.ok ? ((await response.json()) as T) : null;
}

export function probTrue(counts: Counts | null | undefined): number | null {
  if (!counts) return null;
  const values = CATEGORIES.map((name) => counts[name] ?? 0);
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return null;
  const mean = values.reduce((sum, value, index) => sum + (value / total) * SCORES[index], 0);
  return (0.5 + 30 * mean) / 31;
}

export function belief(source: Belief | { category_counts: Counts | null } | null): number | null {
  if (!source) return null;
  return probTrue("counts" in source ? source.counts : source.category_counts);
}

export function verdict(evaluation: Evaluation): string {
  const external = belief(evaluation.external);
  if (external === null) return "no external result";
  const code = belief(evaluation.experiment) ?? 0;
  return external > 0.5 === code > 0.5 ? "aligned" : "opposed";
}

export function chain(evaluation: Evaluation) {
  return [
    { stage: "prior", label: "no evidence", value: belief(evaluation.prior) },
    { stage: "literature", label: "data-blind", value: belief(evaluation.literature) },
    { stage: "experiment", label: "seed data", value: belief(evaluation.experiment) },
    { stage: "external", label: "agent-reported", value: belief(evaluation.external) },
  ];
}

export function shortName(path: string): string {
  return (path.split("/").pop() ?? path).replace(/^(\d{3}_)+/, "");
}

export function runName(entry: IndexEntry): string {
  if (entry.title) return entry.title;
  const files = entry.dataset.map(shortName);
  if (!files.length) return `Run ${entry.id.slice(0, 8)}`;
  const shown = files.slice(0, 2).join(" + ");
  return files.length > 2 ? `${shown} + ${files.length - 2} more` : shown;
}

export interface RunGroup {
  key: string;
  name: string;
  entries: IndexEntry[];
}

function groupName(entries: IndexEntry[]): string {
  const titles = entries.map((entry) => entry.title).filter((title): title is string => Boolean(title));
  if (titles.length === entries.length && titles.length > 0) {
    let prefix = titles[0];
    for (const title of titles.slice(1)) {
      let index = 0;
      while (index < prefix.length && index < title.length && prefix[index] === title[index]) index++;
      prefix = prefix.slice(0, index);
    }
    const trimmed = prefix.replace(/[\s\u2014\u2013\-\u00b7,:(]+$/u, "").trim();
    if (trimmed.length >= 4) return trimmed;
  }
  return runName(entries[0]);
}

export function groupByDataset(entries: IndexEntry[]): RunGroup[] {
  const groups = new Map<string, IndexEntry[]>();
  for (const entry of entries) {
    const key = entry.dataset.map(shortName).sort().join("|") || entry.id;
    groups.set(key, [...(groups.get(key) ?? []), entry]);
  }
  return [...groups].map(([key, members]) => ({ key, name: groupName(members), entries: members }));
}

export const SURPRISAL_STEPS = [0.5, 2, 6, 15];
export const SURPRISAL_CEILING = 24;

export function surprisal(node: CheckpointNode): number | null {
  const value = node.evaluation?.surprisal?.kl_code_search;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function surprisalStep(nats: number | null): number {
  if (nats === null) return 0;
  const index = SURPRISAL_STEPS.findIndex((limit) => nats < limit);
  return index === -1 ? SURPRISAL_STEPS.length + 1 : index + 1;
}

export function surprisalWidth(nats: number | null): number {
  if (nats === null || nats <= 0) return 0;
  return Math.min(1, Math.log1p(nats) / Math.log1p(SURPRISAL_CEILING));
}

export function formatNats(value: number): string {
  if (value >= 10) return value.toFixed(0);
  return value >= 1 ? value.toFixed(1) : value.toFixed(2);
}

export function running(status: string): boolean {
  return !FINISHED.includes(status);
}

export function ranked(checkpoint: Checkpoint | null) {
  if (!checkpoint) return [];
  return checkpoint.nodes
    .filter((node) => node.evaluation !== null)
    .sort((a, b) => b.evaluation!.reward - a.evaluation!.reward);
}

export function activeStages(events: RunEvent[]): string[] {
  const open = new Set<string>();
  for (const event of events) {
    if (event.event === "stage_started" && event.stage) open.add(event.stage);
    if ((event.event === "stage_completed" || event.event === "stage_failed") && event.stage) {
      open.delete(event.stage);
    }
  }
  return [...open];
}

// The server route that merged these two files is gone, so the page joins them
// itself: index.json holds the published runs, labels.json the operator titles.
export async function loadIndex(): Promise<IndexEntry[]> {
  const [entries, labels] = await Promise.all([
    fetchJson<IndexEntry[]>("/index.json"),
    fetchJson<Record<string, string>>("/labels.json"),
  ]);
  return (entries ?? []).map((entry) => ({ ...entry, title: labels?.[entry.id] ?? entry.title }));
}

export async function loadRun(entry: IndexEntry): Promise<Run> {
  const [config, checkpoint, log] = await Promise.all([
    fetchJson<Run["config"]>(`/${entry.id}/run.json`),
    fetchJson<Checkpoint>(`/${entry.id}/mcts_state.json`),
    fetch(`${BASE}/${entry.id}/events.jsonl`)
      .then((response) => (response.ok ? response.text() : ""))
      .catch(() => ""),
  ]);
  const events = log
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as RunEvent);
  return { entry, config, checkpoint, events };
}

export function leadFinding(entries: IndexEntry[]): { entry: IndexEntry; found: Highlight } | null {
  const candidates = entries
    .filter((entry): entry is IndexEntry & { highlight: Highlight } => Boolean(entry.highlight))
    .map((entry) => ({ entry, found: entry.highlight }));
  if (candidates.length === 0) return null;
  return candidates.reduce((best, item) => (moved(item.found) > moved(best.found) ? item : best));
}

export function moved(found: Highlight): number {
  return Math.abs(found.experiment - found.external);
}

export function opposed(found: Highlight): boolean {
  return Math.sign(found.experiment - 0.5) !== Math.sign(found.external - 0.5);
}

export function nodeState(node: CheckpointNode, pending: Set<string>): string {
  if (node.parent_id === null) return "root";
  if (node.evaluation) {
    if (verdict(node.evaluation) === "opposed") return "external-opposed";
    return node.evaluation.experiment.empirical_support ? "agent-supported" : "agent-refuted";
  }
  if (pending.has(node.id)) return "running";
  return node.terminal ? "exhausted" : "queued";
}
