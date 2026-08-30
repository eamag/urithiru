"""A run, local or in a bucket. Every CLI command is one call on one of these."""

import json
import os
import shutil
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from urithiru.agents.goals import ResearchAgent
from urithiru.agents.llm import LLM
from urithiru.cloud.client import GoogleCloud, download_config
from urithiru.core.engine import UrithiruEngine
from urithiru.core.models import Dataset
from urithiru.core.report import export
from urithiru.runtime import events
from urithiru.runtime.config import Config, GoogleConfig
from urithiru.runtime.control import cancellation, run_lock
from urithiru.runtime.files import DatasetFiles, read_json, safe_path, write_json
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


POLL_SECONDS = 5
# The page is a static file: it renders the orchestrator's own checkpoint and event log
# rather than a shape assembled for it by a server. It gets `run.json` instead of the run
# configuration, because the profile names the project, bucket and service account and
# publishing a run should not publish where it ran.
WEB_FILES = ("mcts_state.json", "events.jsonl")
EVENT_LOG = "events.jsonl"
FINISHED = ("completed", "exhausted", "failed", "cancelled")


def publish_file(source: Path, target: Path) -> None:
    """Copy one file out, dropping the bucket reference the event log repeats on every line.

    `run.json` deliberately omits the project and bucket; the event log would put them
    back, in a directory served to anyone. The run's own id identifies it here, and the
    operator's own copy in the bucket keeps the full reference.
    """
    if source.name != EVENT_LOG:
        shutil.copyfile(source, target)
        return
    records = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    for record in records:
        record.pop("run", None)
    target.write_text("".join(f"{json.dumps(record, ensure_ascii=False)}\n" for record in records))


def publish_once(source: Path, destination: Path, reference: str) -> dict:
    """Copy those files under the run's own id, and describe the run in an index beside it."""
    identifier = reference.rstrip("/").rsplit("/", 1)[-1]
    destination.mkdir(parents=True, exist_ok=True)
    # The identifier is the tail of a reference the caller typed, so it is checked like
    # any other untrusted name before it becomes a directory.
    target = safe_path(destination, identifier)
    target.mkdir(parents=True, exist_ok=True)
    for name in WEB_FILES:
        if (source / name).exists():
            publish_file(source / name, target / name)
    # Ordered by when the copy was made, not by the checkpoint: a run that has not
    # reached its first checkpoint has no timestamp of its own and is the one being watched.
    entry = {
        "id": identifier,
        "status": "queued",
        "published_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "updated_at": "",
        "dataset": [],
    }
    if (source / "run_config.json").exists():
        record = read_json(source / "run_config.json")
        write_json(
            target / "run.json",
            {
                "dataset": record["dataset"],
                "steps": record["steps"],
                "seed": record["seed"],
                "models": record["config"]["models"],
                "budget": record["config"]["budget"],
            },
        )
        entry["dataset"] = record["dataset"]["files"]
    if (target / "mcts_state.json").exists():
        checkpoint = read_json(target / "mcts_state.json")
        entry |= {
            "status": checkpoint["status"],
            "completed": len(checkpoint["completed"]),
            "requested": checkpoint["steps"],
            "updated_at": checkpoint["updated_at"],
            "error": checkpoint["error"],
        }
    index = destination / "index.json"
    runs = {row["id"]: row for row in read_json(index)} if index.exists() else {}
    runs[identifier] = entry
    write_json(index, sorted(runs.values(), key=lambda row: row.get("published_at", ""), reverse=True))
    return entry


def publish_loop(refresh: Callable[[], Path], destination: Path, reference: str, watch: bool) -> dict:
    while True:
        entry = publish_once(refresh(), destination, reference)
        if not watch or entry["status"] in FINISHED:
            return entry
        time.sleep(POLL_SECONDS)


