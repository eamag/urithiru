import shutil
from dataclasses import asdict
from pathlib import Path

from urithiru.core.models import Evaluation
from urithiru.runtime.files import read_json, write_json


def format_probability(value: float | None) -> str:
    return "none" if value is None else f"{value:.4f}"


def findings(directory: Path) -> list[dict]:
    checkpoint = read_json(directory / "mcts_state.json")
    nodes = {node["id"]: node for node in checkpoint["nodes"]}
    rows = []
    for identifier in checkpoint["completed"]:
        node = nodes[identifier]
        result = Evaluation.from_dict(node["evaluation"])
        rows.append(
            {
                "id": identifier,
                "hypothesis": node["claim"],
                **result.summary(),
                "literature": asdict(result.literature),
                "experiment": asdict(result.experiment),
                "diagnostics": asdict(result.surprisal),
                "external": asdict(result.external) if result.external is not None else None,
            }
        )
    return sorted(rows, key=lambda row: (-row["reward"], row["id"]))


def export(directory: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError("Choose a new export directory; existing files are never overwritten")
    shutil.copytree(directory, destination, ignore=shutil.ignore_patterns(".run.lock", "*.tmp"))
    rows = findings(directory)
    write_json(destination / "report.json", rows)
    lines = [
        "# Urithiru exploration report",
        "",
        "Beliefs are elicited model assessments, not calibrated confidence.",
        "Metrics, validity flags and external-source provenance are agent-reported and require review.",
        "",
    ]
    for position, row in enumerate(rows, 1):
        lines += [
            f"## {position}. {row['hypothesis']}",
            "",
            f"Agent-reported empirical support: {row['empirical_support']}; "
            f"external result: {row['verdict']}; "
            f"seed reward: {row['seed_reward']:.4f}; external value: {row['external_value']:.4f}.",
            "",
            f"P_param={row['p_param']:.4f} -> P_search={row['p_search']:.4f} -> "
            f"P_code={row['p_code']:.4f} -> P_external={format_probability(row['p_external'])}.",
            "",
            row["experiment"]["summary"],
            "",
            f"Evidence: [evaluations/{row['id']}.json](evaluations/{row['id']}.json)",
            "",
        ]
    (destination / "report.md").write_text("\n".join(lines))
