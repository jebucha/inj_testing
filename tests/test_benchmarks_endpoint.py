"""T-PROMPT-INJECTION-BENCHMARK-027 .. 030: GET /api/benchmarks.

Unit-tested with TestClient against a fixture dataset built under
``tmp_path`` and wired via BENCHMARK_DATASET (the endpoint resolves the
path at call time, so each fixture points the env var at its own file).
"""

import json

import pytest
from starlette.testclient import TestClient

from app.main import create_app

# One valid entry per difficulty (two easy, so the random pick has a real
# choice), plus lines the parser must skip: one malformed JSON line and one
# line missing a required field.
EASY_ENTRIES = [
    {"id": "easy-1", "difficulty": "easy", "prompt": "Easy prompt one."},
    {"id": "easy-2", "difficulty": "easy", "prompt": "Easy prompt two."},
]
MEDIUM_ENTRIES = [
    {"id": "medium-1", "difficulty": "medium", "prompt": "Medium prompt one."},
]
HARD_ENTRIES = [
    {"id": "hard-1", "difficulty": "hard", "prompt": "Hard prompt one."},
]
FIXTURE_LINES = (
    [json.dumps(entry) for entry in EASY_ENTRIES + MEDIUM_ENTRIES + HARD_ENTRIES]
    + ['{this line is not valid json"']
    + [json.dumps({"id": "incomplete-1", "difficulty": "easy"})]  # no prompt
)


def _write_dataset(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient with the fixture dataset wired in via BENCHMARK_DATASET."""
    dataset = tmp_path / "benchmark.jsonl"
    _write_dataset(dataset, FIXTURE_LINES)
    monkeypatch.setenv("BENCHMARK_DATASET", str(dataset))
    client = TestClient(create_app())
    with client:
        yield {"client": client, "dataset": dataset, "tmp_path": tmp_path}


@pytest.fixture
def api_missing(tmp_path, monkeypatch):
    """TestClient with BENCHMARK_DATASET pointing at a nonexistent path."""
    monkeypatch.setenv("BENCHMARK_DATASET", str(tmp_path / "absent.jsonl"))
    client = TestClient(create_app())
    with client:
        yield {"client": client, "tmp_path": tmp_path}


def _files_by_state(tmp_path):
    return {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }


def test_returns_entry_of_requested_difficulty(api):
    """T-PROMPT-INJECTION-BENCHMARK-027"""
    for difficulty, entries in (
        ("easy", EASY_ENTRIES),
        ("medium", MEDIUM_ENTRIES),
        ("hard", HARD_ENTRIES),
    ):
        for _ in range(10):
            response = api["client"].get(f"/api/benchmarks?difficulty={difficulty}")
            assert response.status_code == 200
            body = response.json()
            # exactly the entry's id / difficulty / prompt — no extra fields
            assert set(body.keys()) == {"id", "difficulty", "prompt"}
            # one of the dataset's valid entries for that difficulty: the
            # malformed line and the line missing a field are never returned
            assert body in entries


def test_unknown_difficulty_rejected(api):
    """T-PROMPT-INJECTION-BENCHMARK-028"""
    # a value outside the known set, an empty value, and a missing parameter
    for query in ("difficulty=impossible", "difficulty=", ""):
        response = api["client"].get("/api/benchmarks?" + query)
        assert response.status_code == 400
        error = response.json()["error"]
        assert set(error.keys()) == {"code", "message"}
        assert error["code"] == "INVALID_DIFFICULTY"
        assert error["message"]


def test_missing_dataset_returns_404(api_missing, monkeypatch, tmp_path):
    """T-PROMPT-INJECTION-BENCHMARK-029"""
    # an absent dataset file is a dataset-missing error for every difficulty
    for difficulty in ("easy", "medium", "hard"):
        response = api_missing["client"].get(
            f"/api/benchmarks?difficulty={difficulty}"
        )
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "DATASET_MISSING"
        assert error["message"]

    # a present dataset with no entries for the requested difficulty is the
    # same error (the path is resolved per request, so the env var swap is
    # enough)
    sparse = tmp_path / "sparse.jsonl"
    _write_dataset(sparse, [json.dumps(EASY_ENTRIES[0])])
    monkeypatch.setenv("BENCHMARK_DATASET", str(sparse))
    response = api_missing["client"].get("/api/benchmarks?difficulty=hard")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DATASET_MISSING"


def test_benchmarks_endpoint_writes_no_files(api):
    """T-PROMPT-INJECTION-BENCHMARK-030"""
    before = _files_by_state(api["tmp_path"])

    for difficulty in ("easy", "medium", "hard"):
        assert (
            api["client"].get(f"/api/benchmarks?difficulty={difficulty}")
        ).status_code == 200
    # a rejected call must not write either
    assert (
        api["client"].get("/api/benchmarks?difficulty=impossible")
    ).status_code == 400

    # no file in the working dataset directory was created or modified
    assert _files_by_state(api["tmp_path"]) == before
