import type { Capabilities, IndexEntry, LaunchInput, LaunchResult } from "./types";

const TOKEN_KEY = "urithiru.operator-token";

async function answer<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(data.error ?? `Request failed with status ${response.status}`);
  return data;
}

/**
 * The operator token lives in this tab only. Reading runs never needs it; starting or
 * cancelling one does, and the server is what actually decides -- this is a convenience
 * so the token is typed once per session, not a check of any kind.
 */
export function getToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // A browser that refuses storage still works; the token is retyped per action.
  }
}

function authorized(): HeadersInit {
  const token = getToken();
  return token ? { authorization: `Bearer ${token}` } : {};
}

export async function loadCapabilities(): Promise<Capabilities> {
  try {
    return await answer<Capabilities>(await fetch("/api/capabilities", { cache: "no-store" }));
  } catch {
    // A statically served copy has no API at all, which is a read-only deployment.
    return { launchEnabled: false };
  }
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
  if (input.token) setToken(input.token);
  return answer<LaunchResult>(
    await fetch("/api/runs", { method: "POST", body: form, headers: authorized() }),
  );
}

export async function extendRun(id: string, steps: number): Promise<LaunchResult> {
  return answer<LaunchResult>(
    await fetch("/api/runs", {
      method: "PATCH",
      headers: { "content-type": "application/json", ...authorized() },
      body: JSON.stringify({ id, steps }),
    }),
  );
}

export async function cancelRun(id: string): Promise<void> {
  await answer(
    await fetch("/api/runs", {
      method: "DELETE",
      headers: { "content-type": "application/json", ...authorized() },
      body: JSON.stringify({ id }),
    }),
  );
}

