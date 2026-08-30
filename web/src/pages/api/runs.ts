import type { APIRoute } from "astro";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, extname, resolve } from "node:path";

export const prerender = false;

const REPO = resolve(
  import.meta.env.URITHIRU_ROOT ??
    process.env.URITHIRU_ROOT ??
    (basename(process.cwd()) === "web" ? resolve(process.cwd(), "..") : process.cwd()),
);
const WEB = resolve(REPO, "web");
const RUNS = resolve(WEB, "public/runs");
const WORK = resolve(REPO, ".work/web");
const LABELS = resolve(WORK, "labels.json");
const CONFIG = resolve(
  import.meta.env.URITHIRU_CONFIG ?? process.env.URITHIRU_CONFIG ?? resolve(REPO, "configs/google.local.toml"),
);
const DATA_SUFFIXES = new Set([".csv", ".tsv", ".parquet", ".xlsx", ".xls"]);
const INPUT_LIMIT = 100 * 1024 * 1024;
const STAGES = ["proposal", "search", "code", "external"] as const;

interface CommandResult {
  stdout: string;
  stderr: string;
}

async function command(args: string[], timeoutMs = 180_000): Promise<CommandResult> {
  return await new Promise((accept, reject) => {
    const child = spawn("uv", args, { cwd: REPO, env: process.env });
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

async function saveLabel(id: string, title: string): Promise<void> {
  if (!title.trim()) return;
  await mkdir(WORK, { recursive: true });
  const labels = await readJson<Record<string, string>>(LABELS, {});
  labels[id] = title.trim().slice(0, 100);
  const temporary = `${LABELS}.tmp`;
  await writeFile(temporary, `${JSON.stringify(labels, null, 2)}\n`, "utf-8");
  await rename(temporary, LABELS);
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
    "uv",
    ["run", "urithiru", "publish", run, "--output", RUNS, "--watch"],
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

    const args = ["run", "urithiru", "run", "--config", CONFIG];
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
    await saveLabel(id, title);
    publish(result.run);
    await rm(upload, { recursive: true });
    return Response.json({ ...result, id }, { status: 201 });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
};

export const DELETE: APIRoute = async ({ request }) => {
  const { run } = (await request.json()) as { run?: string };
  const entries = await readJson<Array<{ run: string }>>(resolve(RUNS, "index.json"), []);
  if (!run || !entries.some((entry) => entry.run === run)) {
    return Response.json({ error: "Unknown run." }, { status: 404 });
  }
  try {
    const result = parseCliJson((await command(["run", "urithiru", "cancel", run], 60_000)).stdout);
    return Response.json(result);
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
};
