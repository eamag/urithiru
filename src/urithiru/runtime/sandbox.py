"""The two sandboxes. Both run the same agent CLI; only the isolation differs.

`Sandbox` owns the workspace lifecycle and builds the agent's arguments. A subclass
supplies `launch`: put that command inside a Docker container, or inside a Cloud Run
sandbox, and leave the agent's result files in the workspace.
"""

import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from urithiru.core.models import RESULT_FILES, Dataset, Goal
from urithiru.runtime.checkpoints import read_json, write_json
from urithiru.runtime.config import Config, DockerConfig
from urithiru.runtime.control import Cancelled
from urithiru.runtime.events import emit
from urithiru.runtime.files import DatasetFiles, safe_path

if TYPE_CHECKING:
    from urithiru.cloud.client import GoogleCloud

AGENT_PROMPT = "Read goal.txt. Write results through shell/Python in the working directory."
# Where the agent binary lives in each environment. Docker: the operator's login volume.
# Cloud Run: this project's own Dockerfile installs it there.
DOCKER_AGENT = "/root/.local/bin/agy"
CLOUD_AGENT = "/usr/local/bin/agy"
CLOUD_SANDBOX = "/usr/local/gcp/bin/sandbox"
WORKSPACE = "/workspace"
# The sandbox gets no parent environment, so the agent's home and key are mounted in.
AGENT_HOME = "/agent-home"
AGENT_SECRET = "/agent-secret"
# Headless authentication needs the key *and* this provider setting; the key alone does nothing.
AGENT_SETTINGS = {"modelProvider": "gemini", "trustedWorkspaces": [WORKSPACE]}


class Sandbox:
    """Workspace bookkeeping and the agent command, shared by every runtime."""

    def __init__(self, config: Config, dataset: Dataset, directory: Path, stop: Event):
        self.config, self.dataset, self.directory, self.stop = config, dataset, directory, stop
        self.budget = config.budget

    def workspace(self, goal: Goal) -> Path:
        return safe_path(self.directory / "sandbox_artifacts", goal.id)

    def run(self, goal: Goal) -> Path:
        workspace = self.workspace(goal)
        # A `completed` marker alone is not trusted; the stage's result file must be there too.
        if (workspace / "completed").exists() and (workspace / RESULT_FILES[goal.stage]).exists():
            return workspace
        if workspace.exists():
            workspace.rename(workspace.with_name(f"{goal.id}_previous_{uuid.uuid4().hex[:8]}"))
        workspace.mkdir(parents=True)
        if goal.stage != "external":
            DatasetFiles(self.directory).copy_to(self.dataset, workspace)
        (workspace / "goal.txt").write_text(goal.prompt)
        self.execute(goal, workspace)
        return workspace

    def agent_arguments(self, goal: Goal) -> list[str]:
        """The agent CLI invocation itself, identical in both runtimes."""
        return [
            "--print",
            AGENT_PROMPT,
            "--model",
            self.config.models.agent,
            "--effort",
            self.config.models.effort,
            "--print-timeout",
            f"{self.budget.minutes(goal.stage)}m",
            "--dangerously-skip-permissions",
        ]

    def execute(self, goal: Goal, workspace: Path) -> None:
        """Run `launch`, enforce the deadline, and require a result file on failure."""
        emit("agent_started", goal=goal.id, stage=goal.stage, minutes=self.budget.minutes(goal.stage))
        with (workspace / "agent.log").open("w") as log:
            process = subprocess.Popen(self.launch(goal, workspace), stdout=log, stderr=subprocess.STDOUT)
            try:
                self.wait(process, goal)
                if process.returncode and not (workspace / RESULT_FILES[goal.stage]).exists():
                    raise RuntimeError(
                        f"The agent exited with status {process.returncode}; see {workspace / 'agent.log'}"
                    )
            except TimeoutError:
                if not (workspace / RESULT_FILES[goal.stage]).exists():
                    raise
            finally:
                self.cleanup(goal, process, workspace)
                emit("agent_finished", goal=goal.id, returncode=process.returncode)

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        raise NotImplementedError

    def cleanup(self, goal: Goal, process, workspace: Path) -> None:
        process.wait(timeout=30)

    def wait(self, process, goal: Goal) -> None:
        deadline = time.monotonic() + self.budget.seconds(goal.stage) + self.budget.grace_seconds
        while process.poll() is None:
            if self.stop.wait(0.2):
                raise Cancelled("Execution cancelled")
            if time.monotonic() >= deadline:
                raise TimeoutError("Agent execution timed out")

    def complete(self, goal: Goal) -> None:
        (self.workspace(goal) / "completed").touch()

    def checkpoint(self) -> None:
        """Local checkpoint files need no remote upload."""


