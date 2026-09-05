import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from re import compile as regex

from google.api_core.exceptions import NotFound
from google.cloud import storage

from urithiru.core.models import Belief
from urithiru.runtime.config import GoogleConfig

RUN_ID = regex(r"[0-9a-f]{32}\Z")
PAGE_FILES = ("run.json", "mcts_state.json", "events.jsonl")
CHECKPOINT = "mcts_state.json"
EVENT_LOG = "events.jsonl"
RUN_CONFIG = "run_config.json"
STATUS = "status.json"
LABEL = "label.txt"
LABEL_LIMIT = 200
LISTING_WORKERS = 16
STAGES = ("prior", "literature", "experiment", "external")
TIMEOUT = 30


def summarize(checkpoint: dict) -> dict:
    return {
        "status": checkpoint["status"],
        "completed": len(checkpoint["completed"]),
        "requested": checkpoint["steps"],
        "error": checkpoint["error"],
        "updated_at": checkpoint["updated_at"],
        "highlight": highlight(checkpoint),
    }


def highlight(checkpoint: dict) -> dict | None:
    best, distance = None, 0.0
    for node in checkpoint.get("nodes", []):
        evaluation = node.get("evaluation")
        external = (evaluation or {}).get("external") or {}
        if not evaluation or not external.get("category_counts"):
            continue
        beliefs = {stage: stage_belief(evaluation, stage) for stage in STAGES}
        if beliefs["experiment"] is None or beliefs["external"] is None:
            continue
        moved = abs(beliefs["experiment"] - beliefs["external"])
        if moved > distance:
            best, distance = {"node": node["id"], "claim": node["claim"], **beliefs}, moved
    return best


def stage_belief(evaluation: dict, stage: str) -> float | None:
    recorded = evaluation.get(stage)
    if not isinstance(recorded, dict):
        return None
    counts = recorded.get("category_counts") or recorded.get("counts")
    return Belief(counts, "").prob_true if counts else None


SUMMARY_FIELDS = frozenset(
    summarize({"status": "", "completed": [], "steps": 0, "error": None, "updated_at": "", "nodes": []})
)


def web_config(record: dict) -> dict:
    return {
        "dataset": record["dataset"],
        "steps": record["steps"],
        "seed": record["seed"],
        "models": record["config"]["models"],
        "budget": record["config"]["budget"],
    }


def strip_events(text: str) -> str:
    records = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        record.pop("run", None)
        records.append(record)
    return "".join(f"{json.dumps(record, ensure_ascii=False)}\n" for record in records)


def decode(text: str) -> dict | None:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def download(blob) -> str:
    if blob is None:
        return ""
    try:
        return blob.download_as_text(timeout=TIMEOUT)
    except NotFound:
        return ""


def read(blob) -> dict | None:
    return decode(download(blob))


def run_id(identifier: str) -> str:
    if not RUN_ID.match(identifier):
        raise ValueError(f"Not a run id: {identifier}")
    return identifier


class Bucket:
    def __init__(self, options: GoogleConfig):
        self.storage = storage.Client(project=options.project)
        self.bucket = self.storage.bucket(options.bucket)
        self.root = f"{options.prefix.strip('/')}/"

    def close(self) -> None:
        self.storage.close()

    def __enter__(self) -> "Bucket":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()

    def listing(self) -> dict[str, dict]:
        runs: dict[str, dict] = {}
        blobs = self.storage.list_blobs(
            self.bucket, prefix=self.root, match_glob=f"{self.root}*/*", timeout=TIMEOUT
        )
        for blob in blobs:
            identifier, _, name = blob.name[len(self.root) :].partition("/")
            if RUN_ID.match(identifier) and name:
                runs.setdefault(identifier, {})[name] = blob
        return runs

    def blob(self, identifier: str, name: str):
        return self.bucket.blob(f"{self.root}{run_id(identifier)}/{name}")

    def text(self, identifier: str, name: str) -> str:
        try:
            return self.blob(identifier, name).download_as_text(timeout=TIMEOUT)
        except NotFound:
            return ""

    def json(self, identifier: str, name: str) -> dict | None:
        return decode(self.text(identifier, name))

    def entry(self, identifier: str, contents: dict) -> dict | None:
        record = read(contents.get(RUN_CONFIG))
        if record is None:
            return None
        entry = {
            "id": identifier,
            "status": "queued",
            "updated_at": "",
            "dataset": record["dataset"]["files"],
            "requested": record["steps"],
            "completed": 0,
            "error": None,
        }
        started = contents[RUN_CONFIG].time_created
        if started is not None:
            entry["started_at"] = started.isoformat()
        entry |= self.progress(identifier, contents)
        if LABEL in contents:
            entry["title"] = download(contents[LABEL]).strip()[:LABEL_LIMIT]
        log = contents.get(EVENT_LOG)
        if log is not None and log.updated is not None:
            entry["log_at"] = log.updated.isoformat()
        return entry

    def progress(self, identifier: str, contents: dict) -> dict:
        summary = read(contents.get(STATUS))
        if summary is not None and summary.keys() >= SUMMARY_FIELDS:
            return summary
        checkpoint = read(contents.get(CHECKPOINT))
        if checkpoint is None:
            return {}
        summary = summarize(checkpoint)
        with suppress(Exception):
            self.write_status(identifier, summary)
        return summary

    def write_status(self, identifier: str, summary: dict) -> None:
        self.blob(identifier, STATUS).upload_from_string(
            json.dumps(summary, ensure_ascii=False, indent=2),
            content_type="application/json",
            timeout=TIMEOUT,
        )


def catalog(options: GoogleConfig) -> list[dict]:
    with Bucket(options) as store:
        listing = store.listing()
        if not listing:
            return []
        with ThreadPoolExecutor(max_workers=LISTING_WORKERS) as pool:
            rows = list(pool.map(store.entry, listing, listing.values()))
    return sorted(
        (row for row in rows if row is not None),
        key=lambda row: (row.get("started_at", ""), row["id"]),
        reverse=True,
    )


def artifact(options: GoogleConfig, identifier: str, name: str) -> str:
    if name not in PAGE_FILES:
        raise ValueError(f"Not a published file: {name}")
    with Bucket(options) as store:
        if name == "run.json":
            record = store.json(identifier, RUN_CONFIG)
            if record is None:
                raise FileNotFoundError(f"No run configuration for {identifier}")
            return json.dumps(web_config(record), ensure_ascii=False, indent=2)
        if name == EVENT_LOG:
            return strip_events(store.text(identifier, EVENT_LOG))
        return store.text(identifier, CHECKPOINT)


def set_label(options: GoogleConfig, identifier: str, title: str) -> dict:
    text = title.strip()[:LABEL_LIMIT]
    with Bucket(options) as store:
        blob = store.blob(identifier, LABEL)
        if text:
            blob.upload_from_string(text, content_type="text/plain; charset=utf-8", timeout=TIMEOUT)
        else:
            with suppress(NotFound):
                blob.delete(timeout=TIMEOUT)
    return {"run": identifier, "title": text}


def save_status(bucket, prefix: str, directory: Path) -> None:
    checkpoint = directory / CHECKPOINT
    if not checkpoint.exists():
        return
    summary = summarize(json.loads(checkpoint.read_text(encoding="utf-8")))
    bucket.blob(f"{prefix}/{STATUS}").upload_from_string(
        json.dumps(summary, ensure_ascii=False, indent=2),
        content_type="application/json",
        timeout=TIMEOUT,
    )
