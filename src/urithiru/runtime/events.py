"""One JSON line per event on stdout: readable locally, structured in Cloud Logging."""

import json
import sys
from datetime import UTC, datetime

RUN = {"run": ""}
MESSAGE_LIMIT = 160


def bind(run: str) -> None:
    RUN["run"] = run


def emit(event: str, **fields) -> None:
    record = {
        "severity": fields.pop("severity", "INFO"),
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": RUN["run"],
        "event": event,
        **fields,
    }
    # `message` is the one-line human summary; nested diagnostics stay in the structured fields.
    scalar = str | int | float | bool | None
    scalars = " ".join(f"{key}={value}" for key, value in fields.items() if isinstance(value, scalar))
    record["message"] = f"{event} {scalars}"[:MESSAGE_LIMIT]
    print(json.dumps(record, ensure_ascii=False, default=str), file=sys.stdout, flush=True)
