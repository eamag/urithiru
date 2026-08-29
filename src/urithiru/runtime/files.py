"""Original data and generated artifacts remain ordinary files."""

import hashlib
import shutil
from pathlib import Path, PurePosixPath

from urithiru.core.models import Dataset

DATA_SUFFIXES = {".csv", ".tsv", ".parquet", ".xlsx", ".xls"}


def safe_path(directory: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError(f"Unsafe relative path: {name}")
    path = directory / name
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError(f"Path escapes workspace: {name}")
    return path


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class DatasetFiles:
    def __init__(self, directory: Path):
        self.directory = directory

    def stage(self, data: list[Path], metadata: list[Path], max_bytes: int) -> Dataset:
        self.validate(data, metadata, max_bytes)
        filenames = []
        for index, source in enumerate(data):
            name = f"inputs/{index:03d}_{source.name}"
            target = safe_path(self.directory, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            filenames.append(name)
        text = "\n\n".join(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}" for path in metadata)
        return Dataset(filenames, text, {name: file_hash(self.directory / name) for name in filenames})

    def validate(self, data: list[Path], metadata: list[Path], max_bytes: int) -> None:
        if not data:
            raise ValueError(f"At least one data file is required ({', '.join(sorted(DATA_SUFFIXES))})")
        for path in [*data, *metadata]:
            if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Expected a nonempty regular file: {path}")
        rejected = [str(path) for path in data if path.suffix.lower() not in DATA_SUFFIXES]
        if rejected:
            raise ValueError(f"Data files must be {', '.join(sorted(DATA_SUFFIXES))}: {', '.join(rejected)}")
        total = sum(path.stat().st_size for path in [*data, *metadata])
        if total > max_bytes:
            raise ValueError(
                f"Input bundle is {total // 1048576} MiB; the limit is {max_bytes // 1048576} MiB"
            )
        for path in metadata:
            path.read_text(encoding="utf-8")

    def copy_to(self, dataset: Dataset, workspace: Path) -> None:
        for name in dataset.files:
            source = safe_path(self.directory, name)
            if file_hash(source) != dataset.hashes[name]:
                raise ValueError(f"Input changed: {name}")
            target = safe_path(workspace, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
