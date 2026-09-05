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
    scalar = str | int | float | bool | None
    scalars = " ".join(f"{key}={value}" for key, value in fields.items() if isinstance(value, scalar))
    record["message"] = f"{event} {scalars}"[:MESSAGE_LIMIT]
    line = json.dumps(record, ensure_ascii=False, default=str)
    with WRITING:
        print(line, file=sys.stdout, flush=True)
        if SINK["path"] is not None:
            with SINK["path"].open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
            publish(SINK["path"])


def publish(path: Path) -> None:
    mirror = SINK["mirror"]
    if mirror is None:
        return
    try:
        mirror(path)
    except Exception as error:
        print(f"event log mirror failed: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
