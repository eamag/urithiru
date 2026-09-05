import pytest

from urithiru.core.models import Dataset
from urithiru.runtime.files import DatasetFiles, file_hash, read_json, safe_path, write_json


def test_safe_path_valid(tmp_path):
    p1 = safe_path(tmp_path, "goal.txt")
    assert p1 == tmp_path / "goal.txt"

    p2 = safe_path(tmp_path, "sub/dir/result.json")
    assert p2 == tmp_path / "sub" / "dir" / "result.json"


def test_safe_path_traversal_rejections(tmp_path):
    with pytest.raises(ValueError, match="Unsafe relative path"):
        safe_path(tmp_path, "/etc/passwd")

    with pytest.raises(ValueError, match="Unsafe relative path"):
        safe_path(tmp_path, "../outside.txt")

    with pytest.raises(ValueError, match="Unsafe relative path"):
        safe_path(tmp_path, "sub/../../outside.txt")

    with pytest.raises(ValueError, match="Unsafe relative path"):
        safe_path(tmp_path, r"sub\file.txt")


def test_safe_path_symlink_escape(tmp_path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("classified")

    inside_dir = tmp_path / "workspace"
    inside_dir.mkdir()

    symlink_path = inside_dir / "symlink_escape"
    symlink_path.symlink_to(secret_file)

    with pytest.raises(ValueError, match="Path escapes workspace"):
        safe_path(inside_dir, "symlink_escape")


def test_atomic_write_json(tmp_path):
    target = tmp_path / "state.json"
    data = {"key": "value", "numbers": [1, 2, 3]}

    write_json(target, data)
    assert target.exists()
    assert not (tmp_path / "state.json.tmp").exists()
    assert read_json(target) == data


def test_file_hash(tmp_path):
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("hello world\n")
    file2.write_text("hello world\n")

    h1 = file_hash(file1)
    h2 = file_hash(file2)
    assert h1 == h2
    assert len(h1) == 64


def test_dataset_files_stage_and_validate(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_file = data_dir / "measurements.csv"
    csv_file.write_text("col1,col2\n1,2\n")

    meta_file = data_dir / "notes.md"
    meta_file.write_text("Context notes.")

    dataset_manager = DatasetFiles(tmp_path / "run")
    dataset = dataset_manager.stage(data=[csv_file], metadata=[meta_file], max_bytes=1024 * 1024)

    assert isinstance(dataset, Dataset)
    assert len(dataset.files) == 1
    assert "000_measurements.csv" in dataset.files[0]
    assert dataset.hashes[dataset.files[0]] == file_hash(csv_file)
    assert "Context notes." in dataset.metadata

    workspace = tmp_path / "workspace"
    dataset_manager.copy_to(dataset, workspace)
    assert (workspace / dataset.files[0]).exists()
    assert (workspace / dataset.files[0]).read_text() == "col1,col2\n1,2\n"


def test_dataset_validation_errors(tmp_path):
    dataset_manager = DatasetFiles(tmp_path / "run")

    with pytest.raises(ValueError, match="At least one data file is required"):
        dataset_manager.validate(data=[], metadata=[], max_bytes=1024)

    bad_file = tmp_path / "data.png"
    bad_file.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError, match="Data files must be"):
        dataset_manager.validate(data=[bad_file], metadata=[], max_bytes=1024)

    large_csv = tmp_path / "large.csv"
    large_csv.write_text("a" * 500)
    with pytest.raises(ValueError, match="Input bundle is"):
        dataset_manager.validate(data=[large_csv], metadata=[], max_bytes=100)
