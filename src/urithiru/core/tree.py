"""Stateful MCTS tree: the original selection formula and progressive widening."""

import math

from urithiru.core.models import Belief, CandidateAudit, Evaluation


class Node:
    """`STATE` is the on-disk checkpoint format: every field here must survive a resume."""

    STATE = ("queue", "tried", "visits", "value", "terminal", "evidence", "generation")

    def __init__(self, identifier: str, parent: "Node | None", claim: str):
        self.id, self.parent, self.claim = identifier, parent, claim
        self.children: list[Node] = []
        self.candidates: list[CandidateAudit] = []
        self.queue: list[str] = []
        self.tried: list[str] = []
        self.visits, self.value = 0, 0.0
        self.terminal = False
        self.prior: Belief | None = None
        self.evaluation: Evaluation | None = None
        self.evidence: list[str] = []
        self.generation = 0

    @property
    def ancestors(self) -> list[str]:
        node, claims = self, []
        while node.parent is not None:
            claims.append(node.claim)
            node = node.parent
        return list(reversed(claims))

    def uct(self, exploration: float) -> float:
        if self.visits == 0:
            return math.inf
        visits = self.parent.visits if self.parent is not None and self.parent.visits else self.visits
        return self.value / self.visits + exploration * math.sqrt(math.log(visits + 1) / self.visits)

    def can_widen(self) -> bool:
        if not self.queue and not self.tried:
            return False
        return not self.children or len(self.children) < math.ceil(1.5 * self.visits**0.5)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_id": self.parent.id if self.parent is not None else None,
            "claim": self.claim,
            "candidates": self.candidates,
            "prior": self.prior,
            "evaluation": self.evaluation,
            **{name: getattr(self, name) for name in self.STATE},
        }

    @classmethod
    def from_dict(cls, data: dict, parent: "Node | None") -> "Node":
        node = cls(data["id"], parent, data["claim"])
        for name in cls.STATE:
            setattr(node, name, data[name])
        node.candidates = [CandidateAudit(**item) for item in data["candidates"]]
        node.prior = Belief(**data["prior"]) if data["prior"] is not None else None
        node.evaluation = Evaluation.from_dict(data["evaluation"]) if data["evaluation"] is not None else None
        return node


class MCTSTree:
    def __init__(self, exploration: float):
        self.exploration = exploration
        self.root = Node("root", None, "")
        self.nodes = {self.root.id: self.root}

    def select(self) -> Node:
        node = self.root
        while node.children and not node.can_widen():
            children = [child for child in node.children if not child.terminal]
            if not children:
                break
            node = max(children, key=lambda child: child.uct(self.exploration))
        return node

    def add(self, parent: Node, claim: str) -> Node:
        node = Node(f"node_{len(self.nodes):06d}", parent, claim)
        parent.children.append(node)
        self.nodes[node.id] = node
        return node

    def backpropagate(self, node: Node) -> None:
        if node.evaluation is None:
            raise ValueError("Cannot update the tree without a completed evaluation")
        reward = node.evaluation.total_reward
        current: Node | None = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent

    def restore(self, records: list[dict]) -> None:
        self.nodes = {}
        for record in records:
            parent = self.nodes[record["parent_id"]] if record["parent_id"] is not None else None
            node = Node.from_dict(record, parent)
            self.nodes[node.id] = node
            if parent is not None:
                parent.children.append(node)
        self.root = self.nodes["root"]
