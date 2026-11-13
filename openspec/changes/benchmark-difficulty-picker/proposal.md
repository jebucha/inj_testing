# Proposal

## Why

The injection benchmark currently requires the user to hand-type an attacker
payload into the payload field. A curated benchmark dataset has been added
at `data/benchmark.jsonl` (153 self-contained prompt-injection scenarios,
tagged `difficulty` = `easy` / `medium` / `hard`), and there is no way to run
the benchmark against a randomly chosen entry from it. This change adds a
difficulty picker so a benchmark run can be seeded with a random dataset
prompt of the chosen difficulty.

## What Changes

- New read-only `GET /api/benchmarks` endpoint: given a `difficulty`
  query parameter, parses `data/benchmark.jsonl`, filters to entries with
  that difficulty, picks one at random, and returns its `id`, `difficulty`,
  and `prompt`. Rejects unknown difficulty values with 400 and reports a
  missing or empty dataset with 404. Filesystem reads go through
  `asyncio.to_thread`; the endpoint does not touch the single-flight
  semaphore.
- New "Difficulty" dropdown in the injection panel with a "Manual payload"
  placeholder option (default; selectable, so the user can return to manual
  entry) plus `easy`, `medium`, and `hard`. Selecting a difficulty fetches a
  random prompt for it, populates the existing payload field with that prompt,
  and enables the injection toggle. The existing insertion point, models, judge, canary, and splicing
  behavior are unchanged — the dataset prompt is the payload.
- A re-roll control that fetches a fresh random prompt for the currently
  selected difficulty (re-selecting the same option in a dropdown does not
  fire a change event).
- Selecting "Manual payload" is a no-op deselect: it returns the user to
  manual entry and never clears the textarea.
- Each benchmark result row displays the id of the dataset entry that seeded
  the run (blank/omitted for manual payloads).
- On a failed dataset fetch, the UI shows the error message; in a fresh panel
  (no benchmark models selected) the "Run benchmark" control stays disabled.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `prompt-injection-benchmark`: new requirements — the difficulty picker and
  its re-roll control, the random dataset-prompt endpoint, display of the
  picked dataset entry id on result rows, and the dataset-fetch error
  handling.

## Impact

- `app/main.py` (or a small new module): dataset parsing and the
  `GET /api/benchmarks` endpoint.
- `app/static/index.html`, `app/static/app.js`: difficulty dropdown, re-roll
  control, payload population, result-row id, error handling.
- `data/benchmark.jsonl`: new dataset file consumed by the endpoint
  (committed to git).
- `Dockerfile`: copy `data/` into the image so the container's default
  dataset path resolves.
- Tests: unit/API tests for the endpoint (happy path, random pick, unknown
  difficulty, missing/empty dataset, no file writes) and e2e tests for the
  picker (default placeholder, selection populates the payload, re-roll,
  manual deselect, result-row id, fetch failure).
- User-visible change: bump the app minor version (`uv version --bump minor`)
  before archiving.
