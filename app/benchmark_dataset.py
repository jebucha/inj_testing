"""Benchmark dataset: dataset-path resolution, parsing, and random selection.

Kept free of FastAPI imports (like ``app/persist.py`` and ``app/providers.py``):
the functions are pure over the dataset file path so they are testable
directly against ``tmp_path``.

The dataset is read on every call, never at startup (design decision 1):
a file that changes, appears, or disappears takes effect on the next
request, and a corrupted file degrades to a dataset-missing error rather
than an exception.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from app.errors import DatasetMissingError, InvalidDifficultyError

# Default dataset path: data/benchmark.jsonl in the working directory.
# Overridable via BENCHMARK_DATASET — the same read-at-call-time pattern as
# PROVIDERS_CONFIG in app/providers.py and TRANSCRIPT_DIR in app/persist.py.
_DEFAULT_DATASET = "data/benchmark.jsonl"

# The difficulty tags the dataset entries carry.
DIFFICULTIES = frozenset({"easy", "medium", "hard"})


def dataset_path() -> Path:
    """Resolve the dataset file path at call time (design decision 1)."""
    return Path(os.environ.get("BENCHMARK_DATASET", _DEFAULT_DATASET))


def select_entry(difficulty: str | None) -> dict:
    """Pick one random dataset entry matching ``difficulty``.

    Raises ``InvalidDifficultyError`` for a missing or unknown difficulty
    (before any filesystem access), and ``DatasetMissingError`` when the
    file is absent or contains no valid entry for that difficulty. Lines
    that fail to parse, are not JSON objects, or lack a non-empty string
    ``id``/``difficulty``/``prompt`` are skipped, so a corrupted line can
    never fail the request. Returns exactly ``{"id", "difficulty",
    "prompt"}`` for the picked entry.
    """
    if difficulty not in DIFFICULTIES:
        raise InvalidDifficultyError()
    try:
        with open(dataset_path(), "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        raise DatasetMissingError() from None
    entries: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        prompt = entry.get("prompt")
        if (
            entry.get("difficulty") == difficulty
            and isinstance(entry_id, str)
            and entry_id
            and isinstance(prompt, str)
            and prompt
        ):
            entries.append(
                {"id": entry_id, "difficulty": difficulty, "prompt": prompt}
            )
    if not entries:
        raise DatasetMissingError()
    return random.choice(entries)
