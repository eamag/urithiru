"""Tests for sandbox command and argument construction (pure, no Docker/gVisor needed)."""

from threading import Event
from unittest.mock import MagicMock, patch

from urithiru.core.models import Dataset, Goal
from urithiru.runtime.config import Budget, Config, DockerConfig, GoogleConfig, ModelConfig, SearchConfig
from urithiru.runtime.sandbox import (
    AGENT_HOME,
    AGENT_LOCATION,
    ANALYSIS_BIN,
    CLOUD_AGENT,
    CLOUD_SANDBOX,
    DOCKER_AGENT,
    WORKSPACE,
    CloudSandbox,
    DockerSandbox,
    agent_prompt,
    agent_settings,
)


def make_test_config(runtime: str = "docker") -> Config:
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
            image="urithiru-sandbox:v1",
            credential_volume="agy_credentials",
        )
    else:
        options = GoogleConfig(
            project="test-project-123",
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


def test_agent_prompt():
    prompt = agent_prompt("/custom/workspace")
    assert "/custom/workspace/goal.txt" in prompt
    assert "into /custom/workspace" in prompt
    assert "Nothing outside /custom/workspace is read back" in prompt


def test_docker_sandbox_argument_construction(tmp_path):
    config = make_test_config("docker")
    dataset = Dataset(files=[], metadata="", hashes={})
    stop = Event()
    sandbox = DockerSandbox(config, dataset, tmp_path, stop)

    goal = Goal(id="code_node_000001", stage="code", prompt="Run analysis")
    workspace = tmp_path / "sandbox_artifacts" / goal.id
    workspace.mkdir(parents=True)

    with patch("subprocess.run"):
        cmd = sandbox.launch(goal, workspace)

    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "--memory=4g" in cmd
    assert "--cpus=3" in cmd
    assert "--security-opt=no-new-privileges" in cmd
    assert f"--name=urithiru_{tmp_path.name}_{goal.id}" in cmd or f"urithiru_{tmp_path.name}_{goal.id}" in cmd
    assert f"{config.options.credential_volume}:/root" in cmd
    assert f"{workspace.resolve()}:{WORKSPACE}" in cmd
    assert "--entrypoint" in cmd
    assert DOCKER_AGENT in cmd
    assert config.options.image in cmd
    assert "--print" in cmd
    assert "--model" in cmd
    assert "gemini-3.7-flash" in cmd
    assert "--effort" in cmd
    assert "medium" in cmd
    assert "--print-timeout" in cmd
    assert "10m" in cmd  # code_minutes is 10
    assert "--dangerously-skip-permissions" in cmd


def test_cloud_sandbox_agent_settings(tmp_path):
    workspace = tmp_path / "sandbox_artifacts" / "code_01"
    settings = agent_settings(workspace)
    assert "trustedWorkspaces" in settings
    assert settings["trustedWorkspaces"] == [WORKSPACE, str(workspace.resolve())]


def test_cloud_sandbox_launch_fallback_mode(tmp_path):
    # When CLOUD_SANDBOX is absent (fallback to container isolation)
    config = make_test_config("google")
    from dataclasses import asdict

    from urithiru.runtime.files import write_json

    dataset = Dataset(files=[], metadata="", hashes={})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_json(run_dir / "run_config.json", {"config": asdict(config), "dataset": asdict(dataset)})

    cloud = MagicMock()
    stop = Event()

    with patch("pathlib.Path.exists", return_value=False):
        sandbox = CloudSandbox(cloud, run_dir, stop)
        assert sandbox.isolated is False

        goal = Goal(id="search_node_000001", stage="search", prompt="Search literature")
        workspace = run_dir / "sandbox_artifacts" / goal.id
        workspace.mkdir(parents=True)

        cmd = sandbox.launch(goal, workspace)

    assert cmd[0] == "/bin/bash"
    assert cmd[1] == "-lc"
    script = cmd[2]
    assert f"PATH={ANALYSIS_BIN}:$PATH" in script
    assert "AGY_ADC_AUTH=1" in script
    assert f"GOOGLE_CLOUD_PROJECT='{config.options.project}'" in script
    assert f"GOOGLE_CLOUD_LOCATION={AGENT_LOCATION}" in script
    assert f"cd '{workspace.resolve()}'" in script
    assert f"exec '{CLOUD_AGENT}'" in script
    assert "'--print-timeout' '8m'" in script  # search_minutes is 8


def test_cloud_sandbox_launch_isolated_mode(tmp_path):
    # When CLOUD_SANDBOX is present
    config = make_test_config("google")
    from dataclasses import asdict

    from urithiru.runtime.files import write_json

    dataset = Dataset(files=[], metadata="", hashes={})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_json(run_dir / "run_config.json", {"config": asdict(config), "dataset": asdict(dataset)})

    cloud = MagicMock()
    stop = Event()

    with patch("pathlib.Path.exists", return_value=True):
        sandbox = CloudSandbox(cloud, run_dir, stop)
        assert sandbox.isolated is True

        goal = Goal(id="code_node_000001", stage="code", prompt="Run experiment")
        workspace = run_dir / "sandbox_artifacts" / goal.id
        workspace.mkdir(parents=True)

        cmd = sandbox.launch(goal, workspace)

    assert cmd[0] == CLOUD_SANDBOX
    assert cmd[1] == "do"
    assert "--allow-egress" in cmd
    assert "--write" in cmd
    assert f"type=bind,source={workspace.resolve()},destination={WORKSPACE}" in cmd
    assert "--mount" in cmd
    assert "--" in cmd
    script = cmd[-1]
    assert f"export HOME={AGENT_HOME}" in script
    assert f"cd {WORKSPACE} && exec '{CLOUD_AGENT}'" in script
