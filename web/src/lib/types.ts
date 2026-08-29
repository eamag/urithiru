export type View = "overview" | "new" | "run";
export type RunStatus = "queued" | "running" | "completed" | "failed";
export type NodeStatus = "root" | "queued" | "running" | "supported" | "refuted" | "inconclusive";
export type Budget = "fast" | "standard" | "deep";
export type Verdict = "replicated" | "contradicted" | "no independent data" | "pending";

export interface Beliefs {
  prior: number;
  literature: number;
  seed?: number;
  external?: number;
}

export interface Metric {
  label: string;
  value: string;
}

export interface EvidenceSource {
  title: string;
  source: string;
  kind: "seed" | "literature" | "external";
  note: string;
}

export interface TestSpecification {
  question: string;
  population: string;
  prediction: string;
  method: string;
  successCriteria: string[];
}

export interface SandboxExecution {
  id: string;
  runtime: string;
  image: string;
  region: string;
  startedAt: string;
  duration: string;
  exitCode?: number;
  stdout: string;
  stderr: string;
}

export interface LogLine {
  time: string;
  level: "info" | "success" | "warning" | "error";
  source: "orchestrator" | "verification" | "external" | "sandbox";
  message: string;
}

export interface NodeArtifact {
  name: string;
  path: string;
  size: string;
  kind: "code" | "json" | "log" | "prompt" | "data" | "marker";
  stage: "proposal" | "verification" | "external" | "run";
  savedAt: string;
  content?: string;
  downloadUrl?: string;
}

export interface TreeNode {
  id: string;
  parentId: string | null;
  label: string;
  claim: string;
  status: NodeStatus;
  depth: number;
  visits: number;
  value: number;
  reward?: number;
  belief?: Beliefs;
  verdict?: Verdict;
  empiricalSupport?: boolean;
  summary?: string;
  rationale?: string;
  metrics?: Metric[];
  sources?: EvidenceSource[];
  code?: string;
  whyProposed?: string;
  literatureRationale?: string;
  seedRationale?: string;
  test?: TestSpecification;
  sandbox?: SandboxExecution;
  logs?: LogLine[];
  artifacts?: NodeArtifact[];
}

export interface RunEvent {
  id: string;
  title: string;
  detail: string;
  time: string;
  status: "complete" | "active" | "waiting" | "warning";
}

export interface DiscoveryRun {
  id: string;
  name: string;
  datasetName: string;
  datasetSize: string;
  rows: string;
  columns: number;
  startedAt: string;
  status: RunStatus;
  stage: string;
  budget: Budget;
  progress: number;
  completeNodes: number;
  totalNodes: number;
  candidates: number;
  duplicates: number;
  verified: number;
  currentAction: string;
  summary: string;
  region: string;
  nodes: TreeNode[];
  events: RunEvent[];
}

export interface NewRunInput {
  files: File[];
  title: string;
  metadata: string;
  budget: Budget;
}