class DockerSandbox(Sandbox):
    """Local runtime: the operator's own agent image and login volume."""

    def __init__(self, config: Config, dataset: Dataset, directory: Path, stop: Event):
        if not isinstance(config.options, DockerConfig):
            raise ValueError("Docker settings required")
        super().__init__(config, dataset, directory, stop)
        self.options = config.options

    def container_name(self, goal: Goal) -> str:
        return f"urithiru_{self.directory.name}_{goal.id}"

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        for name in self.options.agent_env:
            if not os.environ[name]:
                raise ValueError(f"Empty declared credential: {name}")
        subprocess.run(self.remove(goal), capture_output=True, timeout=30, check=False)
        return [
            *["docker", "run", "--rm", "--memory=4g", "--cpus=3", "--security-opt=no-new-privileges"],
            *["--name", self.container_name(goal)],
            *["-v", f"{self.options.credential_volume}:/root"],
            *["-v", f"{workspace.resolve()}:{WORKSPACE}"],
            *[part for name in self.options.agent_env for part in ("-e", name)],
            *["-w", WORKSPACE, "--entrypoint", DOCKER_AGENT, self.options.image],
            *self.agent_arguments(goal),
        ]

    def remove(self, goal: Goal) -> list[str]:
        return ["docker", "rm", "-f", self.container_name(goal)]

    def cleanup(self, goal: Goal, process, workspace: Path) -> None:
        subprocess.run(self.remove(goal), capture_output=True, timeout=30, check=False)
        super().cleanup(goal, process, workspace)
        self.sanitize(workspace)

    def sanitize(self, workspace: Path) -> None:
        secrets = [os.environ[name].encode() for name in self.options.agent_env]
        for path in workspace.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.name == ".env"):
                path.unlink()
            elif secrets and path.is_file() and path.relative_to(workspace).parts[0] != "inputs":
                self.redact(path, secrets)

    def redact(self, path: Path, secrets: list[bytes]) -> None:
        """Only a file that actually carries a credential is rewritten."""
        data = path.read_bytes()
        if not any(secret in data for secret in secrets):
            return
        for secret in secrets:
            data = data.replace(secret, b"[REDACTED]")
        path.write_bytes(data)


class CloudSandbox(Sandbox):
    """Cloud runtime: the same agent inside a Cloud Run sandbox, in this same container.

    The sandbox gets the workspace and outbound network, but not this job's environment
    or the metadata server, so generated code cannot reach the run's service identity.
    """

    def __init__(self, cloud: "GoogleCloud", directory: Path, stop: Event):
        record = read_json(directory / "run_config.json")
        super().__init__(Config.from_dict(record["config"]), Dataset(**record["dataset"]), directory, stop)
        self.cloud = cloud
        # Kept outside the run directory so neither is ever uploaded with the artifacts.
        private = Path(tempfile.mkdtemp(prefix="urithiru-agent-"))
        self.home, self.secret = private / "home", private / "secret"
        settings = self.home / ".gemini" / "antigravity-cli"
        settings.mkdir(parents=True)
        write_json(settings / "settings.json", AGENT_SETTINGS)
        self.secret.mkdir()
        (self.secret / "key").write_text(os.environ["GEMINI_API_KEY"])
        (self.secret / "key").chmod(0o600)

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        agent = " ".join(shell_quote(part) for part in [CLOUD_AGENT, *self.agent_arguments(goal)])
        script = (
            f'export HOME={AGENT_HOME} GEMINI_API_KEY="$(cat {AGENT_SECRET}/key)"; '
            f"cd {WORKSPACE} && exec {agent}"
        )
        return [
            *[CLOUD_SANDBOX, "do", "--allow-egress", "--write"],
            *["--mount", f"type=bind,source={workspace.resolve()},destination={WORKSPACE}"],
            *["--mount", f"type=bind,source={self.home},destination={AGENT_HOME}"],
            *["--mount", f"type=bind,source={self.secret},destination={AGENT_SECRET}"],
            *["--", "/bin/bash", "-lc", script],
        ]

    def cleanup(self, goal: Goal, process, workspace: Path) -> None:
        super().cleanup(goal, process, workspace)
        self.cloud.upload_directory(workspace, f"sandbox_artifacts/{goal.id}")

    def checkpoint(self) -> None:
        self.cloud.save_checkpoint(self.directory)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"
