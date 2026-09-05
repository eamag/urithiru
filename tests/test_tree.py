import math

import pytest

from urithiru.core.models import (
    Belief,
    Evaluation,
    Experiment,
    Literature,
    Surprisal,
)
from urithiru.core.tree import MCTSTree, Node


def make_dummy_evaluation(reward: float = 0.8) -> Evaluation:
    counts = {
        "definitely false": 0,
        "maybe false": 0,
        "uncertain": 0,
        "maybe true": 0,
        "definitely true": 30,
    }
    prior = Belief(counts, "prior")
    lit = Literature(counts, "lit", {})
    exp = Experiment(
        execution_success=True,
        test_spec_valid=True,
        direction_supported=True,
        empirical_support=True,
        category_counts=counts,
        rationale="exp",
        metrics={},
        p_value=0.01,
        p_value_corrected=0.01,
        stdout="",
        stderr="",
        summary="",
    )
    surprisal = Surprisal(0.1, 0.1, 0.1, 0.5, 0.1, True)
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


def test_node_uct_formula():
    root = Node("root", None, "")
    root.visits = 10
    child = Node("c1", root, "Claim 1")

    assert child.uct(exploration=1.414) == math.inf

    child.visits = 2
    child.value = 1.5
    expected = 1.5 / 2 + 1.414 * math.sqrt(math.log(10 + 1) / 2)
    assert math.isclose(child.uct(exploration=1.414), expected)


def test_node_progressive_widening():
    node = Node("n", None, "Claim")
    assert not node.can_widen()

    node.queue = ["cand_1"]
    assert node.can_widen()

    c1 = Node("c1", node, "Child 1")
    node.children.append(c1)

    node.visits = 0
    assert not node.can_widen()

    node.visits = 1
    assert node.can_widen()

    c2 = Node("c2", node, "Child 2")
    node.children.append(c2)
    node.visits = 4
    assert node.can_widen()


def test_node_ancestors():
    root = Node("root", None, "")
    c1 = Node("c1", root, "First Claim")
    c2 = Node("c2", c1, "Second Claim")
    c3 = Node("c3", c2, "Third Claim")

    assert c3.ancestors == ["First Claim", "Second Claim", "Third Claim"]


def test_mcts_tree_select_and_backpropagate():
    tree = MCTSTree(exploration=1.414)
    assert tree.root.id == "root"

    assert tree.select() == tree.root

    tree.root.queue = ["c_1", "c_2"]
    assert tree.select() == tree.root

    child1 = tree.add(tree.root, "Hypothesis 1")
    child2 = tree.add(tree.root, "Hypothesis 2")

    selected = tree.select()
    assert selected in (child1, child2)

    with pytest.raises(ValueError, match="Cannot update the tree without a completed evaluation"):
        tree.backpropagate(child1)

    child1.evaluation = make_dummy_evaluation(reward=0.75)
    tree.backpropagate(child1)

    assert child1.visits == 1
    assert child1.value == 0.75
    assert tree.root.visits == 1
    assert tree.root.value == 0.75

    child2.evaluation = make_dummy_evaluation(reward=0.25)
    tree.backpropagate(child2)

    assert child2.visits == 1
    assert child2.value == 0.25
    assert tree.root.visits == 2
    assert tree.root.value == 1.0


def test_mcts_tree_select_skips_terminal():
    tree = MCTSTree(exploration=1.414)
    tree.root.visits = 5
    c1 = tree.add(tree.root, "H1")
    c2 = tree.add(tree.root, "H2")

    c1.terminal = True
    c1.visits = 1
    c1.value = 10.0

    c2.visits = 1
    c2.value = 1.0

    selected = tree.select()
    assert selected == c2
