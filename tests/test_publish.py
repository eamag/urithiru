import json

import pytest

from urithiru.runtime.files import read_json, write_json
from urithiru.runtime.runs import publish_once, unpublish

REFERENCE = "gs://a-private-bucket-000000000000/urithiru/2f0c1d"


def stage_run(directory, status: str = "completed") -> None:
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
                "options": {"project": "a-project", "bucket": "a-private-bucket-000000000000"},
            },
        },
    )
    lines = [
        {"time": "2026-08-30T05:39:00+00:00", "run": REFERENCE, "event": "run_started", "steps": 3},
        {"time": "2026-08-30T05:57:07+00:00", "run": REFERENCE, "event": "run_finished", "status": status},
    ]
    (directory / "events.jsonl").write_text("".join(f"{json.dumps(line)}\n" for line in lines))


def test_published_artifacts_never_carry_the_bucket(tmp_path):
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    publish_once(source, destination, REFERENCE)

    published = list(destination.rglob("*"))
    assert published, "publishing wrote nothing"
    for path in (path for path in published if path.is_file()):
        assert "gs://" not in path.read_text(), f"{path.name} still names the bucket"
        assert "a-private-bucket" not in path.read_text(), f"{path.name} still names the bucket"


def test_event_log_keeps_every_line_and_field_except_the_reference(tmp_path):
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
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    entry = publish_once(source, destination, REFERENCE)

    assert entry["id"] == "2f0c1d"
    assert "run" not in entry
    index = read_json(destination / "index.json")
    assert [row["id"] for row in index] == ["2f0c1d"]
    assert all("run" not in row for row in index)


def test_checkpoint_is_copied_unchanged(tmp_path):
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)

    publish_once(source, destination, REFERENCE)

    assert read_json(destination / "2f0c1d" / "mcts_state.json") == read_json(source / "mcts_state.json")


def test_unpublish_removes_the_copy_and_leaves_the_run(tmp_path):
    source, destination = tmp_path / "run", tmp_path / "public"
    stage_run(source)
    publish_once(source, destination, REFERENCE)
    write_json(destination / "labels.json", {"2f0c1d": "A title", "other": "Keep me"})

    result = unpublish(destination, REFERENCE)

    assert result == {"unpublished": "2f0c1d", "published_runs": 0}
    assert not (destination / "2f0c1d").exists()
    assert read_json(destination / "index.json") == []
    assert read_json(destination / "labels.json") == {"other": "Keep me"}
    assert (source / "mcts_state.json").exists()
    assert (source / "events.jsonl").exists()


def test_unpublish_leaves_other_runs_alone(tmp_path):
    destination = tmp_path / "public"
    for name in ("first", "second"):
        stage_run(tmp_path / name)
        publish_once(tmp_path / name, destination, f"gs://a-bucket/urithiru/{name}")

    unpublish(destination, "gs://a-bucket/urithiru/first")

    assert [row["id"] for row in read_json(destination / "index.json")] == ["second"]
    assert (destination / "second" / "mcts_state.json").exists()
    assert not (destination / "first").exists()


def test_unpublish_cannot_delete_outside_the_published_directory(tmp_path):
    destination = tmp_path / "public"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("untouched")

    unpublish(destination, "gs://a-bucket/urithiru/../outside")
    assert (outside / "keep.txt").exists()
    assert not (destination / "outside").exists()

    for hostile in ("gs://a-bucket/urithiru/..", "gs://a-bucket/urithiru/."):
        with pytest.raises(ValueError):
            unpublish(destination, hostile)
    assert destination.exists()


def test_stream_events_yields_all_events_on_resumed_run():
    from urithiru.runtime.runs import stream_events

    lines = [
        json.dumps({"event": "run_started", "steps": 3}),
        json.dumps({"event": "stage_completed", "node": "node_000001"}),
        json.dumps({"event": "run_finished", "status": "completed", "completed": 3}),
        json.dumps({"event": "stage_started", "node": "node_000004"}),
        json.dumps({"event": "stage_completed", "node": "node_000004"}),
    ]
    streamed = list(stream_events(lambda: lines, follow=False))
    assert len(streamed) == 5
    assert json.loads(streamed[-1])["node"] == "node_000004"


def test_stream_events_follow_terminates_on_final_run_finished():
    from urithiru.runtime.runs import stream_events

    lines = [
        json.dumps({"event": "run_started", "steps": 3}),
        json.dumps({"event": "run_finished", "status": "completed", "completed": 3}),
        json.dumps({"event": "run_resumed", "steps": 6}),
        json.dumps({"event": "run_finished", "status": "completed", "completed": 6}),
    ]
    streamed = list(stream_events(lambda: lines, follow=True))
    assert len(streamed) == 4
    assert json.loads(streamed[-1])["completed"] == 6
