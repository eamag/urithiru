"""A run, local or in a bucket. Every CLI command is one call on one of these."""

import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from urithiru.agents.goals import ResearchAgent
from urithiru.agents.llm import LLM
from urithiru.cloud.client import GoogleCloud, download_config
from urithiru.core.engine import UrithiruEngine
from urithiru.core.models import Dataset
from urithiru.core.report import export
from urithiru.runtime import events
from urithiru.runtime.checkpoints import read_json, write_json
from urithiru.runtime.config import Config, GoogleConfig
from urithiru.runtime.control import cancellation, run_lock
from urithiru.runtime.files import DatasetFiles
from urithiru.runtime.sandbox import CloudSandbox, DockerSandbox


def read_status(directory: Path, reference: str) -> dict:
    path = directory / "mcts_state.json"
    if not path.exists():
        raise FileNotFoundError(f"No run checkpoint at {reference}; check the run identifier")
    checkpoint = read_json(path)
    return {
        "run": reference,
        "status": checkpoint["status"],
        "completed": len(checkpoint["completed"]),
        "requested": checkpoint["steps"],
        "error": checkpoint["error"],
        "updated_at": checkpoint["updated_at"],
        "cancellation_requested": (directory / "cancel").exists(),
    }


def evaluate(directory: Path, cloud: GoogleCloud | None) -> None:
    """The one place a discovery loop is driven, whether locally or inside Cloud Run."""
    record = read_json(directory / "run_config.json")
    config = Config.from_dict(record["config"])
    with run_lock(directory), cancellation(directory) as stop:
        model = LLM(config, record["seed"])
        sandbox = (
            CloudSandbox(cloud, directory, stop)
            if cloud is not None
            else DockerSandbox(config, Dataset(**record["dataset"]), directory, stop)
        )
        try:
            UrithiruEngine(config, ResearchAgent(sandbox), model, record["steps"], record["seed"]).run()
        finally:
            model.close()


class LocalRun:
    """A run directory on this machine; the process that starts it also drives it."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        if not self.directory.is_dir():
            raise FileNotFoundError(f"No run directory at {self.directory}")
        self.reference = str(self.directory)
        events.bind(self.reference)

    def status(self) -> dict:
        return read_status(self.directory, self.reference)

    def resume(self) -> dict:
        with run_lock(self.directory):
            (self.directory / "cancel").unlink(missing_ok=True)
        evaluate(self.directory, None)
        return self.status()

    def cancel(self) -> dict:
        (self.directory / "cancel").touch()
        return self.status()

    def export(self, destination: Path) -> dict:
        with run_lock(self.directory):
            export(self.directory, destination)
        return {"run": self.reference, "export": str(destination)}


class CloudRun:
    """A run in a bucket, driven by a Cloud Run orchestrator; these commands only steer it."""

    def __init__(self, reference: str):
        self.reference = reference
        events.bind(reference)

    @contextmanager
    def open(self):
        with tempfile.TemporaryDirectory(prefix="urithiru-cloud-") as temporary:
            directory = Path(temporary)
            config = Config.from_dict(download_config(self.reference, directory)["config"])
            if not isinstance(config.options, GoogleConfig):
                raise ValueError("Run does not use Google Cloud")
            cloud = GoogleCloud(config.options, self.reference)
            try:
                yield cloud, directory, config
            finally:
                cloud.close()

    def status(self) -> dict:
        with self.open() as (cloud, directory, _config):
            cloud.load_checkpoint(directory)
            return read_status(directory, self.reference)

    def resume(self) -> dict:
        with self.open() as (cloud, directory, config):
            return {
                "run": self.reference,
                "execution": submit(cloud, config, read_json(directory / "run_config.json")["steps"]),
            }

    def cancel(self) -> dict:
        with self.open() as (cloud, _directory, _config):
            cloud.cancel()
            return {"run": self.reference, "cancellation_requested": True}

    def export(self, destination: Path) -> dict:
        with self.open() as (cloud, directory, _config):
            if cloud.active(cloud.options.orchestrator_job):
                raise RuntimeError("Wait for or cancel the run before exporting")
            cloud.download_directory("", directory)
            export(directory, destination)
            return {"run": self.reference, "export": str(destination)}

    def orchestrate(self) -> dict:
        if "CLOUD_RUN_EXECUTION" not in os.environ:
            raise RuntimeError("Orchestrator must execute inside Cloud Run")
        with self.open() as (cloud, directory, _config):
            cloud.download_inputs(directory)
            cloud.load_checkpoint(directory)
            evaluate(directory, cloud)
            return read_status(directory, self.reference)


def open_run(reference: str) -> LocalRun | CloudRun:
    """`gs://bucket/prefix/run-id` is a cloud run; anything else is a local directory."""
    return CloudRun(reference) if reference.startswith("gs://") else LocalRun(Path(reference))


def submit(cloud: GoogleCloud, config: Config, steps: int) -> str:
    if cloud.active(cloud.options.orchestrator_job):
        raise RuntimeError("An orchestrator is already running for this run")
    execution = cloud.submit(
        cloud.options.orchestrator_job,
        ["orchestrate", "--run", cloud.reference],
        config.budget.orchestrator_seconds(steps),
    )
    return execution.name


def start(
    config: Config, data: list[Path], metadata: list[Path], steps: int, seed: int, output: Path
) -> dict:
    """Stage the inputs, then either drive the run here or hand it to Cloud Run."""
    directory = (output / uuid.uuid4().hex).resolve()
    dataset = DatasetFiles(directory).stage(data, metadata, config.budget.input_bytes)
    write_json(
        directory / "run_config.json",
        {"config": asdict(config), "dataset": asdict(dataset), "steps": steps, "seed": seed},
    )
    if isinstance(config.options, GoogleConfig):
        reference = f"gs://{config.options.bucket}/{config.options.prefix}/{directory.name}"
        events.bind(reference)
        cloud = GoogleCloud(config.options, reference)
        try:
            cloud.upload_inputs(directory)
            return {"run": reference, "execution": submit(cloud, config, steps)}
        finally:
            cloud.close()
    events.bind(str(directory))
    print(f"run={directory}", flush=True)
    evaluate(directory, None)
    return read_status(directory, str(directory))
