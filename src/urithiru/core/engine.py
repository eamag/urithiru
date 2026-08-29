"""Original discovery loop decomposed into short methods over shared run state."""

import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime

import numpy as np

from urithiru.core.beliefs import BeliefAnalysis
from urithiru.core.deduplication import CandidateSelector, canonicalize
from urithiru.core.models import CandidateAudit, Evaluation
from urithiru.core.tree import MCTSTree, Node
from urithiru.runtime.checkpoints import read_json, write_json
from urithiru.runtime.control import Cancelled
from urithiru.runtime.events import emit


class UrithiruEngine:
    def __init__(self, config, agent, model, steps: int, seed: int):
        if steps <= 0:
            raise ValueError("A run needs at least one evaluation step")
        self.config, self.agent, self.model = config.search, agent, model
        self.steps, self.seed = steps, seed
        self.rng = random.Random(seed)
        self.status, self.error = "pending", None
        self.directory = agent.directory
        self.selector = CandidateSelector(model, self.directory, self.config.top_k)
        self.tree = MCTSTree(self.config.uct_c)
        self.completed: list[Node] = []
        self.pending: list[Node] = []
        self.generation = 0

    def run(self) -> list[Node]:
        self.load_checkpoint()
        self.status, self.error = "running", None
        emit("run_started", steps=self.steps, seed=self.seed, completed=len(self.completed))
        try:
            while len(self.completed) < self.steps and not self.tree.root.terminal:
                self.check_cancelled()
                if not self.pending:
                    self.prepare_batch()
                if self.pending:
                    self.evaluate_batch()
            # The tree can run out of novel hypotheses before the requested budget is spent.
            self.status = "completed" if len(self.completed) >= self.steps else "exhausted"
            emit("run_finished", status=self.status, completed=len(self.completed), requested=self.steps)
            return self.completed
        except BaseException as error:
            self.status = "cancelled" if isinstance(error, Cancelled | KeyboardInterrupt) else "failed"
            self.error = f"{type(error).__name__}: {error}"
            emit(
                "run_finished",
                severity="WARNING" if self.status == "cancelled" else "ERROR",
                status=self.status,
                completed=len(self.completed),
                requested=self.steps,
                error=self.error,
            )
            raise
        finally:
            self.save_checkpoint()

    def check_cancelled(self) -> None:
        if self.agent.stop.is_set() or (self.directory / "cancel").exists():
            raise Cancelled("Run cancelled; checkpoint and completed work are preserved")

    def prepare_batch(self) -> None:
        leaf = self.tree.select()
        size = min(self.config.parallelism, self.steps - len(self.completed))
        while len(self.pending) < size and (not self.pending or leaf.queue):
            candidate = self.acquire_candidate(leaf)
            if candidate is None:
                break
            node = self.tree.add(leaf, candidate.claim)
            prior = self.model.prior(candidate.claim)
            node.prior = prior
            node.evidence = self.evidence(candidate.claim)
            leaf.queue.remove(candidate.id)
            leaf.tried.append(candidate.claim)
            self.pending.append(node)
            candidate.prior_mean = prior.mean
            candidate.selected_step = len(self.completed) + len(self.pending)
            emit("hypothesis_selected", node=node.id, hypothesis=node.claim, p_param=prior.prob_true)
            self.save_checkpoint()

    def acquire_candidate(self, leaf: Node) -> CandidateAudit | None:
        attempts = 0
        while attempts < 2:
            self.check_cancelled()
            if not leaf.queue:
                self.propose(leaf)
                attempts += 1
                if leaf.terminal:
                    return None
            candidates = self.deduplicate(leaf)
            if candidates:
                return self.select_candidate(candidates)
        leaf.terminal = True
        self.save_checkpoint()
        return None

    def propose(self, leaf: Node) -> None:
        leaf.generation = self.generation + 1
        claims = self.agent.propose(leaf, self.evidence(leaf.claim))
        if not claims:
            leaf.terminal = True
            leaf.queue = []
        else:
            self.generation += 1
            for index, claim in enumerate(claims):
                candidate = self.new_candidate(leaf, claim, index)
                leaf.candidates.append(candidate)
                leaf.queue.append(candidate.id)
        emit("proposals_ready", node=leaf.id, proposed=len(claims), terminal=leaf.terminal)
        self.save_checkpoint()

    def new_candidate(self, leaf: Node, claim: str, index: int) -> CandidateAudit:
        return CandidateAudit(
            id=f"{leaf.id}_generation_{self.generation:06d}_candidate_{index:03d}",
            claim=canonicalize(claim),
            generation=self.generation,
            created_at_node_count=len(self.completed),
            exact_duplicate=False,
            exact_duplicate_of=None,
            semantic_duplicate=None,
            semantic_duplicate_of=None,
            prior_mean=None,
            similarity=None,
            selected=False,
            selected_step=None,
            rejection_reason=None,
        )

    def deduplicate(self, leaf: Node) -> list[CandidateAudit]:
        registry = {candidate.id: candidate for candidate in leaf.candidates}
        candidates = [registry[key] for key in leaf.queue]
        surviving, exact, semantic = self.selector.deduplicate(
            [candidate.claim for candidate in candidates], [node.claim for node in self.completed]
        )
        for index, duplicate in exact.items():
            item = candidates[index]
            item.exact_duplicate, item.exact_duplicate_of = True, duplicate
            item.rejection_reason = "exact_duplicate"
        for index, duplicate in semantic.items():
            item = candidates[index]
            item.semantic_duplicate, item.semantic_duplicate_of = True, duplicate
            item.rejection_reason = "semantic_duplicate"
        result = [candidates[index] for index in surviving]
        for item in result:
            item.semantic_duplicate = False
        leaf.queue = [item.id for item in result]
        emit("deduplicated", node=leaf.id, surviving=len(result), exact=len(exact), semantic=len(semantic))
        return result

    def select_candidate(self, candidates: list[CandidateAudit]) -> CandidateAudit:
        scores = (
            self.selector.diversity(
                [item.claim for item in candidates], [node.claim for node in self.completed]
            )
            if self.completed
            else [0.0] * len(candidates)
        )
        position = int(np.argmin(scores)) if self.completed else self.rng.randrange(len(candidates))
        for index, candidate in enumerate(candidates):
            candidate.similarity, candidate.selected = scores[index], index == position
            candidate.rejection_reason = None if candidate.selected else "not_minimum_local_similarity"
        return candidates[position]

    def evidence(self, claim: str) -> list[str]:
        nodes = [node for node in self.completed if not node.terminal]
        return [self.format_evidence(node) for node in self.selector.retrieve(claim, nodes)]

    def format_evidence(self, node: Node) -> str:
        result = node.evaluation
        if result is None:
            raise ValueError("Evaluated node has no evidence")
        findings = json.dumps(result.verification.extracted_metrics, sort_keys=True)
        return (
            f"Hypothesis: {node.claim} (Belief after experiment: {result.posterior.category}) "
            f"| Evidence Details: Findings: {findings}"
        )

    def evaluate_batch(self) -> None:
        batch, failures = list(self.pending), {}
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {pool.submit(self.evaluate, node): node for node in batch}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as error:
                    failures[futures[future].id] = error
        # Commit every sibling that did succeed before surfacing the failure, so a resume keeps them.
        for node in batch:
            if node.id in failures:
                continue
            self.tree.backpropagate(node)
            self.completed.append(node)
            self.pending.remove(node)
            self.save_checkpoint()
            self.report(node)
        if failures:
            raise next(iter(failures.values()))
        self.check_cancelled()

    def evaluate(self, node: Node) -> None:
        if node.evaluation is not None:
            return
        path = self.directory / "evaluations" / f"{node.id}.json"
        if path.exists():
            node.evaluation = Evaluation.from_dict(read_json(path))
            return
        self.check_cancelled()
        verification = self.agent.verify(node)
        if node.prior is None:
            raise ValueError("Selected node has no parametric prior")
        beliefs = BeliefAnalysis(node.prior, verification.search, verification.code)
        external, error = (
            self.external(node, verification)
            if (beliefs.reward >= self.config.external_minimum_surprise)
            else (None, None)
        )
        result = Evaluation(
            node.prior,
            verification,
            beliefs.evaluate(self.config.surprisal_threshold),
            external,
            error,
            beliefs.reward,
            beliefs.external_value(external, self.config) if external is not None else 0.0,
        )
        write_json(path, result)
        node.evaluation = result

    def external(self, node: Node, verification):
        try:
            return self.agent.external(node, verification), None
        except Exception as error:
            self.check_cancelled()
            emit(
                "external_skipped", severity="WARNING", node=node.id, error=f"{type(error).__name__}: {error}"
            )
            return None, f"{type(error).__name__}: {error}"

    def load_checkpoint(self) -> None:
        path = self.directory / "mcts_state.json"
        if not path.exists():
            return
        data = read_json(path)
        if data["steps"] != self.steps or data["seed"] != self.seed:
            raise ValueError("Run budget/seed differ from the checkpoint")
        self.tree.restore(data["nodes"])
        self.completed = [self.tree.nodes[key] for key in data["completed"]]
        self.pending = [self.tree.nodes[key] for key in data["pending"]]
        self.rng.setstate((3, tuple(data["rng_state"]), None))
        self.generation, self.agent.schema = data["generation"], data["schema_summary"]
        if self.tree.root.visits != len(self.completed):
            raise ValueError("Checkpoint root visits differ from completed evaluations")

    def save_checkpoint(self) -> None:
        write_json(
            self.directory / "mcts_state.json",
            {
                "steps": self.steps,
                "seed": self.seed,
                "status": self.status,
                "error": self.error,
                "nodes": [node.to_dict() for node in self.tree.nodes.values()],
                "completed": [node.id for node in self.completed],
                "pending": [node.id for node in self.pending],
                "rng_state": list(self.rng.getstate()[1]),
                "generation": self.generation,
                "schema_summary": self.agent.schema,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        write_json(
            self.directory / "candidate_audits.json",
            [
                asdict(candidate) | {"parent_id": node.id}
                for node in self.tree.nodes.values()
                for candidate in node.candidates
            ],
        )
        self.agent.sandbox.checkpoint()

    def report(self, node: Node) -> None:
        result = node.evaluation
        if result is None:
            raise ValueError("Completed node has no result")
        emit(
            "hypothesis_evaluated",
            node=node.id,
            completed=len(self.completed),
            requested=self.steps,
            hypothesis=node.claim,
            **result.summary(),
            diagnostics=asdict(result.surprisal),
        )
