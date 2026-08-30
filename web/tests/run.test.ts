import { describe, expect, it } from "bun:test";
import {
  activeStages,
  belief,
  chain,
  groupByDataset,
  probTrue,
  ranked,
  runName,
  running,
  shortName,
  verdict,
} from "../src/lib/run";
import type { Checkpoint, CheckpointNode, Counts, Evaluation, IndexEntry, RunEvent } from "../src/lib/types";

function makeCounts(d_false = 0, m_false = 0, uncert = 0, m_true = 0, d_true = 0): Counts {
  return {
    "definitely false": d_false,
    "maybe false": m_false,
    uncertain: uncert,
    "maybe true": m_true,
    "definitely true": d_true,
  };
}

describe("probTrue and belief calculations", () => {
  it("computes Beta(0.5, 0.5) 30-vote posterior matching Python engine", () => {
    // All 30 on definitely true -> prob_true = 30.5 / 31
    const pTrue = probTrue(makeCounts(0, 0, 0, 0, 30));
    expect(pTrue).not.toBeNull();
    expect(pTrue).toBeCloseTo(30.5 / 31, 6);

    // All 30 on definitely false -> prob_true = 0.5 / 31
    const pFalse = probTrue(makeCounts(30, 0, 0, 0, 0));
    expect(pFalse).not.toBeNull();
    expect(pFalse).toBeCloseTo(0.5 / 31, 6);

    // Uniform 6 across all categories -> prob_true = 0.5
    const pUniform = probTrue(makeCounts(6, 6, 6, 6, 6));
    expect(pUniform).not.toBeNull();
    expect(pUniform).toBeCloseTo(0.5, 6);
  });

  it("handles null and empty counts gracefully", () => {
    expect(probTrue(null)).toBeNull();
    expect(probTrue(undefined)).toBeNull();
    expect(probTrue(makeCounts(0, 0, 0, 0, 0))).toBeNull();
  });

  it("extracts belief from either counts or category_counts", () => {
    const beliefObj = { counts: makeCounts(0, 0, 0, 0, 30), rationale: "ok" };
    expect(belief(beliefObj)).toBeCloseTo(30.5 / 31, 6);

    const litObj = { category_counts: makeCounts(30, 0, 0, 0, 0), rationale: "ok", findings: {} };
    expect(belief(litObj)).toBeCloseTo(0.5 / 31, 6);

    expect(belief(null)).toBeNull();
  });
});

describe("evaluation verdicts and stage chains", () => {
  const dummyPrior = { counts: makeCounts(6, 6, 6, 6, 6), rationale: "" };
  const dummyLit = { category_counts: makeCounts(0, 0, 30, 0, 0), rationale: "", findings: {} };
  const dummyExpSupported = {
    execution_success: true,
    test_spec_valid: true,
    direction_supported: true,
    empirical_support: true,
    category_counts: makeCounts(0, 0, 0, 0, 30),
    rationale: "",
    metrics: {},
    p_value: 0.01,
    p_value_corrected: 0.01,
    stdout: "",
    stderr: "",
    summary: "",
  };

  it("assigns correct verdict strings", () => {
    // No external data
    const evNoExt: Evaluation = {
      prior: dummyPrior,
      literature: dummyLit,
      experiment: dummyExpSupported,
      external: null,
      external_error: null,
      surprisal: {
        kl_search_param: 0,
        kl_code_search: 0.8,
        kl_code_param: 0.8,
        r_ice_norm: 0.5,
        belief_change: 0.4,
        is_surprising: false,
      },
      reward: 0.7,
      external_value: 0,
    };
    expect(verdict(evNoExt)).toBe("no independent data");

    // Replicated
    const evReplicated: Evaluation = {
      ...evNoExt,
      external: {
        source: "openalex",
        category_counts: makeCounts(0, 0, 0, 0, 30),
        rationale: "",
        estimated_cost: 0.1,
        summary: "",
      },
    };
    expect(verdict(evReplicated)).toBe("replicated");

    // Contradicted
    const evContradicted: Evaluation = {
      ...evNoExt,
      external: {
        source: "openalex",
        category_counts: makeCounts(30, 0, 0, 0, 0),
        rationale: "",
        estimated_cost: 0.1,
        summary: "",
      },
    };
    expect(verdict(evContradicted)).toBe("contradicted");
  });

  it("extracts 4-stage belief chain in order", () => {
    const ev: Evaluation = {
      prior: dummyPrior,
      literature: dummyLit,
      experiment: dummyExpSupported,
      external: null,
      external_error: null,
      surprisal: {
        kl_search_param: 0,
        kl_code_search: 0,
        kl_code_param: 0,
        r_ice_norm: 0,
        belief_change: 0,
        is_surprising: false,
      },
      reward: 0.5,
      external_value: 0,
    };
    const c = chain(ev);
    expect(c).toHaveLength(4);
    expect(c[0].stage).toBe("prior");
    expect(c[1].stage).toBe("literature");
    expect(c[2].stage).toBe("experiment");
    expect(c[3].stage).toBe("external");
    expect(c[3].value).toBeNull();
  });
});

