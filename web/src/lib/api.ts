import type { DiscoveryRun, NewRunInput } from "./types";

const API_BASE = (import.meta.env.PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export const apiConfigured = API_BASE.length > 0;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `Urithiru API returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function listRuns(): Promise<DiscoveryRun[]> {
  const result = await request<DiscoveryRun[] | { runs: DiscoveryRun[] }>("/runs");
  return Array.isArray(result) ? result : result.runs;
}

export async function createRun(input: NewRunInput): Promise<DiscoveryRun> {
  const body = new FormData();
  input.files.forEach((file) => body.append("data", file));
  body.append("title", input.title);
  body.append("metadata", input.metadata);
  body.append("budget", input.budget);
  const result = await request<DiscoveryRun | { run: DiscoveryRun }>("/runs", { method: "POST", body });
  return "run" in result ? result.run : result;
}
