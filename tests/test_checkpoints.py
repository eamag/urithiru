from unittest.mock import MagicMock

import pytest

from urithiru.core.engine import UrithiruEngine
from urithiru.core.models import (
    Belief,
    CandidateAudit,
    Evaluation,
    Experiment,
    Literature,
    Surprisal,
)
from urithiru.core.tree import MCTSTree
from urithiru.runtime.config import Budget, Config, DockerConfig, ModelConfig, SearchConfig
from urithiru.runtime.files import read_json, write_json
from urithiru.runtime.runs import amend_budget


def make_dummy_config() -> Config:
    budget = Budget(
        proposal_minutes=5,
        search_minutes=8,
        code_minutes=10,
        external_minutes=10,
        grace_minutes=4,
        max_output_tokens=4096,
        input_mib=50,
        stage_attempts=2,
    )
    search = SearchConfig(
        parallelism=2,
        branching_factor=5,
        top_k=5,
        uct_c=1.414,
        external_minimum_surprise=0.3,
        external_opportunity_weight=1.0,
        external_cost_weight=0.1,
    )
    models = ModelConfig(
        agent="gemini-3.7-flash",
        prior="gemini-3.7-flash",
        deduplication="gemini-3.5-flash-lite",
        embedding="text-embedding-005",
        temperature=0.7,
        effort="medium",
    )
    options = DockerConfig(
        image="urithiru-sandbox:latest",
        credential_volume="agy_credentials",
    )
    return Config(
        runtime="docker",
        budget=budget,
        search=search,
        models=models,
        options=options,
    )


def make_dummy_evaluation(reward: float = 0.5) -> Evaluation:
    counts = {
        "definitely false": 0,
        "maybe false": 0,
        "uncertain": 6,
        "maybe true": 0,
        "definitely true": 24,
    }
    prior = Belief(counts, "prior")
    lit = Literature(counts, "lit", {"summary": "lit finding"})
    exp = Experiment(
        execution_success=True,
        test_spec_valid=True,
        direction_supported=True,
        empirical_support=True,
        category_counts=counts,
        rationale="exp",
        metrics={"f_stat": 4.2},
        p_value=0.03,
        p_value_corrected=0.03,
        stdout="done",
        stderr="",
        summary="supported",
    )
    surprisal = Surprisal(0.2, 0.4, 0.5, 0.6, 0.2, False)
    return Evaluation(
        prior=prior,
        literature=lit,
        experiment=exp,
        external=None,
        external_error=None,
        surprisal=surprisal,
        reward=reward,
        external_value=0.0,
    )


def test_node_and_tree_serialization_roundtrip():
    tree = MCTSTree(exploration=1.414)
    child = tree.add(tree.root, "Hypothesis 1")
    child.queue = ["c1", "c2"]
    child.tried = ["tried_claim"]
    child.visits = 1
    child.value = 0.75
    child.terminal = False
    child.evidence = ["Evidence piece"]
    child.generation = 1
    child.prior = Belief(
        {
            "definitely false": 6,
            "maybe false": 6,
            "uncertain": 6,
            "maybe true": 6,
            "definitely true": 6,
        },
        "prior",
    )
    child.evaluation = make_dummy_evaluation(0.75)
    child.candidates = [
        CandidateAudit(
            id="c1",
            claim="Hypothesis 1",
            generation=1,
            duplicate_of=None,
            similarity=None,
            prior=0.5,
            selected=True,
            selected_step=1,
            rejection_reason=None,
        )
    ]
    tree.root.visits = 1
    tree.root.value = 0.75

    import json
    from dataclasses import asdict

    records = json.loads(json.dumps([node.to_dict() for node in tree.nodes.values()], default=asdict))

    restored_tree = MCTSTree(exploration=1.414)
    restored_tree.restore(records)

    assert "root" in restored_tree.nodes
    assert child.id in restored_tree.nodes
    restored_child = restored_tree.nodes[child.id]
    assert restored_child.claim == "Hypothesis 1"
    assert restored_child.visits == 1
    assert restored_child.value == 0.75
    assert restored_child.parent == restored_tree.root
    assert restored_child.evaluation is not None
    assert restored_child.evaluation.reward == 0.75
    assert len(restored_child.candidates) == 1
    assert restored_child.candidates[0].claim == "Hypothesis 1"


