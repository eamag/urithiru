import type { IndexEntry, LaunchInput, LaunchResult } from "./types";

async function answer<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(data.error ?? `Request failed with status ${response.status}`);
  return data;
}

export async function listRuns(): Promise<IndexEntry[]> {
  return answer<IndexEntry[]>(await fetch(`/api/runs?t=${Date.now()}`, { cache: "no-store" }));
}

export async function launchRun(input: LaunchInput): Promise<LaunchResult> {
  const form = new FormData();
  for (const file of input.data) form.append("data", file);
  for (const file of input.metadataFiles) form.append("metadata_file", file);
  form.set("title", input.title);
  form.set("metadata", input.metadata);
  form.set("steps", String(input.steps));
  form.set("seed", String(input.seed));
  for (const [stage, value] of Object.entries(input.minutes)) {
    if (Number.isFinite(value) && Number(value) > 0) form.set(`${stage}_minutes`, String(value));
  }
  return answer<LaunchResult>(await fetch("/api/runs", { method: "POST", body: form }));
}

export async function cancelRun(run: string): Promise<void> {
  await answer(await fetch("/api/runs", { method: "DELETE", headers: { "content-type": "application/json" }, body: JSON.stringify({ run }) }));
}
