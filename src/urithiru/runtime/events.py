"""One JSON line per event: stdout for Cloud Logging, events.jsonl beside the checkpoint.

The durable log is what anything outside the process reads to follow a run in progress;
the checkpoint only says where a run got to, not what it did on the way. A `mirror`
publishes each new line where a reader outside this machine can see it, so a stage that
takes eight minutes is still visible while it runs rather than only once it lands.
"""

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

SINK: dict = {"run": "", "path": None, "mirror": None}
WRITING = Lock()
MESSAGE_LIMIT = 160


def bind(run: str, directory: Path | None = None, mirror: Callable[[Path], None] | None = None) -> None:
    """Name the run every event belongs to, where its durable log lives, and who mirrors it."""
    SINK["run"] = run
    SINK["path"] = None if directory is None else directory / "events.jsonl"
    SINK["mirror"] = mirror


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
            publish(SINK["path"])


def publish(path: Path) -> None:
    """Mirror the log, but never let a failed upload take down the run that logged it."""
    mirror = SINK["mirror"]
    if mirror is None:
        return
    try:
        mirror(path)
    except Exception as error:  # Reporting this through emit() would recurse.
        print(f"event log mirror failed: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
