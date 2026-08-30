"""The two sandboxes. Both run the same agent CLI; only the isolation differs.

`Sandbox` owns the workspace lifecycle and builds the agent's arguments. A subclass
supplies `launch`: put that command inside a Docker container, or inside a Cloud Run
sandbox, and leave the agent's result files in the workspace.
"""

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

AGENT_PROMPT = (
    "Read goal.txt. Write results through shell/Python into the directory you start in, "
    "at the relative path goal.txt names. Do not write results anywhere else: only that "
    "directory is read back."
)
# Where the agent binary lives in each environment. Docker: the operator's login volume.
# Cloud Run: this project's own Dockerfile installs it there.
DOCKER_AGENT = "/root/.local/bin/agy"
CLOUD_AGENT = "/usr/local/bin/agy"
CLOUD_SANDBOX = "/usr/local/gcp/bin/sandbox"
# The agents' preinstalled scientific Python, built by this project's Dockerfile from
# deploy/analysis-requirements.txt. A sandbox inherits no environment, so this has to go
# on PATH explicitly or the agent gets the bare system interpreter with no pandas.
ANALYSIS_BIN = "/opt/analysis/bin"
WORKSPACE = "/workspace"
# The sandbox gets no parent environment, so the agent's home is mounted in.
AGENT_HOME = "/agent-home"
# `AGY_ADC_AUTH` makes the agent authenticate with Application Default Credentials -- in
# Cloud Run, the job's own service account -- instead of a Gemini API key. That bills the
# agent to Cloud Billing through Agent Platform rather than to AI Studio prepaid credits,
# and means no key is stored, mounted, or reachable by generated code. The agent's models
# are only served from `global`; a regional endpoint rejects them.
AGENT_LOCATION = "global"


def agent_settings(workspace: Path) -> dict:
    """No `modelProvider`: that setting forces the API-key route and defeats ADC.

    Only this goal's own workspace is trusted. Trusting the directory that holds every
    goal's workspace would let the literature agent read the experiment agent's result
    on the fallback path, where there is no bind mount and these paths are the guard.
    A workspace is `/workspace` when the sandbox bind-mounts it and its real path when
    the sandbox is absent, so both spellings of the one workspace are listed.
    """
    return {"trustedWorkspaces": [WORKSPACE, str(workspace.resolve())]}


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
            self.reset(goal)
        workspace.mkdir(parents=True)
        # The literature and external agents are never given the seed files. That absence,
        # not a prompt or a timestamp check, is what makes their beliefs independent of it.
        if goal.stage in DATA_STAGES:
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
                emit("agent_finished", goal=goal.id, stage=goal.stage, returncode=process.returncode)

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        raise NotImplementedError

    def reset(self, goal: Goal) -> None:
        """Discard anything the failed attempt left outside the workspace."""

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
        subprocess.run(self.remove(goal), capture_output=True, timeout=30, check=False)
        return [
            *["docker", "run", "--rm", "--memory=4g", "--cpus=3", "--security-opt=no-new-privileges"],
            *["--name", self.container_name(goal)],
            *["-v", f"{self.options.credential_volume}:/root"],
            *["-v", f"{workspace.resolve()}:{WORKSPACE}"],
            *["-w", WORKSPACE, "--entrypoint", DOCKER_AGENT, self.options.image],
            *self.agent_arguments(goal),
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
    """Cloud runtime: the same agent inside a Cloud Run sandbox, in this same container.

    The sandbox gets the workspace and outbound network, but not this job's environment
    or the metadata server, so generated code cannot reach the run's service identity.
    Cloud Run sandboxes are a Preview feature; where the binary is absent the agent runs
    directly in this container instead, which completes the run with weaker isolation.
    """

    def __init__(self, cloud: "GoogleCloud", directory: Path, stop: Event):
        record = read_json(directory / "run_config.json")
        config = Config.from_dict(record["config"])
        if not isinstance(config.options, GoogleConfig):
            raise ValueError("Google settings required")
        super().__init__(config, Dataset(**record["dataset"]), directory, stop)
        self.cloud = cloud
        self.project = config.options.project
        # Kept outside the run directory so they are never uploaded with the artifacts.
        self.homes = Path(tempfile.mkdtemp(prefix="urithiru-agent-"))
        self.isolated = Path(CLOUD_SANDBOX).exists()
        if not self.isolated:
            emit("sandbox_unavailable", severity="WARNING", path=CLOUD_SANDBOX, isolation="container")

    def reset(self, goal: Goal) -> None:
        """A retry gets a new home, because the agent resumes whatever it finds in the old one.

        The failed attempt leaves its session state, and sometimes the result file it put in
        the wrong place, under this goal's home. Reusing that home makes the agent believe the
        work is already done: it returns in seconds, writes nothing to the workspace, and the
        retry fails exactly as the first attempt did instead of being a second chance.
        """
        shutil.rmtree(self.homes / goal.id, ignore_errors=True)

    def agent_home(self, goal: Goal, workspace: Path) -> Path:
        """One home per goal, because the agent keeps a scratch directory inside its home.

        Sharing one home hands each agent the previous agent's scratch files, which is a
        second route to the data that copying no dataset into the workspace does not close.
        """
        home = self.homes / goal.id
        settings = home / ".gemini" / "antigravity-cli"
        settings.mkdir(parents=True, exist_ok=True)
        write_json(settings / "settings.json", agent_settings(workspace))
        return home

    def credentials(self, home: str) -> str:
        """The agent's whole environment: a private home, the analysis Python, and ADC."""
        return (
            f"export HOME={home} PATH={ANALYSIS_BIN}:$PATH AGY_ADC_AUTH=1 "
            f"GOOGLE_CLOUD_PROJECT={shell_quote(self.project)} "
            f"GOOGLE_CLOUD_LOCATION={AGENT_LOCATION}; "
        )

    def launch(self, goal: Goal, workspace: Path) -> list[str]:
        agent = " ".join(shell_quote(part) for part in [CLOUD_AGENT, *self.agent_arguments(goal)])
        home = self.agent_home(goal, workspace)
        if not self.isolated:
            # No bind mounts, so the agent uses the real paths and reaches the metadata
            # server for its Application Default Credentials.
            script = (
                self.credentials(shell_quote(str(home)))
                + f"cd {shell_quote(str(workspace.resolve()))} && exec {agent}"
            )
            return ["/bin/bash", "-lc", script]
        # A sandbox withholds the metadata server, which is also where ADC comes from, so
        # this branch cannot authenticate until Cloud Run sandboxes expose a credential
        # path. See docs/google.md; the run falls back to the branch above meanwhile.
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
