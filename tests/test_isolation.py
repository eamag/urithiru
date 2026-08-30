"""Tests asserting the data and workspace isolation guarantees as verifiable claims.

Isolation Guarantee:
1. Data-blindness is structural: DATA_STAGES excludes 'search' and 'external'. The literature
   agent's workspace receives goal.txt and nothing else; seed data is physically absent.
2. Distinct workspaces: each goal receives its own dedicated directory under sandbox_artifacts/<goal.id>.
3. Distinct HOME directories: each goal in CloudSandbox gets a private HOME outside the run
   artifacts, preventing scratch-file leakage across stages.
4. Tight trust boundary: trustedWorkspaces names only /workspace and the goal's own resolved
   workspace path, never the parent directory containing other goals' workspaces.
5. gVisor fallback disclosure: when Cloud Run gVisor sandbox launcher is missing, the run
   transparently falls back to in-container isolation and emits 'sandbox_unavailable'.
"""

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
    """Verify that literature search and external stages are strictly excluded from DATA_STAGES."""
    assert "proposal" in DATA_STAGES
    assert "code" in DATA_STAGES
    assert "search" not in DATA_STAGES
    assert "external" not in DATA_STAGES
    assert DATA_STAGES == ("proposal", "code")


def test_literature_workspace_never_receives_seed_data(tmp_path):
    """Verify that running a literature goal does NOT copy seed data into its workspace."""
    config = make_dummy_config("docker")
    # Create fake staged input file
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

    # Mock execute so we don't actually spawn docker
    sandbox.execute = MagicMock()

    # Run search stage
    search_goal = Goal(id="search_node_000001", stage="search", prompt="Literature search prompt")
    search_ws = sandbox.run(search_goal)

    # Verify search workspace contains goal.txt and NO dataset files
    assert (search_ws / "goal.txt").exists()
    assert not (search_ws / "inputs").exists()
    assert not (search_ws / "inputs" / "000_data.csv").exists()

    # Run code stage
    code_goal = Goal(id="code_node_000001", stage="code", prompt="Code analysis prompt")
    code_ws = sandbox.run(code_goal)

    # Verify code workspace DOES contain seed data copy
    assert (code_ws / "goal.txt").exists()
    assert (code_ws / "inputs" / "000_data.csv").exists()


def test_distinct_workspaces_and_private_homes(tmp_path):
    """Verify that each goal gets its own workspace and distinct HOME directory."""
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

    # Retrying g1 resets ONLY g1's home without touching g2's home
    (home1 / "scratch.txt").write_text("temp data")
    (home2 / "scratch.txt").write_text("temp data")
    sandbox.reset(g1)
    assert not (home1 / "scratch.txt").exists()
    assert (home2 / "scratch.txt").exists()


def test_trusted_workspaces_isolation():
    """Verify trustedWorkspaces restricts agent to only its own workspace path."""
    ws = Path("/tmp/urithiru/runs/123/sandbox_artifacts/search_01")
    settings = agent_settings(ws)
    trusted = settings["trustedWorkspaces"]

    assert "/workspace" in trusted
    assert str(ws.resolve()) in trusted
    # Ensure parent containing all goals is NOT trusted
    assert str(ws.parent.resolve()) not in trusted
    assert len(trusted) == 2


def test_gvisor_fallback_disclosure_and_event_emission(tmp_path):
    """Verify that absence of gVisor binary logs fallback and emits sandbox_unavailable warning."""
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
