/**
 * Who may start work on this deployment, and how often.
 *
 * Reading a run needs nothing: the page is served from files that name no project and no
 * bucket. Starting one spends money in someone's Google Cloud project and runs
 * agent-authored code there, so it is refused unless the operator set a token on the
 * server. An unconfigured deployment is therefore read-only rather than open, which is
 * the safe way round for a public URL.
 */

const TOKEN = process.env.URITHIRU_LAUNCH_TOKEN?.trim() ?? "";
const WINDOW_MS = 60 * 60 * 1000;
const LIMIT = Number(process.env.URITHIRU_LAUNCH_LIMIT ?? 6);

/** Launch timestamps inside the current window. Per instance, which is the deployment. */
const recent: number[] = [];

export const launchEnabled = TOKEN.length > 0;

/** Constant-time compare, so a wrong token leaks nothing about how wrong it was. */
function sameToken(offered: string): boolean {
  if (offered.length !== TOKEN.length) return false;
  let difference = 0;
  for (let index = 0; index < TOKEN.length; index += 1) {
    difference |= offered.charCodeAt(index) ^ TOKEN.charCodeAt(index);
  }
  return difference === 0;
}

export interface Refusal {
  error: string;
  status: number;
}

/** `null` when the request may proceed, otherwise the response body and status to return. */
export function refuse(request: Request): Refusal | null {
  if (!launchEnabled) {
    return { error: "This deployment is read-only: no launch token is configured.", status: 503 };
  }
  const header = request.headers.get("authorization") ?? "";
  const offered = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!offered || !sameToken(offered)) {
    return { error: "That operator token was not accepted.", status: 401 };
  }
  return null;
}

/** Called only once a launch is actually about to happen, so refusals cost no quota. */
export function overLaunchLimit(): Refusal | null {
  const now = Date.now();
  while (recent.length && now - recent[0] > WINDOW_MS) recent.shift();
  if (recent.length >= LIMIT) {
    return { error: `Launch limit reached: ${LIMIT} runs per hour on this deployment.`, status: 429 };
  }
  recent.push(now);
  return null;
}
