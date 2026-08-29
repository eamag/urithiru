"""Information gained at each hop: naked prior -> literature -> experiment -> elsewhere.

Every measure is a KL divergence in nats over the same five categories, so the hops are
directly comparable and their ratio means something.
"""

import math

import numpy as np

from urithiru.core.models import Belief, External, Surprisal


def categorical_kl(posterior: Belief, prior: Belief) -> float:
    p, q = np.clip(posterior.prob_vector, 1e-9, 1), np.clip(prior.prob_vector, 1e-9, 1)
    p, q = p / p.sum(), q / q.sum()
    return float((p * np.log(p / q)).sum())


class BeliefAnalysis:
    """The three hops of one evaluation, measured once and read many ways."""

    def __init__(self, prior: Belief, search: Belief, code: Belief):
        self.search_param = categorical_kl(search, prior)
        self.code_search = categorical_kl(code, search)
        self.code_param = categorical_kl(code, prior)
        self.belief_change = abs(code.prob_true - search.prob_true)

    @property
    def reward(self) -> float:
        """A hypothesis is worth exploring from when running the analysis moved the belief."""
        return math.tanh(self.code_search)

    def surprisal(self, minimum: float) -> Surprisal:
        return Surprisal(
            kl_search_param=self.search_param,
            kl_code_search=self.code_search,
            kl_code_param=self.code_param,
            r_ice_norm=self.code_search / (self.code_search + self.code_param + 1e-3),
            belief_change=self.belief_change,
            is_surprising=self.reward >= minimum,
        )


def external_value(external: External | None, code: Belief, opportunity: float, cost: float) -> float:
    """Independent evidence earns its keep only when it moves the belief more than it costs.

    A stage that never ran and a stage that ran and abstained are both worth nothing.
    """
    if external is None or external.belief is None:
        return 0.0
    information = math.tanh(categorical_kl(external.belief, code))
    return opportunity * max(0.0, information - cost * external.estimated_cost)
