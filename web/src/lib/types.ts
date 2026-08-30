// These mirror the files `urithiru publish` copies, field for field. The page renders the
// orchestrator's own checkpoint and event log; nothing reshapes them on the way here.

export const CATEGORIES = [
  "definitely false",
  "maybe false",
  "uncertain",
  "maybe true",
  "definitely true",
] as const;

export type View = "runs" | "launch" | "run";

export type Counts = Record<string, number>;

export interface Belief {
  counts: Counts;
  rationale: string;
}

export interface Literature {
  category_counts: Counts;
  rationale: string;
  findings: Record<string, unknown>;
}

export interface Experiment {
  execution_success: boolean;
  test_spec_valid: boolean;
  direction_supported: boolean;
  empirical_support: boolean;
  category_counts: Counts;
  rationale: string;
  metrics: Record<string, unknown>;
  p_value: number | null;
  p_value_corrected: number | null;
  stdout: string;
  stderr: string;
  summary: string;
}

export interface External {
  source: string;
  category_counts: Counts | null;
  rationale: string;
  estimated_cost: number;
  summary: string;
}

export interface Surprisal {
  kl_search_param: number;
  kl_code_search: number;
  kl_code_param: number;
  r_ice_norm: number;
  belief_change: number;
  is_surprising: boolean;
}

export interface Evaluation {
  prior: Belief;
  literature: Literature;
  experiment: Experiment;
  external: External | null;
  external_error: string | null;
  surprisal: Surprisal;
  reward: number;
  external_value: number;
}

export interface CheckpointNode {
  id: string;
  parent_id: string | null;
  claim: string;
  visits: number;
  value: number;
  terminal: boolean;
  candidates: { claim: string; duplicate_of: string | null; rejection_reason: string | null }[];
  evaluation: Evaluation | null;
}

export interface Checkpoint {
  steps: number;
  seed: number;
  status: string;
  error: string | null;
  nodes: CheckpointNode[];
  completed: string[];
  pending: string[];
  updated_at: string;
}

export interface RunConfig {
  dataset: { files: string[]; metadata: string };
  steps: number;
  seed: number;
  models: Record<string, string>;
  budget: Record<string, number>;
}

export interface RunEvent {
  time: string;
  event: string;
  severity: string;
  message: string;
  stage?: string;
  goal?: string;
  node?: string;
}

export interface IndexEntry {
  id: string;
  title?: string;
  status: string;
  published_at?: string;
  updated_at: string;
  dataset: string[];
  completed?: number;
  requested?: number;
  error?: string | null;
}

export interface Run {
  entry: IndexEntry;
  config: RunConfig | null;
  checkpoint: Checkpoint | null;
  events: RunEvent[];
}

/** Per-stage minute overrides. An absent key keeps the operator profile's value. */
export interface StageMinutes {
  proposal?: number;
  search?: number;
  code?: number;
  external?: number;
}

export interface LaunchInput {
  data: File[];
  metadataFiles: File[];
  title: string;
  metadata: string;
  steps: number;
  seed: number;
  minutes: StageMinutes;
  /** Sent as a bearer token; empty reuses whatever this tab already holds. */
  token: string;
}

/** What the deployment serving this page permits. A read-only host enables nothing. */
export interface Capabilities {
  launchEnabled: boolean;
}

export interface LaunchResult {
  id: string;
  execution?: string;
}
