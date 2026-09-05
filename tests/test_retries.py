from contextlib import contextmanager
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from urithiru.agents.goals import RETRY_BACKOFF_SECONDS, ResearchAgent
from urithiru.core.models import Dataset
from urithiru.runtime.control import Cancelled


@contextmanager
def patched():
    with (
        patch("urithiru.agents.goals.emit"),
        patch("urithiru.agents.goals.prompt", return_value="goal text"),
    ):
        yield


def make_agent(stage_attempts: int, stop: Event | None = None) -> ResearchAgent:
    sandbox = MagicMock()
    sandbox.config.budget.stage_attempts = stage_attempts
    sandbox.config.budget.seconds.return_value = 60
    sandbox.dataset = Dataset(files=[], metadata="schema", hashes={})
    sandbox.stop = stop or Event()
    return ResearchAgent(sandbox)


def test_a_failing_stage_waits_longer_before_each_further_attempt():
    agent = make_agent(stage_attempts=3)
    agent.sandbox.run.side_effect = RuntimeError("agent exited with status 1")

    waits: list[float] = []
    agent.stop = MagicMock()
    agent.stop.wait.side_effect = lambda seconds: waits.append(seconds) or False

    with pytest.raises(RuntimeError), patched():
        agent.stage("search_node_000001", "search", {})

    assert waits == [RETRY_BACKOFF_SECONDS, RETRY_BACKOFF_SECONDS * 2]
    assert agent.sandbox.run.call_count == 3


def test_a_single_attempt_budget_never_waits():
    agent = make_agent(stage_attempts=1)
    agent.sandbox.run.side_effect = RuntimeError("agent exited with status 1")
    agent.stop = MagicMock()

    with pytest.raises(RuntimeError), patched():
        agent.stage("search_node_000001", "search", {})

    agent.stop.wait.assert_not_called()


def test_cancelling_during_the_wait_stops_the_run_rather_than_retrying():
    stop = Event()
    stop.set()
    agent = make_agent(stage_attempts=3, stop=stop)
    agent.sandbox.run.side_effect = RuntimeError("agent exited with status 1")

    with pytest.raises(Cancelled), patched():
        agent.stage("search_node_000001", "search", {})

    assert agent.sandbox.run.call_count == 1


def test_cancellation_from_the_agent_is_never_retried():
    agent = make_agent(stage_attempts=3)
    agent.sandbox.run.side_effect = Cancelled("operator cancelled")

    with pytest.raises(Cancelled), patched():
        agent.stage("search_node_000001", "search", {})

    assert agent.sandbox.run.call_count == 1


def experiment_result(**overrides):
    from urithiru.core.models import Experiment

    fields = {
        "execution_success": True,
        "test_spec_valid": True,
        "direction_supported": True,
        "empirical_support": True,
        "category_counts": {
            "definitely false": 0,
            "maybe false": 4,
            "uncertain": 6,
            "maybe true": 14,
            "definitely true": 6,
        },
        "rationale": "because",
        "metrics": {"n": 158},
        "p_value": 0.08,
        "p_value_corrected": 0.204,
        "stdout": "",
        "stderr": "",
        "summary": "",
    }
    return Experiment(**(fields | overrides))


def test_a_directional_effect_that_fails_correction_may_withhold_support():
    result = experiment_result(empirical_support=False)
    assert result.empirical_support is False
    assert result.direction_supported is True


def test_support_still_requires_all_three_flags():
    import pytest as _pytest

    for missing in ("execution_success", "test_spec_valid", "direction_supported"):
        with _pytest.raises(ValueError, match="Empirical support requires"):
            experiment_result(**{missing: False})
