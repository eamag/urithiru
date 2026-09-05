import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from urithiru.core.models import DATA_STAGES, RESULT_FILES, Dataset, Goal
from urithiru.runtime.config import Config, DockerConfig, GoogleConfig
from urithiru.runtime.control import Cancelled
from urithiru.runtime.events import emit
from urithiru.runtime.files import DatasetFiles, read_json, safe_path, write_json

if TYPE_CHECKING:
    from urithiru.cloud.client import GoogleCloud


def agent_prompt(root: str) -> str:
    return (
        f"Read {root}/goal.txt. Write every result file goal.txt names into {root}, by "
        f"absolute path, through shell or Python. Nothing outside {root} is read back."
    )


DOCKER_AGENT = "/usr/local/bin/agy"
CLOUD_AGENT = "/usr/local/bin/agy"
CLOUD_SANDBOX = "/usr/local/gcp/bin/sandbox"
ANALYSIS_BIN = "/opt/analysis/bin"
WORKSPACE = "/workspace"
AGENT_HOME = "/agent-home"
AGENT_LOCATION = "global"


def agent_settings(workspace: Path) -> dict:
    return {"trustedWorkspaces": [WORKSPACE, str(workspace.resolve())]}


class Sandbox:
    def __init__(self, config: Config, dataset: Dataset, directory: Path, stop: Event):
        self.config, self.dataset, self.directory, self.stop = config, dataset, directory, stop
        self.budget = config.budget

    def workspace(self, goal: Goal) -> Path:
        return safe_path(self.directory / "sandbox_artifacts", goal.id)

    def run(self, goal: Goal) -> Path:
        workspace = self.workspace(goal)
        if (workspace / "completed").exists() and (workspace / RESULT_FILES[goal.stage]).exists():
            return workspace
        if workspace.exists():
            workspace.rename(workspace.with_name(f"{goal.id}_previous_{uuid.uuid4().hex[:8]}"))
            self.reset(goal)
        workspace.mkdir(parents=True)
        if goal.stage in DATA_STAGES:
            DatasetFiles(self.directory).copy_to(self.dataset, workspace)
        (workspace / "goal.txt").write_text(goal.prompt)
        self.execute(goal, workspace)
        return workspace

    def agent_arguments(self, goal: Goal, root: str) -> list[str]:
        return [
            "--print",
            agent_prompt(root),
            "--model",
            self.config.models.agent,
            "--effort",
            self.config.models.effort,
            "--print-timeout",
            f"{self.budget.minutes(goal.stage)}m",
            "--dangerously-skip-permissions",
        ]

    def execute(self, goal: Goal, workspace: Path) -> None:
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
                emit("agent_finished", goal=goal.id, stage=goal.stage, returncode=process.returncode)

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        raise NotImplementedError

    def reset(self, goal: Goal) -> None:
        pass

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
        pass


class DockerSandbox(Sandbox):
    def __init__(self, config: Config, dataset: Dataset, directory: Path, stop: Event):
        if not isinstance(config.options, DockerConfig):
            raise ValueError("Docker settings required")
        super().__init__(config, dataset, directory, stop)
        self.options = config.options

    def container_name(self, goal: Goal) -> str:
        return f"urithiru_{self.directory.name}_{goal.id}"

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        subprocess.run(self.remove(goal), capture_output=True, timeout=30, check=False)
        return [
            *["docker", "run", "--rm", "--memory=4g", "--cpus=3", "--security-opt=no-new-privileges"],
            *["--user", "root"],
            *["--name", self.container_name(goal)],
            *["-v", f"{self.options.credential_volume}:/root"],
            *["-v", f"{workspace.resolve()}:{WORKSPACE}"],
            *["-w", WORKSPACE, "--entrypoint", DOCKER_AGENT, self.options.image],
            *self.agent_arguments(goal, WORKSPACE),
        ]

    def remove(self, goal: Goal) -> list[str]:
        return ["docker", "rm", "-f", self.container_name(goal)]

    def cleanup(self, goal: Goal, process, workspace: Path) -> None:
        subprocess.run(self.remove(goal), capture_output=True, timeout=30, check=False)
        super().cleanup(goal, process, workspace)
        for path in workspace.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.name == ".env"):
                path.unlink()


class CloudSandbox(Sandbox):
    def __init__(self, cloud: "GoogleCloud", directory: Path, stop: Event):
        record = read_json(directory / "run_config.json")
        config = Config.from_dict(record["config"])
        if not isinstance(config.options, GoogleConfig):
            raise ValueError("Google settings required")
        super().__init__(config, Dataset(**record["dataset"]), directory, stop)
        self.cloud = cloud
        self.project = config.options.project
        self.homes = Path(tempfile.mkdtemp(prefix="urithiru-agent-"))
        self.isolated = Path(CLOUD_SANDBOX).exists()
        if not self.isolated:
            emit("sandbox_unavailable", severity="WARNING", path=CLOUD_SANDBOX, isolation="container")

    def reset(self, goal: Goal) -> None:
        shutil.rmtree(self.homes / goal.id, ignore_errors=True)

    def agent_home(self, goal: Goal, workspace: Path) -> Path:
        home = self.homes / goal.id
        settings = home / ".gemini" / "antigravity-cli"
        settings.mkdir(parents=True, exist_ok=True)
        write_json(settings / "settings.json", agent_settings(workspace))
        return home

    def credentials(self, home: str) -> str:
        return (
            f"export HOME={home} PATH={ANALYSIS_BIN}:$PATH AGY_ADC_AUTH=1 "
            f"GOOGLE_CLOUD_PROJECT={shell_quote(self.project)} "
            f"GOOGLE_CLOUD_LOCATION={AGENT_LOCATION}; "
        )

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        home = self.agent_home(goal, workspace)
        root = WORKSPACE if self.isolated else str(workspace.resolve())
        agent = " ".join(shell_quote(part) for part in [CLOUD_AGENT, *self.agent_arguments(goal, root)])
        if not self.isolated:
            script = self.credentials(shell_quote(str(home))) + f"cd {shell_quote(root)} && exec {agent}"
            return ["/bin/bash", "-lc", script]
        script = self.credentials(AGENT_HOME) + f"cd {WORKSPACE} && exec {agent}"
        return [
            *[CLOUD_SANDBOX, "do", "--allow-egress", "--write"],
            *["--mount", f"type=bind,source={workspace.resolve()},destination={WORKSPACE}"],
            *["--mount", f"type=bind,source={home},destination={AGENT_HOME}"],
            *["--", "/bin/bash", "-lc", script],
        ]

    def cleanup(self, goal: Goal, process, workspace: Path) -> None:
        super().cleanup(goal, process, workspace)
        self.cloud.upload_directory(workspace, f"sandbox_artifacts/{goal.id}")

    def checkpoint(self) -> None:
        self.cloud.save_checkpoint(self.directory)


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"
