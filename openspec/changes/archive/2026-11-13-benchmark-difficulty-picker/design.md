# Design

## Context

The app is a single FastAPI backend (`app/main.py`) serving a vanilla JS, no-build
frontend from `app/static`, with these standing conventions (AGENTS.md):

- All fetched content enters the DOM via `textContent` only.
- No blocking I/O on the event loop — filesystem work goes through
  `asyncio.to_thread`.
- The single-flight semaphore governs only the YouTube fetch chain; read
  endpoints must not touch it.

The injection benchmark today is: user types a payload into `#injection-payload`
→ on run, a per-run canary instruction is appended → the payload is spliced into
the displayed transcript at the chosen insertion point → one `POST /api/llm-call`
per selected model → canary/judge/human verdicts per model. The payload field is
only ever user-typed.

`data/benchmark.jsonl` (153 lines) provides the dataset. Each line has
`id`, `source_item_id`, `use_case`, `difficulty` (`easy`/`medium`/`hard`),
`prompt`, `verification_criteria`. Counts: easy 31, medium 61, hard 61.

Existing pattern for overridable paths: env var read at call time with a
repo default (`TRANSCRIPT_DIR` in `app/persist.py`, `PROVIDERS_CONFIG` in
`app/providers.py`). Tests point these at temp files.

## Goals / Non-Goals

**Goals:**

- One server-side random, difficulty-filtered pick per fetch; the browser never
  needs the full dataset.
- The fetched prompt feeds the *existing* payload pipeline (payload field →
  canary → splice → llm-call) with zero changes to splicing, canary, judge, or
  tally semantics.
- Testability: unit-testable endpoint and e2e-testable picker, both able to
  point at a fixture dataset or a missing one.

**Non-Goals:**

- No changes to `/api/llm-call`, the canary, the judge flow, insertion points,
  or the per-model tally.
- No persistence of which dataset entry seeded a run (UI state only).
- No dataset authoring/upload/editing; the file is a committed data asset.
- No guarantee against picking the same entry on consecutive runs.

## Decisions

### 1. Server endpoint `GET /api/benchmarks?difficulty=<easy|medium|hard>`

New read-only endpoint in `app/main.py`, backed by a small module
(`app/benchmark_dataset.py`) that owns parsing and selection:

- `dataset_path()` resolves at call time: env var `BENCHMARK_DATASET`
  (same pattern as `TRANSCRIPT_DIR`), default `data/benchmark.jsonl` —
  CWD-relative, exactly like `PROVIDERS_CONFIG`'s `providers.json` default:
  locally the app runs from the repo root, and in the container the WORKDIR
  is `/app` with `COPY data ./data`, so it resolves to
  `/app/data/benchmark.jsonl`.
- The handler validates `difficulty` against the known set, reads and parses
  the file inside `asyncio.to_thread`, filters to matching entries, and picks
  one with `random.choice`, returning `{"id", "difficulty", "prompt"}`.

Error semantics (new error codes, following the existing taxonomy style):

- 400 `INVALID_DIFFICULTY` — value missing or not one of the three.
- 404 `DATASET_MISSING` — file absent, or no valid entries for the difficulty.

Lines that fail to parse or lack `id`/`difficulty`/`prompt` are skipped, so a
corrupted line cannot 500 the endpoint; if skipping leaves no entries for the
difficulty, the result is 404.

Alternatives considered:

- *Serve the raw file, parse in JS* — ships the whole (growing) dataset to the
  browser and hard-codes its location client-side. Rejected.
- *Pick server-side at run time (POST)* — the picker's whole point (see
  decision 2) is that the user sees and previews the exact prompt before
  running. Rejected.

The endpoint does not create or modify files and does not touch the
single-flight semaphore (read endpoint, per AGENTS.md).

### 2. Pick happens on selection / re-roll, into the visible payload field

The difficulty `<select>` (new, in the injection panel's control row) has a
`value="manual"` placeholder option — "Manual payload" — plus the three
difficulties. The placeholder is selectable (not `disabled`): browsers and
Playwright's `select_option` refuse to select a disabled option, which would
make the deselect path unusable and untestable. On `change` to a difficulty:
`fetch("/api/benchmarks?difficulty=…")` → on 200, set `#injection-payload` to
the prompt, store the entry `id` in JS state, check the injection toggle (if
the existing toggle rules allow, i.e. a transcript is displayed), and call
`updateBenchmarkEnabled()` explicitly — a programmatic `checked` assignment
fires no `change` event, and the toggle's `change` listener is the only other
trigger — so the payload field becomes enabled/visible, the preview refreshes,
and the run button state is recomputed. On non-200: show the error in a small
status line (textContent) and, if the fetch had turned the toggle on, turn it
off again; the existing `updateBenchmarkEnabled` logic then keeps "Run
benchmark" disabled in the fresh-panel case (a transcript displayed, no models
selected — see the Risks note below).

