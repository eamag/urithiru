"""Scientific records from the original engine, with derived values kept as properties."""

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
STAGES = ("proposal", "verification", "external")
RESULT_FILES = {
    "proposal": "eda_proposal.json",
    "verification": "result.json",
    "external": "external_result.json",
}


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
    def category_counts(self) -> dict[str, int]:
        return dict(
            zip(CATEGORIES, (round(value * self.n_samples) for value in self.prob_vector), strict=True)
        )

    @property
    def n_true(self) -> float:
        return float(self.prob_vector @ SCORES) * self.n_samples

    @property
    def mean(self) -> float:
        """The plain category-score expectation, before the Beta-Bernoulli prior."""
        return self.n_true / self.n_samples

    @property
    def alpha(self) -> float:
        return self.alpha_0 + self.n_true

    @property
    def beta(self) -> float:
        return self.beta_0 + self.n_samples - self.n_true

    @property
    def prob_true(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def category(self) -> str:
        return CATEGORIES[int(np.argmin(np.abs(SCORES - self.prob_true)))]


@dataclass
class AgentExecutionResult:
    execution_success: bool
    test_spec_valid: bool
    direction_supported: bool
    empirical_support: bool
    stdout: str
    stderr: str
    summary: str
    p_value: float | None
    p_value_corrected: float | None
    error_code: str
    search_category_counts: dict[str, int]
    search_rationale: str
    code_category_counts: dict[str, int]
    code_rationale: str
    literature_findings: dict[str, Any]
    extracted_metrics: dict[str, Any]

    def validate(self) -> None:
        if not isinstance(self.extracted_metrics, dict) or not isinstance(self.literature_findings, dict):
            raise TypeError("Scientific metrics and literature findings must be structured objects")
        if any(
            not isinstance(value, str) for value in (self.stdout, self.stderr, self.summary, self.error_code)
        ):
            raise TypeError("Execution output, summary and error code must be strings")
        flags = [
            self.execution_success,
            self.test_spec_valid,
            self.direction_supported,
            self.empirical_support,
        ]
        if any(type(flag) is not bool for flag in flags) or self.empirical_support != all(flags[:3]):
            raise ValueError("Empirical support must equal execution AND specification AND direction support")
        for value in (self.p_value, self.p_value_corrected):
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid p-value")
        Belief(self.search_category_counts, self.search_rationale)
        Belief(self.code_category_counts, self.code_rationale)

    @property
    def search(self) -> Belief:
        return Belief(self.search_category_counts, self.search_rationale)

    @property
    def code(self) -> Belief:
        return Belief(self.code_category_counts, self.code_rationale)


@dataclass(frozen=True)
class ExternalVerificationResult:
    source: str
    external_category_counts: dict[str, int] | None
    external_rationale: str
    estimated_cost: float
    summary: str

    def __post_init__(self):
        if self.estimated_cost < 0 or not math.isfinite(self.estimated_cost):
            raise ValueError("External cost must be finite and nonnegative")
        if self.external_category_counts is not None:
            Belief(self.external_category_counts, self.external_rationale)

    @property
    def belief(self) -> Belief | None:
        return (
            Belief(self.external_category_counts, self.external_rationale)
            if self.external_category_counts is not None
            else None
        )


@dataclass(frozen=True)
class SurprisalResult:
    belief_change: float
    kl_divergence: float
    is_surprising: bool
    kl_code_search: float
    kl_search_param: float
    r_ice: float
    log_r_ice: float
    r_ice_norm: float
    fidelity: float
    incompatibility_c_dm: float
    incompatibility_c_ce: float
    incompatibility_c_credal: float
    efe: float


@dataclass(frozen=True)
class Evaluation:
    prior: Belief
    verification: AgentExecutionResult
    surprisal: SurprisalResult
    external: ExternalVerificationResult | None
    external_error: str | None
    reward: float
    external_value: float

    @property
    def posterior(self) -> Belief:
        external = self.external.belief if self.external is not None else None
        return external if external is not None else self.verification.code

    @property
    def external_belief(self) -> Belief | None:
        return self.external.belief if self.external is not None else None

    def summary(self) -> dict:
        """The single description of an evaluation shared by the live log and the report."""
        external = self.external_belief
        return {
            "p_param": self.prior.prob_true,
            "p_search": self.verification.search.prob_true,
            "p_code": self.verification.code.prob_true,
            "p_external": external.prob_true if external is not None else None,
            "empirical_support": self.verification.empirical_support,
            "reward": self.reward + self.external_value,
            "seed_reward": self.reward,
            "external_value": self.external_value,
            "external_error": self.external_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evaluation":
        verification = AgentExecutionResult(**data["verification"])
        verification.validate()
        return cls(
            Belief(**data["prior"]),
            verification,
            SurprisalResult(**data["surprisal"]),
            ExternalVerificationResult(**data["external"]) if data["external"] is not None else None,
            data["external_error"],
            data["reward"],
            data["external_value"],
        )


@dataclass
class CandidateAudit:
    id: str
    claim: str
    generation: int
    created_at_node_count: int
    exact_duplicate: bool
    exact_duplicate_of: str | None
    semantic_duplicate: bool | None
    semantic_duplicate_of: str | None
    prior_mean: float | None
    similarity: float | None
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
