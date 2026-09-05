import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

CATEGORY_MAPPING = {
    "definitely false": 0.0,
    "maybe false": 0.25,
    "uncertain": 0.5,
    "maybe true": 0.75,
    "definitely true": 1.0,
}
CATEGORIES = tuple(CATEGORY_MAPPING)
SCORES = np.array(list(CATEGORY_MAPPING.values()))

STAGES = ("proposal", "search", "code", "external")
RESULT_FILES = {
    "proposal": "eda_proposal.json",
    "search": "p_search.json",
    "code": "result.json",
    "external": "external_result.json",
}
DATA_STAGES = ("proposal", "code")


@dataclass(frozen=True)
class Belief:
    counts: Mapping[str, int | float]
    rationale: str
    n_samples: ClassVar[int] = 30
    alpha_0: ClassVar[float] = 0.5
    beta_0: ClassVar[float] = 0.5

    def __post_init__(self):
        if set(self.counts) != set(CATEGORIES):
            raise ValueError("All five belief categories are required")
        if any(value < 0 or not math.isfinite(value) for value in self.counts.values()):
            raise ValueError("Belief counts must be finite and nonnegative")
        if sum(self.counts.values()) <= 0:
            raise ValueError("Belief counts must sum to a positive value")

    @property
    def prob_vector(self) -> np.ndarray:
        values = np.array([self.counts[name] for name in CATEGORIES], dtype=np.float64)
        return values / values.sum()

    @property
    def n_true(self) -> float:
        return float(self.prob_vector @ SCORES) * self.n_samples

    @property
    def prob_true(self) -> float:
        return (self.alpha_0 + self.n_true) / (self.alpha_0 + self.beta_0 + self.n_samples)

    @property
    def category(self) -> str:
        return CATEGORIES[int(np.argmin(np.abs(SCORES - self.prob_true)))]


@dataclass(frozen=True)
class Literature:
    category_counts: dict[str, int]
    rationale: str
    findings: dict[str, Any]

    def __post_init__(self):
        if not isinstance(self.findings, dict):
            raise TypeError("Literature findings must be a structured object")
        Belief(self.category_counts, self.rationale)

    @property
    def belief(self) -> Belief:
        return Belief(self.category_counts, self.rationale)


@dataclass(frozen=True)
class Experiment:
    execution_success: bool
    test_spec_valid: bool
    direction_supported: bool
    empirical_support: bool
    category_counts: dict[str, int]
    rationale: str
    metrics: dict[str, Any]
    p_value: float | None
    p_value_corrected: float | None
    stdout: str
    stderr: str
    summary: str

    def __post_init__(self):
        if not isinstance(self.metrics, dict):
            raise TypeError("Scientific metrics must be a structured object")
        if any(not isinstance(value, str) for value in (self.stdout, self.stderr, self.summary)):
            raise TypeError("Execution output and summary must be strings")
        flags = [self.execution_success, self.test_spec_valid, self.direction_supported]
        if any(type(flag) is not bool for flag in [*flags, self.empirical_support]):
            raise TypeError("Verification outcomes must be Boolean")
        if self.empirical_support and not all(flags):
            raise ValueError("Empirical support requires execution, specification and direction support")
        for value in (self.p_value, self.p_value_corrected):
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid p-value")
        Belief(self.category_counts, self.rationale)

    @property
    def belief(self) -> Belief:
        return Belief(self.category_counts, self.rationale)


@dataclass(frozen=True)
class External:
    source: str
    category_counts: dict[str, int] | None
    rationale: str
    estimated_cost: float
    summary: str

    def __post_init__(self):
        if self.estimated_cost < 0 or not math.isfinite(self.estimated_cost):
            raise ValueError("External cost must be finite and nonnegative")
        if self.category_counts is not None:
            Belief(self.category_counts, self.rationale)

    @property
    def belief(self) -> Belief | None:
        if self.category_counts is None:
            return None
        return Belief(self.category_counts, self.rationale)


@dataclass(frozen=True)
class Surprisal:
    kl_search_param: float
    kl_code_search: float
    kl_code_param: float
    r_ice_norm: float
    belief_change: float
    is_surprising: bool


@dataclass(frozen=True)
class Evaluation:
    prior: Belief
    literature: Literature
    experiment: Experiment
    external: External | None
    external_error: str | None
    surprisal: Surprisal
    reward: float
    external_value: float

    @property
    def search(self) -> Belief:
        return self.literature.belief

    @property
    def code(self) -> Belief:
        return self.experiment.belief

    @property
    def external_belief(self) -> Belief | None:
        return self.external.belief if self.external is not None else None

    @property
    def posterior(self) -> Belief:
        return self.external_belief or self.code

    @property
    def total_reward(self) -> float:
        return self.reward + self.external_value

    @property
    def verdict(self) -> str:
        external = self.external_belief
        if external is None:
            return "no external result"
        return "aligned" if (external.prob_true > 0.5) == (self.code.prob_true > 0.5) else "opposed"

    def summary(self) -> dict:
        external = self.external_belief
        return {
            "p_param": self.prior.prob_true,
            "p_search": self.search.prob_true,
            "p_code": self.code.prob_true,
            "p_external": external.prob_true if external is not None else None,
            "empirical_support": self.experiment.empirical_support,
            "belief_change": self.surprisal.belief_change,
            "verdict": self.verdict,
            "reward": self.total_reward,
            "seed_reward": self.reward,
            "external_value": self.external_value,
            "external_error": self.external_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evaluation":
        return cls(
            Belief(**data["prior"]),
            Literature(**data["literature"]),
            Experiment(**data["experiment"]),
            External(**data["external"]) if data["external"] is not None else None,
            data["external_error"],
            Surprisal(**data["surprisal"]),
            data["reward"],
            data["external_value"],
        )


@dataclass
class CandidateAudit:
    id: str
    claim: str
    generation: int
    duplicate_of: str | None
    similarity: float | None
    prior: float | None
    selected: bool
    selected_step: int | None
    rejection_reason: str | None


@dataclass(frozen=True)
class Dataset:
    files: list[str]
    metadata: str
    hashes: dict[str, str]


@dataclass(frozen=True)
class Goal:
    id: str
    stage: str
    prompt: str
