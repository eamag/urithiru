"""The original proposal, verification and external goals, independent of their sandbox."""

import json
from pathlib import Path

from urithiru.agents.llm import prompt
from urithiru.core.models import AgentExecutionResult, ExternalVerificationResult, Goal
from urithiru.runtime.checkpoints import read_json
from urithiru.runtime.control import Cancelled
from urithiru.runtime.events import emit

SEARCH_FIELDS = ("search_category_counts", "search_rationale", "literature_findings")


def read_proposals(workspace: Path) -> dict:
    data = read_json(workspace / "eda_proposal.json")
    return {
        "hypotheses": [item["hypothesis"] for item in data["hypotheses"]],
        "schema_summary": data["schema_summary"],
    }


def check_phase_order(workspace: Path) -> None:
    """The agent enforces Phase A by prompt; the harness checks the artifacts afterwards.

    `p_search.json` is the data-blind literature assessment. It must exist, and it must
    have been written before any script that could have touched the seed data.
    """
    frozen = workspace / "p_search.json"
    if not frozen.exists():
        raise RuntimeError("No p_search.json: the data-blind literature assessment was never frozen")
    scripts = [path.stat().st_mtime for path in workspace.rglob("*.py")]
    if scripts and min(scripts) < frozen.stat().st_mtime:
        raise RuntimeError("Analysis code predates p_search.json: Phase A was not data-blind")


def read_verification(workspace: Path) -> AgentExecutionResult:
    check_phase_order(workspace)
    data = read_json(workspace / "result.json")
    search = read_json(workspace / "p_search.json")
    data.update({key: search[key] for key in SEARCH_FIELDS})
    result = AgentExecutionResult(**data)
    if result.error_code:
        # Infrastructure failure is never scientific evidence; the stage retries instead.
        raise RuntimeError(f"Agent reported {result.error_code}: {result.summary}")
    result.validate()
    return result


def read_external(workspace: Path) -> ExternalVerificationResult:
    return ExternalVerificationResult(**read_json(workspace / "external_result.json"))


RESULT_READERS = {"proposal": read_proposals, "verification": read_verification, "external": read_external}


class ResearchAgent:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.config, self.dataset = sandbox.config, sandbox.dataset
        self.budget = sandbox.config.budget
        self.directory, self.stop = sandbox.directory, sandbox.stop
        self.schema = self.dataset.metadata

    @property
    def dataset_context(self) -> str:
        return (
            f"Data files (relative to working directory): {json.dumps(self.dataset.files)}\n"
            f"User metadata:\n{self.dataset.metadata}\nSchema description:\n{self.schema}"
        )

    def stage(self, identifier: str, name: str, values: dict):
        """Build the goal, run it, and read its result, retrying a transient agent failure."""
        goal = Goal(identifier, name, prompt(name, {"seconds": self.budget.seconds(name), **values}))
        for attempt in range(1, self.budget.stage_attempts + 1):
            emit("stage_started", stage=name, goal=goal.id, attempt=attempt)
            try:
                result = RESULT_READERS[name](self.sandbox.run(goal))
                self.sandbox.complete(goal)
                emit("stage_completed", stage=name, goal=goal.id, attempt=attempt)
                return result
            except (Cancelled, KeyboardInterrupt, TimeoutError):
                raise
            except Exception as error:
                emit(
                    "stage_failed",
                    severity="ERROR",
                    stage=name,
                    goal=goal.id,
                    attempt=attempt,
                    remaining=self.budget.stage_attempts - attempt,
                    error=f"{type(error).__name__}: {error}",
                )
                if attempt == self.budget.stage_attempts:
                    raise
        raise RuntimeError(f"Stage {name} exhausted {self.budget.stage_attempts} attempts")

    def propose(self, node, evidence: list[str]) -> list[str]:
        result = self.stage(
            f"proposal_{node.id}_{node.generation:06d}",
            "proposal",
            {
                "dataset": self.dataset_context,
                "ancestors": "\n".join(node.ancestors),
                "attempted": "\n".join(item.claim for item in node.candidates),
                "evidence": "\n".join(evidence),
                "n_candidates": self.config.search.branching_factor,
            },
        )
        if result["hypotheses"]:
            self.schema = result["schema_summary"]
        return result["hypotheses"]

    def verify(self, node) -> AgentExecutionResult:
        return self.stage(
            f"verification_{node.id}",
            "verification",
            {
                "dataset": self.dataset_context,
                "hypothesis": node.claim,
                "evidence": "\n".join(node.evidence),
            },
        )

    def external(self, node, verification) -> ExternalVerificationResult:
        return self.stage(
            f"external_{node.id}",
            "external",
            {
                "dataset": self.dataset_context,
                "hypothesis": node.claim,
                "p_search": verification.search.prob_true,
                "p_code": verification.code.prob_true,
            },
        )
