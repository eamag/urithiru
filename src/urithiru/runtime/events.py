"""One JSON line per event: stdout for Cloud Logging, events.jsonl beside the checkpoint.

The durable log is what anything outside the process reads to follow a run in progress;
the checkpoint only says where a run got to, not what it did on the way.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

SINK: dict = {"run": "", "path": None}
WRITING = Lock()
MESSAGE_LIMIT = 160


def bind(run: str, directory: Path | None = None) -> None:
    """Name the run every event belongs to, and where its durable log lives."""
    SINK["run"] = run
    SINK["path"] = None if directory is None else directory / "events.jsonl"


def emit(event: str, **fields) -> None:
    record = {
        "severity": fields.pop("severity", "INFO"),
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": SINK["run"],
        "event": event,
        **fields,
    }
    # `message` is the one-line human summary; nested diagnostics stay in the structured fields.
    scalar = str | int | float | bool | None
    scalars = " ".join(f"{key}={value}" for key, value in fields.items() if isinstance(value, scalar))
    record["message"] = f"{event} {scalars}"[:MESSAGE_LIMIT]
    line = json.dumps(record, ensure_ascii=False, default=str)
    # Agents run in parallel threads, so one whole line must land at a time.
    with WRITING:
        print(line, file=sys.stdout, flush=True)
        if SINK["path"] is not None:
            with SINK["path"].open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