describe("display formatting helpers", () => {
  it("formats shortName by stripping numeric prefixes", () => {
    expect(shortName("inputs/000_measurements.csv")).toBe("measurements.csv");
    expect(shortName("001_002_data.parquet")).toBe("data.parquet");
    expect(shortName("plain.csv")).toBe("plain.csv");
  });

  it("formats runName with title fallback and truncation", () => {
    const entryWithTitle: IndexEntry = {
      id: "abc123456789",
      status: "completed",
      published_at: "",
      updated_at: "",
      dataset: ["inputs/000_a.csv"],
      title: "NHANES Blood Pressure Study",
    };
    expect(runName(entryWithTitle)).toBe("NHANES Blood Pressure Study");

    const entryWithoutTitle: IndexEntry = {
      id: "abc123456789",
      status: "completed",
      published_at: "",
      updated_at: "",
      dataset: ["inputs/000_a.csv", "inputs/001_b.csv", "inputs/002_c.csv"],
    };
    expect(runName(entryWithoutTitle)).toBe("a.csv + b.csv + 1 more");

    const emptyEntry: IndexEntry = {
      id: "abc123456789",
      status: "completed",
      published_at: "",
      updated_at: "",
      dataset: [],
    };
    expect(runName(emptyEntry)).toBe("Run abc12345");
  });

  it("groups runs by dataset and computes common prefix title", () => {
    const e1: IndexEntry = {
      id: "r1",
      status: "completed",
      published_at: "",
      updated_at: "",
      dataset: ["000_data.csv"],
      title: "NHANES Study: Baseline",
    };
    const e2: IndexEntry = {
      id: "r2",
      status: "completed",
      published_at: "",
      updated_at: "",
      dataset: ["000_data.csv"],
      title: "NHANES Study: Followup",
    };
    const groups = groupByDataset([e1, e2]);
    expect(groups).toHaveLength(1);
    expect(groups[0].name).toBe("NHANES Study");
    expect(groups[0].entries).toHaveLength(2);
  });

  it("computes running status correctly", () => {
    expect(running("running")).toBe(true);
    expect(running("pending")).toBe(true);
    expect(running("completed")).toBe(false);
    expect(running("exhausted")).toBe(false);
    expect(running("failed")).toBe(false);
    expect(running("cancelled")).toBe(false);
  });

  it("ranks nodes by evaluation reward descending", () => {
    const node1: CheckpointNode = {
      id: "n1",
      parent_id: "root",
      claim: "Claim 1",
      candidates: [],
      evaluation: { reward: 0.3 } as any,
      visits: 1,
      value: 0.3,
      terminal: false,
    };
    const node2: CheckpointNode = {
      id: "n2",
      parent_id: "root",
      claim: "Claim 2",
      candidates: [],
      evaluation: { reward: 0.9 } as any,
      visits: 1,
      value: 0.9,
      terminal: false,
    };
    const checkpoint: Checkpoint = {
      steps: 2,
      seed: 42,
      status: "completed",
      error: null,
      nodes: [node1, node2],
      completed: ["n1", "n2"],
      pending: [],
      updated_at: "",
    };

    const sorted = ranked(checkpoint);
    expect(sorted[0].id).toBe("n2");
    expect(sorted[1].id).toBe("n1");
  });

  it("tracks active stages off event stream", () => {
    const events: RunEvent[] = [
      { severity: "INFO", time: "", event: "stage_started", stage: "proposal", message: "" },
      { severity: "INFO", time: "", event: "stage_completed", stage: "proposal", message: "" },
      { severity: "INFO", time: "", event: "stage_started", stage: "search", message: "" },
      { severity: "INFO", time: "", event: "stage_started", stage: "code", message: "" },
      { severity: "INFO", time: "", event: "stage_completed", stage: "search", message: "" },
    ];
    const active = activeStages(events);
    expect(active).toEqual(["code"]);
  });
});
