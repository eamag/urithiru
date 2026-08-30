import { CATEGORIES } from "./types";
import type { Belief, Checkpoint, Counts, Evaluation, IndexEntry, Run, RunEvent } from "./types";

// Where `urithiru publish` put the runs. Point it at a public bucket to skip the copy.
const BASE = (import.meta.env.PUBLIC_RUN_BASE ?? "/runs").replace(/\/$/, "");
const SCORES = [0, 0.25, 0.5, 0.75, 1];
const FINISHED = ["completed", "exhausted", "failed", "cancelled"];

async function fetchJson<T>(path: string): Promise<T | null> {
  const response = await fetch(`${BASE}${path}?t=${Date.now()}`, { cache: "no-store" });
  return response.ok ? ((await response.json()) as T) : null;
}

/** Thirty votes over five categories through a Beta(0.5, 0.5) prior -- `Belief.prob_true`. */
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
  if (external === null) return "no independent data";
  const code = belief(evaluation.experiment) ?? 0;
  return external > 0.5 === code > 0.5 ? "replicated" : "contradicted";
}

/** The four beliefs in the order they were formed. `null` means that stage did not answer. */
export function chain(evaluation: Evaluation) {
  return [
    { stage: "prior", label: "no evidence", value: belief(evaluation.prior) },
    { stage: "literature", label: "data-blind", value: belief(evaluation.literature) },
    { stage: "experiment", label: "seed data", value: belief(evaluation.experiment) },
    { stage: "external", label: "independent", value: belief(evaluation.external) },
  ];
}

export function shortName(path: string): string {
  return (path.split("/").pop() ?? path).replace(/^(\d{3}_)+/, "");
}

/** A run's operator label, or as much of its file list as reads as a name. */
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

/** Runs over the same files are one discovery, and the group takes their shared label. */
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

export function running(status: string): boolean {
  return !FINISHED.includes(status);
}

export function ranked(checkpoint: Checkpoint | null) {
  if (!checkpoint) return [];
  return checkpoint.nodes
    .filter((node) => node.evaluation !== null)
    .sort((a, b) => b.evaluation!.reward - a.evaluation!.reward);
}

/** What each stage is doing right now, read off the tail of the event log. */
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

export async function loadIndex(): Promise<IndexEntry[]> {
  const response = await fetch(`/api/runs?t=${Date.now()}`, { cache: "no-store" });
  return response.ok ? ((await response.json()) as IndexEntry[]) : [];
}

export async function loadRun(entry: IndexEntry): Promise<Run> {
  const [config, checkpoint, log] = await Promise.all([
    fetchJson<Run["config"]>(`/${entry.id}/run.json`),
    fetchJson<Checkpoint>(`/${entry.id}/mcts_state.json`),
    fetch(`${BASE}/${entry.id}/events.jsonl?t=${Date.now()}`, { cache: "no-store" })
      .then((response) => (response.ok ? response.text() : ""))
      .catch(() => ""),
  ]);
  const events = log
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as RunEvent);
  return { entry, config, checkpoint, events };
}
