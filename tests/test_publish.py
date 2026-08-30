"""Tests for what publishing a run does and does not put in a public directory."""

import json

from urithiru.runtime.files import read_json, write_json
from urithiru.runtime.runs import publish_once

REFERENCE = "gs://a-private-bucket-604410934339/urithiru/2f0c1d"


def stage_run(directory, status: str = "completed") -> None:
    """The three files a real run has by the time anything is published."""
    directory.mkdir(parents=True, exist_ok=True)
    write_json(
        directory / "mcts_state.json",
        {
            "steps": 3,
            "seed": 7,
            "status": status,
            "error": None,
            "completed": ["node_000001"],
            "pending": [],
            "updated_at": "2026-08-30T05:57:07+00:00",
        },
    )
    write_json(
        directory / "run_config.json",
        {
            "steps": 3,
            "seed": 7,
            "dataset": {"files": ["inputs/000_data.csv"], "metadata": "notes", "hashes": {}},
            "config": {
                "models": {"agent": "gemini-3.7-flash"},
                "budget": {"code_minutes": 10},
                "options": {"project": "a-project", "bucket": "a-private-bucket-604410934339"},
            },
        },
    )
    lines = [
        {"time": "2026-08-30T05:39:00+00:00", "run": REFERENCE, "event": "run_started", "steps": 3},
        {"time": "2026-08-30T05:57:07+00:00", "run": REFERENCE, "event": "run_finished", "status": status},
    ]
    (directory / "events.jsonl").write_text("".join(f"{json.dumps(line)}\n" for line in lines))


def test_published_artifacts_never_carry_the_bucket(tmp_path):
    """Every published byte, not just `run.json`, has to be free of the run's location."""
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    publish_once(source, destination, REFERENCE)

    published = list(destination.rglob("*"))
    assert published, "publishing wrote nothing"
    for path in (path for path in published if path.is_file()):
        assert "gs://" not in path.read_text(), f"{path.name} still names the bucket"
        assert "a-private-bucket" not in path.read_text(), f"{path.name} still names the bucket"


def test_event_log_keeps_every_line_and_field_except_the_reference(tmp_path):
    """Redaction must not become truncation: the log is the run's audit trail."""
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    publish_once(source, destination, REFERENCE)

    original = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
    published = [
        json.loads(line) for line in (destination / "2f0c1d" / "events.jsonl").read_text().splitlines()
    ]
    assert len(published) == len(original)
    for before, after in zip(original, published, strict=True):
        assert "run" not in after
        assert after == {key: value for key, value in before.items() if key != "run"}


def test_index_entry_identifies_a_run_by_id_alone(tmp_path):
    """The browser gets the id; only the operator's own machine resolves it to a bucket."""
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    entry = publish_once(source, destination, REFERENCE)

    assert entry["id"] == "2f0c1d"
    assert "run" not in entry
    index = read_json(destination / "index.json")
    assert [row["id"] for row in index] == ["2f0c1d"]
    assert all("run" not in row for row in index)


def test_checkpoint_is_copied_unchanged(tmp_path):
    """Only the event log is rewritten; the checkpoint the page renders is verbatim."""
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    publish_once(source, destination, REFERENCE)

    assert read_json(destination / "2f0c1d" / "mcts_state.json") == read_json(source / "mcts_state.json")