def stream_events(load: Callable[[], list[str]], follow: bool) -> Iterator[str]:
    """Every event so far, then new ones as they arrive, stopping when the run reports done."""
    seen = 0
    while True:
        lines = load()
        for line in lines[seen:]:
            yield line
            if json.loads(line).get("event") == "run_finished":
                return
        seen = len(lines)
        if not follow:
            return
        time.sleep(POLL_SECONDS)


def amend_budget(directory: Path, steps: int | None, minutes: dict[str, int]) -> tuple[dict, Config]:
    """Raise a run's budget in place, so a resume continues instead of starting over.

    Everything already evaluated is reloaded from the checkpoint, so added steps buy new
    hypotheses rather than repeats and a raised stage limit applies to what is left to do.
    The step count may only grow: lowering it would leave the checkpoint holding more
    finished work than the run admits to having asked for.
    """
    record = read_json(directory / "run_config.json")
    config = Config.from_dict(record["config"], minutes)
    if steps is not None and steps < record["steps"]:
        raise ValueError(f"This run requested {record['steps']} steps; a budget can only grow")
    amended = record | {"steps": steps or record["steps"], "config": asdict(config)}
    if amended != record:
        write_json(directory / "run_config.json", amended)
    return amended, config


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
        events.bind(self.reference, self.directory)

    def status(self) -> dict:
        return read_status(self.directory, self.reference)

    def resume(self, steps: int | None = None, minutes: dict[str, int] | None = None) -> dict:
        with run_lock(self.directory):
            (self.directory / "cancel").unlink(missing_ok=True)
            amend_budget(self.directory, steps, minutes or {})
        evaluate(self.directory, None)
        return self.status()

    def cancel(self) -> dict:
        (self.directory / "cancel").touch()
        return self.status()

    def export(self, destination: Path) -> dict:
        with run_lock(self.directory):
            export(self.directory, destination)
        return {"run": self.reference, "export": str(destination)}

    def logs(self, follow: bool) -> Iterator[str]:
        path = self.directory / "events.jsonl"
        return stream_events(lambda: path.read_text().splitlines() if path.exists() else [], follow)

    def publish(self, destination: Path, watch: bool) -> dict:
        return publish_loop(lambda: self.directory, destination, self.reference, watch)


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
            running = cloud.active(cloud.options.orchestrator_job)
            # A checkpoint saying "running" with no live execution means the job died.
            return read_status(directory, self.reference) | {
                "execution": running[0].name.rsplit("/", 1)[-1] if running else None
            }

    def resume(self, steps: int | None = None, minutes: dict[str, int] | None = None) -> dict:
        with self.open() as (cloud, directory, _config):
            record, config = amend_budget(directory, steps, minutes or {})
            # The orchestrator reads its budget from the bucket, and the execution's own
            # timeout is derived from it, so the amended file goes up before the job starts.
            cloud.upload_file(directory / "run_config.json", "run_config.json")
            return {
                "run": self.reference,
                "steps": record["steps"],
                "execution": submit(cloud, config, record["steps"]),
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

    def logs(self, follow: bool) -> Iterator[str]:
        with self.open() as (cloud, _directory, _config):
            yield from stream_events(lambda: cloud.read_text("events.jsonl").splitlines(), follow)

    def publish(self, destination: Path, watch: bool) -> dict:
        with self.open() as (cloud, directory, _config):

            def refresh() -> Path:
                for name in WEB_FILES:
                    cloud.download_optional(name, directory)
                return directory

            cloud.download_optional("run_config.json", directory)

            return publish_loop(refresh, destination, self.reference, watch)

    def orchestrate(self) -> dict:
        if "CLOUD_RUN_EXECUTION" not in os.environ:
            raise RuntimeError("Orchestrator must execute inside Cloud Run")
        with self.open() as (cloud, directory, _config):
            cloud.download_inputs(directory)
            cloud.load_checkpoint(directory)
            events.bind(self.reference, directory, cloud.mirror_events)
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
    events.bind(str(directory), directory)
    print(f"run={directory}", flush=True)
    evaluate(directory, None)
    return read_status(directory, str(directory))
