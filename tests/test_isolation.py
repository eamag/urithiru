from dataclasses import asdict
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

from urithiru.core.models import DATA_STAGES, Dataset, Goal
from urithiru.runtime.config import Budget, Config, DockerConfig, GoogleConfig, ModelConfig, SearchConfig
from urithiru.runtime.files import write_json
from urithiru.runtime.sandbox import (
    CLOUD_SANDBOX,
    CloudSandbox,
    DockerSandbox,
    Sandbox,
    agent_settings,
)


def make_dummy_config(runtime: str = "docker") -> Config:
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
    if runtime == "docker":
        options = DockerConfig(
            image="urithiru-sandbox:latest",
            credential_volume="agy_credentials",
        )
    else:
        options = GoogleConfig(
            project="test-project",
            region="us-central1",
            bucket="test-bucket",
            prefix="runs",
            orchestrator_job="test-job",
        )
    return Config(
        runtime=runtime,
        budget=budget,
        search=search,
        models=models,
        options=options,
    )


def test_data_stages_definition_guarantee():
    assert "proposal" in DATA_STAGES
    assert "code" in DATA_STAGES
    assert "search" not in DATA_STAGES
    assert "external" not in DATA_STAGES
    assert DATA_STAGES == ("proposal", "code")


def test_literature_workspace_never_receives_seed_data(tmp_path):
    config = make_dummy_config("docker")
    input_file = tmp_path / "inputs" / "000_data.csv"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("a,b\n1,2\n")

    from urithiru.runtime.files import file_hash

    dataset = Dataset(
        files=["inputs/000_data.csv"],
        metadata="Schema info",
        hashes={"inputs/000_data.csv": file_hash(input_file)},
    )
    stop = Event()
    sandbox = DockerSandbox(config, dataset, tmp_path, stop)

    sandbox.execute = MagicMock()

    search_goal = Goal(id="search_node_000001", stage="search", prompt="Literature search prompt")
    search_ws = sandbox.run(search_goal)

    assert (search_ws / "goal.txt").exists()
    assert not (search_ws / "inputs").exists()
    assert not (search_ws / "inputs" / "000_data.csv").exists()

    code_goal = Goal(id="code_node_000001", stage="code", prompt="Code analysis prompt")
    code_ws = sandbox.run(code_goal)

    assert (code_ws / "goal.txt").exists()
    assert (code_ws / "inputs" / "000_data.csv").exists()


def test_distinct_workspaces_and_private_homes(tmp_path):
    config = make_dummy_config("google")
    dataset = Dataset(files=[], metadata="", hashes={})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_json(run_dir / "run_config.json", {"config": asdict(config), "dataset": asdict(dataset)})

    cloud = MagicMock()
    stop = Event()

    sandbox = CloudSandbox(cloud, run_dir, stop)

    g1 = Goal(id="search_node_000001", stage="search", prompt="Search")
    g2 = Goal(id="code_node_000001", stage="code", prompt="Code")

    ws1 = sandbox.workspace(g1)
    ws2 = sandbox.workspace(g2)
    assert ws1 != ws2
    assert ws1.name == "search_node_000001"
    assert ws2.name == "code_node_000001"

    home1 = sandbox.agent_home(g1, ws1)
    home2 = sandbox.agent_home(g2, ws2)
    assert home1 != home2
    assert home1.parent == sandbox.homes
    assert home2.parent == sandbox.homes

    (home1 / "scratch.txt").write_text("temp data")
    (home2 / "scratch.txt").write_text("temp data")
    sandbox.reset(g1)
    assert not (home1 / "scratch.txt").exists()
    assert (home2 / "scratch.txt").exists()


def test_trusted_workspaces_isolation():
    ws = Path("/tmp/urithiru/runs/123/sandbox_artifacts/search_01")
    settings = agent_settings(ws)
    trusted = settings["trustedWorkspaces"]

    assert "/workspace" in trusted
    assert str(ws.resolve()) in trusted
    assert str(ws.parent.resolve()) not in trusted
    assert len(trusted) == 2


def test_gvisor_fallback_disclosure_and_event_emission(tmp_path):
    config = make_dummy_config("google")
    dataset = Dataset(files=[], metadata="", hashes={})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_json(run_dir / "run_config.json", {"config": asdict(config), "dataset": asdict(dataset)})

    cloud = MagicMock()
    stop = Event()
    with (
        patch("urithiru.runtime.sandbox.emit") as mock_emit,
        patch("pathlib.Path.exists", return_value=False),
    ):
        sandbox = CloudSandbox(cloud, run_dir, stop)
        assert sandbox.isolated is False
        mock_emit.assert_called_once_with(
            "sandbox_unavailable",
            severity="WARNING",
            path=CLOUD_SANDBOX,
            isolation="container",
        )


def test_docker_runtime_shares_one_agent_home_across_goals(tmp_path):
    config = make_dummy_config("docker")
    dataset = Dataset(files=[], metadata="", hashes={})
    sandbox = DockerSandbox(config, dataset, tmp_path, Event())

    first = Goal(id="search_node_000001", stage="search", prompt="")
    second = Goal(id="code_node_000001", stage="code", prompt="")

    def home_mount(goal: Goal) -> str:
        argv = sandbox.launch(goal, tmp_path / goal.id)
        return argv[argv.index("-v") + 1]

    assert home_mount(first) == home_mount(second) == "agy_credentials:/root"
    assert type(sandbox).reset is Sandbox.reset
