from pathlib import Path

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import run_v2, storage
from google.protobuf.duration_pb2 import Duration

from urithiru.cloud.catalog import save_status
from urithiru.runtime.config import GoogleConfig
from urithiru.runtime.files import file_hash, read_json, safe_path

EVENT_LOG = "events.jsonl"
CHECKPOINT_FILES = (
    "mcts_state.json",
    "candidate_audits.json",
    "artifacts/embeddings.json",
    "artifacts/dedupe_llm_decisions.json",
)
NOT_ARTIFACTS = ("run_config.json", "inputs/")


class GoogleCloud:
    def __init__(self, options: GoogleConfig, reference: str):
        self.options, self.reference = options, reference.rstrip("/")
        if not self.reference.startswith("gs://") or "/" not in self.reference.removeprefix("gs://"):
            raise ValueError(f"Expected gs://bucket/run-prefix, not {reference}")
        bucket, self.prefix = self.reference.removeprefix("gs://").split("/", 1)
        if bucket != options.bucket:
            raise ValueError(
                f"Run reference names bucket {bucket}, but the profile configures {options.bucket}"
            )
        self.storage = storage.Client(project=options.project)
        self.bucket = self.storage.bucket(bucket)
        self.jobs, self.executions = run_v2.JobsClient(), run_v2.ExecutionsClient()
        self.uploaded: dict[str, str] = {}
        self.generations: dict[str, int] = {}

    def close(self) -> None:
        self.storage.close()
        self.jobs.transport.close()
        self.executions.transport.close()

    def upload_file(self, path: Path, name: str) -> None:
        self.bucket.blob(f"{self.prefix}/{name}").upload_from_filename(str(path), timeout=60)

    def upload_inputs(self, directory: Path) -> None:
        names = ["run_config.json", *read_json(directory / "run_config.json")["dataset"]["files"]]
        for name in names:
            self.upload_file(directory / name, name)

    def download_inputs(self, directory: Path) -> None:
        self.download_file("run_config.json", directory)
        for name in read_json(directory / "run_config.json")["dataset"]["files"]:
            self.download_file(name, directory)

    def download_file(self, name: str, directory: Path) -> None:
        target = safe_path(directory, name)
        data = self.bucket.blob(f"{self.prefix}/{name}").download_as_bytes(timeout=60)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def mirror_events(self, path: Path) -> None:
        self.bucket.blob(f"{self.prefix}/{EVENT_LOG}").upload_from_filename(str(path), timeout=30)

    def download_optional(self, name: str, directory: Path) -> bool:
        try:
            self.download_file(name, directory)
        except NotFound:
            return False
        return True

    def read_text(self, name: str) -> str:
        try:
            return self.bucket.blob(f"{self.prefix}/{name}").download_as_text(timeout=60)
        except NotFound:
            return ""

    def save_checkpoint(self, directory: Path) -> None:
        for name in CHECKPOINT_FILES:
            path = directory / name
            if path.exists():
                self.upload_once(path, name)
        for path in sorted((directory / "evaluations").glob("*.json")):
            self.upload_once(path, f"evaluations/{path.name}")
        save_status(self.bucket, self.prefix, directory)

    def upload_once(self, path: Path, name: str) -> None:
        digest = file_hash(path)
        if self.uploaded.get(name) == digest:
            return
        blob = self.bucket.blob(f"{self.prefix}/{name}")
        expected = self.generations.get(name, self.generation_of(blob))
        try:
            blob.upload_from_filename(str(path), timeout=60, if_generation_match=expected)
        except PreconditionFailed:
            raise RuntimeError(
                f"{name} changed in the bucket since this process last wrote it; "
                "another orchestrator owns this run"
            ) from None
        if blob.generation is None:
            raise RuntimeError(f"Cloud Storage returned no generation for {name}")
        self.uploaded[name], self.generations[name] = digest, blob.generation

    def generation_of(self, blob) -> int:
        try:
            blob.reload(timeout=30)
        except NotFound:
            return 0
        return blob.generation

    def load_checkpoint(self, directory: Path) -> None:
        for name in (EVENT_LOG, *CHECKPOINT_FILES):
            try:
                self.download_file(name, directory)
            except NotFound:
                if name == "mcts_state.json":
                    return
        self.download_directory("evaluations", directory / "evaluations")

    def upload_directory(self, source: Path, prefix: str) -> None:
        for path in source.rglob("*"):
            relative = path.relative_to(source).as_posix()
            if (
                path.is_file()
                and not path.is_symlink()
                and not any(part.startswith(".") for part in Path(relative).parts)
                and not relative.startswith(NOT_ARTIFACTS)
            ):
                self.bucket.blob(f"{self.prefix}/{prefix}/{relative}").upload_from_filename(
                    str(path), timeout=60
                )

    def download_directory(self, prefix: str, target: Path) -> None:
        root = f"{self.prefix}/{prefix}/" if prefix else f"{self.prefix}/"
        for blob in self.storage.list_blobs(self.bucket, prefix=root, timeout=30):
            path = safe_path(target, blob.name[len(root) :])
            path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(path), timeout=60)

    def job_name(self, name: str) -> str:
        return f"projects/{self.options.project}/locations/{self.options.region}/jobs/{name}"

    def active(self, job: str) -> list:
        return [
            execution
            for execution in self.executions.list_executions(parent=self.job_name(job))
            if not execution.completion_time and self.reference in execution.template.containers[0].args
        ]

    def submit(self, job: str, arguments: list[str], seconds: int):
        request = run_v2.RunJobRequest(
            name=self.job_name(job),
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[run_v2.RunJobRequest.Overrides.ContainerOverride(args=arguments)],
                task_count=1,
                timeout=Duration(seconds=seconds),
            ),
        )
        operation = self.jobs.run_job(request=request, retry=None, timeout=60)
        if operation.metadata is None or not operation.metadata.name:
            raise RuntimeError("Cloud launch outcome is unknown; inspect Cloud Run before submitting again")
        return operation.metadata

    def cancel(self) -> None:
        for execution in self.active(self.options.orchestrator_job):
            self.executions.cancel_execution(name=execution.name, retry=None, timeout=30)


def download_config(reference: str, directory: Path) -> dict:
    if not reference.startswith("gs://") or "/" not in reference.removeprefix("gs://"):
        raise ValueError(f"Expected gs://bucket/run-prefix, not {reference}")
    bucket, prefix = reference.removeprefix("gs://").split("/", 1)
    directory.mkdir(parents=True, exist_ok=True)
    with storage.Client() as client:
        client.bucket(bucket).blob(f"{prefix.rstrip('/')}/run_config.json").download_to_filename(
            str(directory / "run_config.json"), timeout=60
        )
    return read_json(directory / "run_config.json")
