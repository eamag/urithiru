"""What each agent is asked to do, and how its answer is read back. No sandbox knowledge."""

import json
from pathlib import Path

from urithiru.agents.llm import prompt
from urithiru.core.models import Experiment, External, Goal, Literature
from urithiru.runtime.control import Cancelled
from urithiru.runtime.events import emit
from urithiru.runtime.files import read_json


def read_proposals(workspace: Path) -> dict:
    data = read_json(workspace / "eda_proposal.json")
    return {
        "hypotheses": [item["hypothesis"] for item in data["hypotheses"]],
        "schema_summary": data["schema_summary"],
    }


def read_literature(workspace: Path) -> Literature:
    return Literature(**read_json(workspace / "p_search.json"))


def read_experiment(workspace: Path) -> Experiment:
    data = read_json(workspace / "result.json")
    failure = data.pop("error_code", "")
    if failure:
        # Infrastructure failure is never scientific evidence; the stage retries instead.
        raise RuntimeError(f"Agent reported {failure}: {data.get('summary', '')}")
    return Experiment(**data)


def read_external(workspace: Path) -> External:
    return External(**read_json(workspace / "external_result.json"))


RESULT_READERS = {
    "proposal": read_proposals,
    "search": read_literature,
    "code": read_experiment,
    "external": read_external,
}


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

    def literature(self, node) -> Literature:
        """The data-blind belief. This sandbox is never given the dataset files."""
        return self.stage(
            f"search_{node.id}",
            "search",
            {
                "hypothesis": node.claim,
                # Only the descriptive schema, so constructs can be named without seeing values.
                "dataset": self.schema,
                "evidence": "\n".join(node.evidence),
            },
        )

    def experiment(self, node) -> Experiment:
        """The empirical belief, formed by an agent that never learns what the literature said."""
        return self.stage(
            f"code_{node.id}",
            "code",
            {
                "hypothesis": node.claim,
                "dataset": self.dataset_context,
                "evidence": "\n".join(node.evidence),
            },
        )

    def external(self, node, literature: Literature, experiment: Experiment) -> External:
        return self.stage(
            f"external_{node.id}",
            "external",
            {
                "hypothesis": node.claim,
                "dataset": self.dataset_context,
                "p_search": literature.belief.prob_true,
                "p_code": experiment.belief.prob_true,
            },
        )
