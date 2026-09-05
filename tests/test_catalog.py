import json

import pytest

from urithiru.cloud.catalog import PAGE_FILES, run_id, strip_events, summarize, web_config

REFERENCE = "gs://a-private-bucket-000000000000/urithiru/2f0c1d"


def test_a_run_id_is_the_only_thing_a_caller_names():
    assert run_id("68943881abcc45dd94a81ff3c48cd042") == "68943881abcc45dd94a81ff3c48cd042"
    hostile = [
        "../../etc/passwd",
        "68943881abcc45dd94a81ff3c48cd042/../../other",
        "68943881abcc45dd94a81ff3c48cd042/inputs/000_data.csv",
        "68943881ABCC45DD94A81CD042",
        "",
        ".",
        "*",
    ]
    for identifier in hostile:
        with pytest.raises(ValueError):
            run_id(identifier)


def test_only_the_three_files_the_page_reads_are_named():
    assert PAGE_FILES == ("run.json", "mcts_state.json", "events.jsonl")
    for private in ("run_config.json", "inputs/000_data.csv", "sandbox_artifacts/search/p_search.json"):
        assert private not in PAGE_FILES


def test_run_json_omits_where_the_run_ran():
    record = {
        "steps": 3,
        "seed": 7,
        "dataset": {"files": ["inputs/000_data.csv"], "metadata": "notes", "hashes": {}},
        "config": {
            "models": {"agent": "gemini-3.7-flash"},
            "budget": {"code_minutes": 10},
            "options": {"project": "a-project", "bucket": "a-private-bucket-000000000000"},
        },
    }

    published = web_config(record)

    assert set(published) == {"dataset", "steps", "seed", "models", "budget"}
    assert "a-private-bucket" not in json.dumps(published)
    assert "a-project" not in json.dumps(published)


def test_stripped_log_keeps_every_line_and_field_except_the_reference():
    lines = [
        {"time": "05:39", "run": REFERENCE, "event": "run_started", "steps": 3},
        {"time": "05:57", "run": REFERENCE, "event": "run_finished", "status": "completed"},
    ]
    text = "".join(f"{json.dumps(line)}\n" for line in lines)

    stripped = [json.loads(line) for line in strip_events(text).splitlines()]

    assert len(stripped) == len(lines)
    for before, after in zip(lines, stripped, strict=True):
        assert "run" not in after
        assert after == {key: value for key, value in before.items() if key != "run"}


def test_a_line_that_will_not_parse_is_dropped_rather_than_passed_through():
    text = f'{json.dumps({"run": REFERENCE, "event": "run_started"})}\n{{"run": "{REFERENCE}", "even\n'

    stripped = strip_events(text)

    assert "gs://" not in stripped
    assert [json.loads(line)["event"] for line in stripped.splitlines()] == ["run_started"]


def test_summary_is_the_index_row_and_the_status_report_at_once():
    checkpoint = {
        "steps": 3,
        "status": "failed",
        "error": "FileNotFoundError",
        "completed": ["node_000001"],
        "pending": [],
        "updated_at": "2026-08-30T05:57:07+00:00",
        "nodes": [],
    }

    summary = summarize(checkpoint)

    assert (
        summary
        | {
            "status": "failed",
            "completed": 1,
            "requested": 3,
            "error": "FileNotFoundError",
            "updated_at": "2026-08-30T05:57:07+00:00",
        }
        == summary
    )
    assert summary["highlight"] is None