"Manual payload" is a no-op deselect: it clears the stored entry id (so result
rows stop showing it) but never touches the payload field.

A separate re-roll control re-runs the same fetch for the currently selected
difficulty. It is disabled while the selector shows "Manual payload". This
exists because `<select>` `change` does not fire when the same value is
re-selected.

The difficulty select and the re-roll control join `updateBenchmarkEnabled`'s
governance like the other `.injection-controls` controls: both are disabled
while a benchmark run is in flight and, like the toggle, require a displayed
transcript to be interactive (the re-roll control keeps its additional
"Manual payload" rule above).

Alternatives considered:

- *Pick on every "Run benchmark" click* — statistically nicer, but the payload
  would change invisibly per run and the preview would lie. Rejected per the
  explored design (transparency of "see exactly what will be sent").
- *Hidden state instead of the payload field* — would bypass the existing
  preview/effectivePayload machinery and diverge from the harness's
  plain-text-only rendering. Rejected.

### 3. Dataset entry id on result rows

JS state holds the id of the entry most recently fetched into the payload. At
run time it is captured into each run's results and rendered as a plain-text
meta line on each result row (next to the existing canary span), via
`textContent`. It is cleared when the user deselects to "Manual payload"; manual
edits to the payload field do not clear it (the payload was still seeded by
that entry — the id is shown whenever an entry id is stored, not only while
the field is unedited). Runs with no stored id render nothing for this cell.

### 4. UI placement

Difficulty select and re-roll control join the existing `.injection-controls`
row, after the insertion-point select, reusing the `benchmark-label` / `btn`
classes. The error status line lives beside them and is `hidden` except on
failure. No CSS framework, no new dependencies.

## Risks / Trade-offs

- [Consecutive runs can repeat the same entry (1/31 for easy)] → re-roll is the
  escape hatch; a no-repeat queue is a future enhancement, not in scope.
- [Rapid re-roll clicks fire overlapping fetches; responses could land out of
  order] → last-arriving response wins; at this dataset size and latency the
  worst case is the payload showing a slightly older random entry, still a
  valid entry of the selected difficulty. No request-id machinery for this.
- [Dataset shape drift (new/renamed fields)] → missing required fields make a
  line invalid and skipped; the endpoint degrades to 404 rather than 500.
- [Very long prompts in a 3-row textarea] → it scrolls; the preview already
  handles long spliced text.
- [The "failed fetch blocks the run" guarantee is scoped to the fresh-panel
  pre-state] → with a transcript displayed and no models selected, the existing
  enable logic keeps the run button disabled after the failure, and the e2e
  test asserts exactly that pre-state. With models already selected, a failed
  re-roll leaves the previous (still valid) payload runnable — accepted
  trade-off: the error line tells the user the re-roll failed, and a successful
  re-fetch or a manual edit supersedes the payload.

## Test Strategy

- **Backend (API) tests** — `tests/test_benchmarks_endpoint.py`
  (T-PROMPT-INJECTION-BENCHMARK-027…030): exercise `GET /api/benchmarks`
  against a fixture dataset built under `tmp_path` and wired via
  `BENCHMARK_DATASET` (valid lines per difficulty, one malformed JSON line,
  one line missing a required field) plus a missing-dataset fixture
  (`BENCHMARK_DATASET` → a nonexistent path) — asserting the 200 contract,
  the difficulty match of the random pick, the 400 invalid-difficulty
  response, the 404 dataset-missing mapping, and that no file is written.
- **e2e (UI) tests** — `tests/e2e/test_benchmark_difficulty_picker.py`
  (T-PROMPT-INJECTION-BENCHMARK-031…038): headless Chromium via Playwright,
  reusing the in-process uvicorn + stubbed fetch chain + recording
  chat-completions stub pattern from `tests/e2e/test_injection_benchmark.py`;
  the picker scenarios run against a small fixture dataset wired via
  `BENCHMARK_DATASET`, and the fetch-failure scenario points `BENCHMARK_DATASET`
  at a nonexistent path.
- One-time prerequisite for e2e: `uv run python -m playwright install chromium`.
- Every Test Requirement block in the spec carries its own File/Command; all
  commands run as `uv run python -m pytest … -q` and pass on exit code 0 with
  no skipped tests.

## Migration Plan

Pure addition: no schema, data, or API breakage; the dataset file is committed
to the repo and copied into the image by the Dockerfile (`COPY data ./data`),
landing at `/app/data/benchmark.jsonl` next to the app code. Rollback is
reverting the change (picker, endpoint, packaging line, and tests go away
together). Per repo convention, bump the app minor version
(`uv version --bump minor`) before archiving since the change is
user-visible.
