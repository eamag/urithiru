import math

import numpy as np

from urithiru.core.models import Belief, External, Surprisal


def categorical_kl(posterior: Belief, prior: Belief) -> float:
    posterior_probs = np.clip(posterior.prob_vector, 1e-9, 1)
    prior_probs = np.clip(prior.prob_vector, 1e-9, 1)
    posterior_probs = posterior_probs / posterior_probs.sum()
    prior_probs = prior_probs / prior_probs.sum()
    return float((posterior_probs * np.log(posterior_probs / prior_probs)).sum())


class BeliefAnalysis:
    def __init__(self, prior: Belief, search: Belief, code: Belief):
        self.search_param = categorical_kl(search, prior)
        self.code_search = categorical_kl(code, search)
        self.code_param = categorical_kl(code, prior)
        self.belief_change = abs(code.prob_true - search.prob_true)

    @property
    def reward(self) -> float:
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
    if external is None or external.belief is None:
        return 0.0
    information = math.tanh(categorical_kl(external.belief, code))
    return opportunity * max(0.0, information - cost * external.estimated_cost)
