#!/usr/bin/env python3
"""Audit an Urithiru discovery run: health, progress, anomalies, and ranked findings."""

import argparse
import json
import sys
from pathlib import Path


def audit_run(run_path: Path) -> dict:
    state_file = run_path / "mcts_state.json"
    if not state_file.exists():
        return {"error": f"No mcts_state.json found in {run_path}"}

    state = json.loads(state_file.read_text(encoding="utf-8"))
    events_file = run_path / "events.jsonl"
    events = []
    if events_file.exists():
        lines = events_file.read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines if line.strip()]

    completed_ids = state.get("completed", [])
    nodes = {n["id"]: n for n in state.get("nodes", [])}

    findings = []
    for nid in completed_ids:
        node = nodes.get(nid)
        if not node:
            continue
        ev = node.get("evaluation")
        if not ev:
            continue
        exp = ev.get("experiment", {})
        ext = ev.get("external")
        findings.append(
            {
                "id": nid,
                "claim": node.get("claim"),
                "empirical_support": exp.get("empirical_support"),
                "direction_supported": exp.get("direction_supported"),
                "test_spec_valid": exp.get("test_spec_valid"),
                "execution_success": exp.get("execution_success"),
                "p_value": exp.get("p_value"),
                "p_value_corrected": exp.get("p_value_corrected"),
                "reward": (ev.get("reward") or 0.0) + (ev.get("external_value") or 0.0),
                "seed_reward": ev.get("reward"),
                "external_value": ev.get("external_value"),
                "external_source": ext.get("source") if ext else None,
                "summary": exp.get("summary"),
            }
        )

    findings.sort(key=lambda x: -x["reward"])

    # Look for warnings / errors in events
    warnings = [e for e in events if e.get("severity") in ("WARNING", "ERROR")]

    return {
        "status": state.get("status"),
        "steps_requested": state.get("steps"),
        "steps_completed": len(completed_ids),
        "total_nodes": len(nodes),
        "warnings_and_errors": warnings[-10:],
        "top_findings": findings[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Audit an Urithiru discovery run directory.")
    parser.add_argument("run_directory", type=Path, help="Path to run directory or exported run")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = audit_run(args.run_directory)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Urithiru Run Audit: {args.run_directory.name} ===")
    status_line = (
        f"Status: {result['status']} | "
        f"Completed: {result['steps_completed']} of {result['steps_requested']} hypotheses"
    )
    print(status_line)
    print(f"Total MCTS Nodes: {result['total_nodes']}\n")

    if result["top_findings"]:
        print("--- Top Evaluated Hypotheses (Ranked by Reward) ---")
        for idx, f in enumerate(result["top_findings"], 1):
            sup = "✓ Supported" if f["empirical_support"] else "✗ Refuted"
            ext = f" | Ext: {f['external_source']}" if f["external_source"] else ""
            print(f"\n{idx}. [{sup}] Reward: {f['reward']:.4f}{ext}")
            print(f"   Claim: {f['claim']}")
            print(f"   Summary: {f['summary']}")
    else:
        print("No completed evaluations yet.")

    if result["warnings_and_errors"]:
        print("\n--- Recent Warnings / Errors ---")
        for w in result["warnings_and_errors"]:
            print(f"- [{w.get('severity')}] {w.get('event')}: {w.get('message')}")


if __name__ == "__main__":
    main()
