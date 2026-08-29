"""Plain JSON checkpoints, matching the original temporary-file-and-replace approach."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2, default=asdict)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
