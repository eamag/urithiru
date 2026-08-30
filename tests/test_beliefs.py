"""Tests for belief arithmetic, 30-vote posterior, and evaluation metrics."""

import math

import numpy as np
import pytest

from urithiru.core.beliefs import BeliefAnalysis, categorical_kl, external_value
from urithiru.core.models import (
    Belief,
    Evaluation,
    Experiment,
    External,
    Literature,
    Surprisal,
)


def make_counts(d_false=0, m_false=0, uncert=0, m_true=0, d_true=0) -> dict[str, int]:
    return {
        "definitely false": d_false,
        "maybe false": m_false,
        "uncertain": uncert,
        "maybe true": m_true,
        "definitely true": d_true,
    }


def test_belief_validation_all_categories_required():
    with pytest.raises(ValueError, match="All five belief categories are required"):
        Belief({"definitely false": 10, "uncertain": 20}, rationale="incomplete")


def test_belief_validation_nonnegative_and_finite():
    counts = make_counts(d_false=-1, uncert=31)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        Belief(counts, rationale="negative count")

    counts_inf = make_counts(d_false=float("inf"), uncert=30)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        Belief(counts_inf, rationale="infinite count")


def test_belief_validation_positive_sum():
    counts = make_counts(0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="sum to a positive value"):
        Belief(counts, rationale="zero votes")


def test_belief_prob_vector_and_posterior_calculation():
    # 30 votes all on "definitely true"
    b_true = Belief(make_counts(d_true=30), rationale="pure true")
    assert np.allclose(b_true.prob_vector, [0, 0, 0, 0, 1.0])
    assert b_true.n_true == 30.0
    # prob_true = (0.5 + 30) / (0.5 + 0.5 + 30) = 30.5 / 31.0
    expected_prob_true = 30.5 / 31.0
    assert math.isclose(b_true.prob_true, expected_prob_true)
    assert b_true.category == "definitely true"

    # 30 votes all on "definitely false"
    b_false = Belief(make_counts(d_false=30), rationale="pure false")
    assert np.allclose(b_false.prob_vector, [1.0, 0, 0, 0, 0])
    assert b_false.n_true == 0.0
    assert math.isclose(b_false.prob_true, 0.5 / 31.0)
    assert b_false.category == "definitely false"

    # Uniform votes: 6 in each of the 5 categories
    b_uniform = Belief(make_counts(6, 6, 6, 6, 6), rationale="uniform")
    assert np.allclose(b_uniform.prob_vector, [0.2, 0.2, 0.2, 0.2, 0.2])
    # scores: 0, 0.25, 0.5, 0.75, 1.0 -> mean = 0.5
    # n_true = 0.5 * 30 = 15.0
    assert math.isclose(b_uniform.n_true, 15.0)
    # prob_true = (0.5 + 15) / 31 = 15.5 / 31 = 0.5
    assert math.isclose(b_uniform.prob_true, 0.5)
    assert b_uniform.category == "uncertain"


def test_categorical_kl():
    b1 = Belief(make_counts(6, 6, 6, 6, 6), rationale="uniform")
    b2 = Belief(make_counts(6, 6, 6, 6, 6), rationale="uniform")
    # Same distribution -> KL is ~0
    assert math.isclose(categorical_kl(b1, b2), 0.0, abs_tol=1e-6)

    # Different distribution -> KL > 0
    b3 = Belief(make_counts(d_true=30), rationale="true")
    kl = categorical_kl(b3, b1)
    assert kl > 0.0


def test_belief_analysis_rewards_and_surprisal():
    prior = Belief(make_counts(6, 6, 6, 6, 6), rationale="prior")
    search = Belief(make_counts(m_false=10, uncert=20), rationale="search")
    code = Belief(make_counts(d_true=30), rationale="code")

    analysis = BeliefAnalysis(prior=prior, search=search, code=code)

    assert analysis.reward == math.tanh(analysis.code_search)
    assert math.isclose(analysis.belief_change, abs(code.prob_true - search.prob_true))

    surprisal = analysis.surprisal(minimum=0.2)
    assert isinstance(surprisal, Surprisal)
    assert surprisal.kl_search_param == analysis.search_param
    assert surprisal.kl_code_search == analysis.code_search
    assert surprisal.kl_code_param == analysis.code_param
    assert surprisal.is_surprising == (analysis.reward >= 0.2)


def test_external_value():
    code = Belief(make_counts(d_true=30), rationale="code")
    opportunity = 2.0
    cost = 0.1

    # When external is None
    assert external_value(None, code, opportunity, cost) == 0.0

    # When external belief is None (abstained)
    ext_abstained = External(
        source="zenodo",
        category_counts=None,
        rationale="no data found",
        estimated_cost=5.0,
        summary="abstained",
    )
    assert external_value(ext_abstained, code, opportunity, cost) == 0.0

    # When external has valid belief
    ext_valid = External(
        source="zenodo",
        category_counts=make_counts(d_false=30),
        rationale="found opposing data",
        estimated_cost=1.0,
        summary="opposing",
    )
    val = external_value(ext_valid, code, opportunity, cost)
    assert val > 0.0


def test_evaluation_verdict_and_summary():
    prior = Belief(make_counts(6, 6, 6, 6, 6), rationale="prior")
    lit = Literature(category_counts=make_counts(uncert=30), rationale="lit", findings={})
    exp = Experiment(
        execution_success=True,
        test_spec_valid=True,
        direction_supported=True,
        empirical_support=True,
        category_counts=make_counts(d_true=30),
        rationale="exp",
        metrics={"p": 0.01},
        p_value=0.01,
        p_value_corrected=0.01,
        stdout="ok",
        stderr="",
        summary="supported",
    )
    surprisal = Surprisal(
        kl_search_param=0.1,
        kl_code_search=0.8,
        kl_code_param=0.9,
        r_ice_norm=0.5,
        belief_change=0.4,
        is_surprising=True,
    )

    # Without external
    ev_no_ext = Evaluation(
        prior=prior,
        literature=lit,
        experiment=exp,
        external=None,
        external_error=None,
        surprisal=surprisal,
        reward=0.7,
        external_value=0.0,
    )
    assert ev_no_ext.verdict == "no independent data"
    assert ev_no_ext.posterior == exp.belief
    assert ev_no_ext.total_reward == 0.7

    # With replicating external
    ext_rep = External(
        source="openalex",
        category_counts=make_counts(d_true=30),
        rationale="agrees",
        estimated_cost=0.5,
        summary="replicated",
    )
    ev_rep = Evaluation(
        prior=prior,
        literature=lit,
        experiment=exp,
        external=ext_rep,
        external_error=None,
        surprisal=surprisal,
        reward=0.7,
        external_value=0.5,
    )
    assert ev_rep.verdict == "replicated"
    assert ev_rep.total_reward == 1.2

    # With contradicting external
    ext_contra = External(
        source="openalex",
        category_counts=make_counts(d_false=30),
        rationale="disagrees",
        estimated_cost=0.5,
        summary="contradicted",
    )
    ev_contra = Evaluation(
        prior=prior,
        literature=lit,
        experiment=exp,
        external=ext_contra,
        external_error=None,
        surprisal=surprisal,
        reward=0.7,
        external_value=0.5,
    )
    assert ev_contra.verdict == "contradicted"

    summary = ev_contra.summary()
    assert summary["verdict"] == "contradicted"
    assert summary["empirical_support"] is True
    assert summary["reward"] == 1.2
