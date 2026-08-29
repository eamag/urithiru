"""Complete active belief analysis; selection reward remains separate from diagnostics."""

import math

import numpy as np
from scipy.special import gammaln
from scipy.stats import entropy

from urithiru.core.models import CATEGORIES, Belief, SurprisalResult


def categorical_kl(posterior: Belief, prior: Belief) -> float:
    p, q = np.clip(posterior.prob_vector, 1e-9, 1), np.clip(prior.prob_vector, 1e-9, 1)
    return float(entropy(p / p.sum(), q / q.sum()))


def binary_kl(posterior: float, prior: float) -> float:
    p, q = np.clip([posterior, prior], 1e-6, 1 - 1e-6)
    return float(entropy([p, 1 - p], [q, 1 - q]))


class BeliefAnalysis:
    def __init__(self, prior: Belief, search: Belief, code: Belief):
        self.prior, self.search, self.code = prior, search, code
        self.kl_code_search = categorical_kl(code, search)
        self.kl_code_param = categorical_kl(code, prior)
        self.kl_search_param = categorical_kl(search, prior)

    def evaluate(self, threshold: float) -> SurprisalResult:
        change = abs(self.code.prob_true - self.search.prob_true)
        dm = self.dirichlet_incompatibility()
        return SurprisalResult(
            belief_change=change,
            kl_divergence=binary_kl(self.code.prob_true, self.search.prob_true),
            is_surprising=change >= threshold,
            kl_code_search=self.kl_code_search,
            kl_search_param=self.kl_search_param,
            r_ice=self.kl_code_search / max(1e-6, self.kl_code_param),
            log_r_ice=math.log((self.kl_code_search + 1e-3) / (self.kl_code_param + 1e-3)),
            r_ice_norm=self.kl_code_search / (self.kl_code_search + self.kl_code_param + 1e-3),
            fidelity=1 - math.tanh(self.kl_code_search),
            incompatibility_c_dm=dm,
            incompatibility_c_ce=self.cross_entropy(),
            incompatibility_c_credal=self.credal_incompatibility(),
            efe=float(entropy(self.code.prob_vector)) + self.code.prob_true * (1 - self.code.prob_true),
        )

    def dirichlet_incompatibility(self) -> float:
        counts = np.array([self.search.category_counts[name] for name in CATEGORIES], dtype=np.float64)
        alpha = np.array([self.prior.category_counts[name] for name in CATEGORIES], dtype=np.float64) + 1
        n = self.search.n_samples
        log_p = (
            gammaln(n + 1)
            - gammaln(counts + 1).sum()
            + gammaln(alpha.sum())
            - gammaln(alpha.sum() + n)
            + (gammaln(alpha + counts) - gammaln(alpha)).sum()
        )
        return float(-log_p)

    def probabilities(self) -> tuple[np.ndarray, np.ndarray]:
        p, q = np.clip(self.search.prob_vector, 1e-9, 1), np.clip(self.prior.prob_vector, 1e-9, 1)
        return p / p.sum(), q / q.sum()

    def cross_entropy(self) -> float:
        p, q = self.probabilities()
        return float(-(p * np.log(q)).sum())

    def credal_incompatibility(self) -> float:
        p, q = self.probabilities()
        lower = np.maximum(1e-9, q - np.sqrt(q * (1 - q) / self.prior.n_samples))
        return float(entropy(p, lower / lower.sum()))

    @property
    def reward(self) -> float:
        return math.tanh(self.kl_code_search)

    def external_value(self, result, search) -> float:
        external = result.belief
        if external is None:
            return 0.0
        information = math.tanh(categorical_kl(external, self.code))
        return search.external_opportunity_weight * max(
            0.0, information - search.external_cost_weight * result.estimated_cost
        )
