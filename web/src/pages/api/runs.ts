import type { APIRoute } from "astro";
import { overLaunchLimit, refuse } from "../../lib/guard";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, extname, resolve } from "node:path";

export const prerender = false;

const REPO = resolve(
  import.meta.env.URITHIRU_ROOT ??
    process.env.URITHIRU_ROOT ??
    (basename(process.cwd()) === "web" ? resolve(process.cwd(), "..") : process.cwd()),
);
const WEB = resolve(REPO, "web");
// Where published runs live. In development that is the source tree's own `public/runs`;
// a container points this at the directory the built server already serves, so a run
// published while the server is up is visible without a rebuild.
const RUNS = resolve(
  import.meta.env.URITHIRU_RUNS ?? process.env.URITHIRU_RUNS ?? resolve(WEB, "public/runs"),
);
// Only the run references live here: this directory is never served and never published.
const WORK = resolve(
  import.meta.env.URITHIRU_WORK ?? process.env.URITHIRU_WORK ?? resolve(REPO, ".work/web"),
);
// Titles are UI text and sit with the runs they name, so a built image carries them and
// a published copy stays self-describing.
const LABELS = resolve(RUNS, "labels.json");
// Kept out of public/runs on purpose: the published artifacts identify a run by its id
// alone, so the bucket it lives in never reaches a browser. Only this server resolves one.
const REFERENCES = resolve(WORK, "references.json");
const CONFIG = resolve(
  import.meta.env.URITHIRU_CONFIG ?? process.env.URITHIRU_CONFIG ?? resolve(REPO, "configs/google.local.toml"),
);
const DATA_SUFFIXES = new Set([".csv", ".tsv", ".parquet", ".xlsx", ".xls"]);
// A public deployment should not accept a laptop-sized upload; the operator raises this
// when running locally against their own data.
const INPUT_LIMIT = Number(process.env.URITHIRU_UPLOAD_MIB ?? 100) * 1024 * 1024;
const STAGES = ["proposal", "search", "code", "external"] as const;

interface CommandResult {
  stdout: string;
  stderr: string;
}

// How to invoke the CLI. A checkout runs it through uv; an image that already has it
// installed sets URITHIRU_CLI=urithiru, because there is no project for uv to sync.
const CLI = (process.env.URITHIRU_CLI ?? "uv run urithiru").split(" ").filter(Boolean);

async function command(args: string[], timeoutMs = 180_000): Promise<CommandResult> {
  return await new Promise((accept, reject) => {
    const child = spawn(CLI[0], [...CLI.slice(1), ...args], { cwd: REPO, env: process.env });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += String(chunk)));
    child.stderr.on("data", (chunk) => (stderr += String(chunk)));
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs);
    child.on("error", reject);
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) accept({ stdout, stderr });
      else reject(new Error(stderr.trim() || stdout.trim() || `urithiru exited with status ${code}`));
    });
  });
}

async function readJson<T>(path: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readFile(path, "utf-8")) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return fallback;
    throw error;
  }
}

async function remember(path: string, id: string, value: string): Promise<void> {
  if (!value.trim()) return;
  await mkdir(dirname(path), { recursive: true });
  const store = await readJson<Record<string, string>>(path, {});
  store[id] = value.trim().slice(0, 200);
  const temporary = `${path}.tmp`;
  await writeFile(temporary, `${JSON.stringify(store, null, 2)}\n`, "utf-8");
  await rename(temporary, path);
}

/**
 * What a failure may say out loud.
 *
 * The CLI quotes the run's `gs://` reference and the profile path in its errors, and both
 * name where this deployment runs. An operator holding the token still gets the useful
 * part of the message; the location is not part of it.
 */
function safeMessage(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.replaceAll(/gs:\/\/\S+/g, "<run location>").split(CONFIG).join("<operator profile>");
}

function safeName(name: string, index: number): string {
  const cleaned = basename(name).replace(/[^\p{L}\p{N}._ -]/gu, "_");
  return `${String(index).padStart(3, "0")}_${cleaned || "upload"}`;
}

function parseCliJson(stdout: string): { run: string; execution?: string } {
  const start = stdout.indexOf("{");
  if (start < 0) throw new Error(`Urithiru returned no launch record: ${stdout.trim()}`);
  return JSON.parse(stdout.slice(start)) as { run: string; execution?: string };
}

function publish(run: string): void {
  const child = spawn(
    CLI[0],
    [...CLI.slice(1), "publish", run, "--output", RUNS, "--watch"],
    { cwd: REPO, env: process.env, detached: true, stdio: "ignore" },
  );
  child.unref();
}

export const GET: APIRoute = async () => {
  const [entries, labels] = await Promise.all([
    readJson<Array<Record<string, unknown>>>(resolve(RUNS, "index.json"), []),
    readJson<Record<string, string>>(LABELS, {}),
  ]);
  return Response.json(entries.map((entry) => ({ ...entry, title: labels[String(entry.id)] })));
};