def test_engine_checkpoint_save_and_load(tmp_path):
    config = make_dummy_config()
    agent = MagicMock()
    agent.directory = tmp_path
    agent.schema = "Schema description"
    model = MagicMock()

    engine = UrithiruEngine(config, agent, model, steps=3, seed=42)
    node = engine.tree.add(engine.tree.root, "Evaluated claim")
    node.evaluation = make_dummy_evaluation(0.6)
    engine.tree.backpropagate(node)
    engine.completed.append(node)
    engine.generation = 1

    engine.save_checkpoint()

    assert (tmp_path / "mcts_state.json").exists()
    assert (tmp_path / "candidate_audits.json").exists()

    engine2 = UrithiruEngine(config, agent, model, steps=3, seed=42)
    engine2.load_checkpoint()

    assert len(engine2.completed) == 1
    assert engine2.completed[0].id == node.id
    assert engine2.completed[0].claim == "Evaluated claim"
    assert engine2.generation == 1
    assert engine2.tree.root.visits == 1


def test_engine_budget_growth_guard(tmp_path):
    config = make_dummy_config()
    agent = MagicMock()
    agent.directory = tmp_path
    agent.schema = "Schema"
    model = MagicMock()

    engine = UrithiruEngine(config, agent, model, steps=5, seed=42)
    engine.save_checkpoint()

    engine_shrunk = UrithiruEngine(config, agent, model, steps=3, seed=42)
    with pytest.raises(ValueError, match="a budget can only grow"):
        engine_shrunk.load_checkpoint()

    engine_grown = UrithiruEngine(config, agent, model, steps=6, seed=42)
    engine_grown.load_checkpoint()
    assert engine_grown.steps == 6


def test_engine_seed_and_visit_invariance_guards(tmp_path):
    config = make_dummy_config()
    agent = MagicMock()
    agent.directory = tmp_path
    agent.schema = "Schema"
    model = MagicMock()

    engine = UrithiruEngine(config, agent, model, steps=3, seed=42)
    engine.save_checkpoint()

    engine_diff_seed = UrithiruEngine(config, agent, model, steps=3, seed=999)
    with pytest.raises(ValueError, match="Run seed differs from the checkpoint"):
        engine_diff_seed.load_checkpoint()

    checkpoint = read_json(tmp_path / "mcts_state.json")
    checkpoint["nodes"][0]["visits"] = 99
    write_json(tmp_path / "mcts_state.json", checkpoint)

    engine_corrupted = UrithiruEngine(config, agent, model, steps=3, seed=42)
    with pytest.raises(ValueError, match="Checkpoint root visits differ from completed evaluations"):
        engine_corrupted.load_checkpoint()


def test_amend_budget_shrinking_rejected(tmp_path):
    config = make_dummy_config()
    run_record = {
        "config": {
            "runtime": config.runtime,
            "budget": {
                "proposal_minutes": config.budget.proposal_minutes,
                "search_minutes": config.budget.search_minutes,
                "code_minutes": config.budget.code_minutes,
                "external_minutes": config.budget.external_minutes,
                "grace_minutes": config.budget.grace_minutes,
                "max_output_tokens": config.budget.max_output_tokens,
                "input_mib": config.budget.input_mib,
                "stage_attempts": config.budget.stage_attempts,
            },
            "search": {
                "parallelism": config.search.parallelism,
                "branching_factor": config.search.branching_factor,
                "top_k": config.search.top_k,
                "uct_c": config.search.uct_c,
                "external_minimum_surprise": config.search.external_minimum_surprise,
                "external_opportunity_weight": config.search.external_opportunity_weight,
                "external_cost_weight": config.search.external_cost_weight,
            },
            "models": {
                "agent": config.models.agent,
                "prior": config.models.prior,
                "deduplication": config.models.deduplication,
                "embedding": config.models.embedding,
                "temperature": config.models.temperature,
                "effort": config.models.effort,
            },
            "options": {
                "image": config.options.image,
                "credential_volume": config.options.credential_volume,
            },
        },
        "dataset": {"files": [], "metadata": "", "hashes": {}},
        "steps": 4,
        "seed": 42,
    }
    write_json(tmp_path / "run_config.json", run_record)

    with pytest.raises(ValueError, match="a budget can only grow"):
        amend_budget(tmp_path, steps=2, minutes={})

    amended, new_config = amend_budget(tmp_path, steps=6, minutes={"code_minutes": 15})
    assert amended["steps"] == 6
    assert new_config.budget.code_minutes == 15
