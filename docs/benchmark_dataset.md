# `app/benchmark_dataset.py` — the benchmark dataset

## Purpose

The dataset side of the injection benchmark's difficulty picker: resolving
the dataset file path, parsing `data/benchmark.jsonl`, and picking one
random entry of a requested difficulty. It has no FastAPI imports — the
functions are pure over the dataset file path so they are testable directly
against `tmp_path`. `app/main.py` wraps `select_entry` in
`asyncio.to_thread` for the read-only `GET /api/benchmarks` endpoint.

## Public surface

- `dataset_path() -> Path` — resolves the dataset file path at call time:
  env var `BENCHMARK_DATASET` (same pattern as `TRANSCRIPT_DIR` and
  `PROVIDERS_CONFIG`), default `data/benchmark.jsonl` — CWD-relative,
  exactly like `PROVIDERS_CONFIG`'s `providers.json` default (locally the
  app runs from the repo root; in the container the WORKDIR is `/app` with
  `COPY data ./data`, so it resolves to `/app/data/benchmark.jsonl`).
- `DIFFICULTIES` — the frozenset of valid difficulty tags: `easy`,
  `medium`, `hard`.
- `select_entry(difficulty) -> dict` — validates the difficulty, reads and
  parses the file, filters to matching entries, and returns one random
  pick as exactly `{"id", "difficulty", "prompt"}`.

## Invariants

- **Read-only.** The file is only ever opened for reading (`"r"`); the
  module creates or modifies nothing — a dataset pick can never pollute the
  filesystem.
- **The dataset is read on every call, never at startup.** A file that
  changes, appears, or disappears takes effect on the next request; a
  corrupted file degrades to a dataset-missing error rather than an
  exception.
- **Difficulty validation happens before any filesystem access.** A missing
  or unknown difficulty raises `InvalidDifficultyError` (400) before the
  file is opened.
- **Corrupted lines are skipped, not fatal.** Lines that fail to parse, are
  not JSON objects, or lack a non-empty string `id`/`difficulty`/`prompt`
  are dropped; if that leaves no entries for the difficulty, the result is
  `DatasetMissingError` (404) rather than a 500.
- **No blocking I/O on the event loop.** The module itself is synchronous;
  `app/main.py` dispatches the call with `asyncio.to_thread`.
- **No single-flight.** The dataset pick never touches the fetch chain's
  semaphore (read path, per AGENTS.md).
- **The dataset is a committed data asset.** No authoring, upload, or
  editing; the file ships in the repo and is copied into the image by the
  Dockerfile.

## Log events emitted

None.

## Error codes raised/handled

- `InvalidDifficultyError` (400 `INVALID_DIFFICULTY`) — the difficulty is
  missing or not one of `easy`/`medium`/`hard`.
- `DatasetMissingError` (404 `DATASET_MISSING`) — the file is absent,
  unreadable, or its valid lines leave no entry for the difficulty.

## Design decisions

Resolved from the archived change design docs:

- `benchmark-difficulty-picker` **decision 1** — the call-time path
  resolution (`BENCHMARK_DATASET`, CWD-relative default, the
  `TRANSCRIPT_DIR` / `PROVIDERS_CONFIG` pattern), read-per-request
  semantics, the skip-malformed-lines rule, and the server-side random pick
  (the browser never needs the full dataset).

## Cross-links

- [`main.py`](main.html) — the `GET /api/benchmarks` endpoint wrapping this
- [`errors.py`](errors.html) — the two taxonomy codes it raises
- [`static/app-js.html`](static/app-js.html) — the picker that fetches it