export const POST: APIRoute = async ({ request }) => {
  const refusal = refuse(request);
  if (refusal) return Response.json({ error: refusal.error }, { status: refusal.status });
  const form = await request.formData();
  const data = form.getAll("data").filter((value): value is File => value instanceof File);
  const metadataFiles = form.getAll("metadata_file").filter((value): value is File => value instanceof File);
  const metadataText = String(form.get("metadata") ?? "").trim();
  const title = String(form.get("title") ?? "").trim();
  const steps = Math.min(12, Math.max(1, Number(form.get("steps") ?? 1) || 1));
  const seed = Number(form.get("seed") ?? 42) || 42;
  const total = [...data, ...metadataFiles].reduce((bytes, file) => bytes + file.size, 0) + metadataText.length;

  if (!data.length) return Response.json({ error: "Choose at least one data file." }, { status: 400 });
  if (total > INPUT_LIMIT) return Response.json({ error: "The complete upload exceeds 100 MiB." }, { status: 413 });
  const rejected = data.filter((file) => !DATA_SUFFIXES.has(extname(file.name).toLowerCase()));
  if (rejected.length) {
    return Response.json({ error: `Unsupported data file: ${rejected.map((file) => file.name).join(", ")}` }, { status: 400 });
  }
  // Counted only once the request is known to be well formed, so a typo costs no quota.
  const throttled = overLaunchLimit();
  if (throttled) return Response.json({ error: throttled.error }, { status: throttled.status });

  const upload = resolve(WORK, "uploads", randomUUID());
  await mkdir(upload, { recursive: true });
  const dataPaths: string[] = [];
  const metadataPaths: string[] = [];

  try {
    for (const [index, file] of data.entries()) {
      const path = resolve(upload, safeName(file.name, index));
      await writeFile(path, new Uint8Array(await file.arrayBuffer()));
      dataPaths.push(path);
    }
    for (const [index, file] of metadataFiles.entries()) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      const path = resolve(upload, safeName(file.name, index));
      await writeFile(path, bytes);
      metadataPaths.push(path);
    }
    if (title || metadataText) {
      const path = resolve(upload, "context.md");
      await writeFile(path, `${title ? `# ${title}\n\n` : ""}${metadataText}\n`, "utf-8");
      metadataPaths.push(path);
    }

    const args = ["run", "--config", CONFIG];
    for (const path of dataPaths) args.push("--data", path);
    for (const path of metadataPaths) args.push("--metadata", path);
    args.push("--steps", String(steps), "--seed", String(seed));
    // Absent or unparseable stays absent, so the operator profile's value stands.
    for (const stage of STAGES) {
      const raw = form.get(`${stage}_minutes`);
      if (raw === null) continue;
      const value = Math.round(Number(raw));
      if (Number.isFinite(value) && value >= 1 && value <= 60) args.push(`--${stage}-minutes`, String(value));
    }
    const result = parseCliJson((await command(args)).stdout);
    const id = result.run.replace(/\/$/, "").split("/").at(-1) ?? result.run;
    await remember(LABELS, id, title);
    await remember(REFERENCES, id, result.run);
    publish(result.run);
    await rm(upload, { recursive: true });
    // The reference stays on this side: the browser only ever needs the run's id.
    return Response.json({ id, execution: result.execution }, { status: 201 });
  } catch (error) {
    return Response.json({ error: safeMessage(error) }, { status: 500 });
  }
};

export const PATCH: APIRoute = async ({ request }) => {
  const refusal = refuse(request);
  if (refusal) return Response.json({ error: refusal.error }, { status: refusal.status });
  const { id, steps } = (await request.json()) as { id?: string; steps?: number };
  if (!id) return Response.json({ error: "Run ID is required." }, { status: 400 });
  if (!steps || steps < 1) return Response.json({ error: "A positive step count is required." }, { status: 400 });

  const references = await readJson<Record<string, string>>(REFERENCES, {});
  const run = references[id] ?? resolve(RUNS, id);

  try {
    const result = parseCliJson((await command(["resume", run, "--steps", String(steps)], 180_000)).stdout);
    publish(result.run);
    return Response.json({ id, steps, execution: result.execution });
  } catch (error) {
    return Response.json({ error: safeMessage(error) }, { status: 500 });
  }
};

export const DELETE: APIRoute = async ({ request }) => {
  const refusal = refuse(request);
  if (refusal) return Response.json({ error: refusal.error }, { status: refusal.status });
  const { id } = (await request.json()) as { id?: string };
  const references = await readJson<Record<string, string>>(REFERENCES, {});
  const run = id ? references[id] : undefined;
  // A run launched outside this server has no reference here, so it cannot be cancelled
  // from the page. That is the cost of keeping the bucket out of the published index.
  if (!run) return Response.json({ error: "Unknown run." }, { status: 404 });
  try {
    const result = parseCliJson((await command(["cancel", run], 60_000)).stdout);
    return Response.json(result);
  } catch (error) {
    return Response.json({ error: safeMessage(error) }, { status: 500 });
  }
};

