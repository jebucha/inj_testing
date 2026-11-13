# Spec Delta

## ADDED Requirements

### Requirement: Random dataset-prompt endpoint
The application SHALL expose a read-only `GET /api/benchmarks` endpoint that accepts a `difficulty` query parameter, filters the benchmark dataset's entries to that difficulty, randomly selects one, and returns 200 with that entry's `id`, `difficulty`, and `prompt`. It SHALL respond 400 with an invalid-difficulty error code for unknown difficulty values and 404 with a dataset-missing error code when the dataset is absent or has no matching entries, and SHALL NOT create or modify any file.

#### Scenario: Returns an entry of the requested difficulty
- **WHEN** the endpoint is called with `difficulty=easy` and the dataset contains `easy` entries
- **THEN** the response is 200 with `id`, `difficulty`, and `prompt` fields matching one of the dataset's `easy` entries
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-027
  - **File:** tests/test_benchmarks_endpoint.py::test_returns_entry_of_requested_difficulty
  - **Command:** uv run python -m pytest tests/test_benchmarks_endpoint.py::test_returns_entry_of_requested_difficulty -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unknown difficulty is rejected
- **WHEN** the endpoint is called with a `difficulty` value other than `easy`, `medium`, or `hard` (or without one)
- **THEN** the response is 400 with an invalid-difficulty error code
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-028
  - **File:** tests/test_benchmarks_endpoint.py::test_unknown_difficulty_rejected
  - **Command:** uv run python -m pytest tests/test_benchmarks_endpoint.py::test_unknown_difficulty_rejected -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Absent or empty dataset is a dataset-missing error
- **WHEN** the endpoint is called with a valid difficulty and the dataset file is absent or contains no entries for that difficulty
- **THEN** the response is 404 with a dataset-missing error code
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-029
  - **File:** tests/test_benchmarks_endpoint.py::test_missing_dataset_returns_404
  - **Command:** uv run python -m pytest tests/test_benchmarks_endpoint.py::test_missing_dataset_returns_404 -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: The endpoint does not persist anything
- **WHEN** the endpoint is called with a valid difficulty
- **THEN** no file is created or modified by the call
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-030
  - **File:** tests/test_benchmarks_endpoint.py::test_benchmarks_endpoint_writes_no_files
  - **Command:** uv run python -m pytest tests/test_benchmarks_endpoint.py::test_benchmarks_endpoint_writes_no_files -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Difficulty picker in the injection panel
The injection panel SHALL provide a "Difficulty" selector defaulting to a "Manual payload" placeholder option — selectable, so that selecting it returns the user to manual entry — with options `easy`, `medium`, and `hard`. Selecting a difficulty SHALL fetch a random dataset prompt, populate the payload field with it, and enable the injection control per the existing toggle rules. Selecting "Manual payload" SHALL be a no-op deselect that SHALL NOT clear or alter the payload field.

#### Scenario: The picker defaults to manual payload
- **WHEN** the page is loaded and the user has not touched the difficulty selector
- **THEN** the selector shows the "Manual payload" placeholder and the payload field is untouched
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-031
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_picker_defaults_to_manual_payload
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_picker_defaults_to_manual_payload -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Selecting a difficulty populates the payload
- **WHEN** a transcript is displayed and the user selects a dataset difficulty
- **THEN** the payload field contains the `prompt` of a dataset entry with that difficulty, the injection control is enabled, and the injection preview shows the prompt spliced into the transcript at the chosen insertion point
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-032
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_selecting_difficulty_populates_payload
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_selecting_difficulty_populates_payload -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Deselecting to manual payload preserves the text
- **WHEN** the payload field holds content (including content set by the picker) and the user selects "Manual payload"
- **THEN** the payload field retains its content unchanged and remains editable
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-033
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_manual_payload_preserves_text
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_manual_payload_preserves_text -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Re-roll of the random dataset prompt
The injection panel SHALL provide a re-roll control that, while a dataset difficulty is selected, fetches a fresh random dataset prompt for that difficulty and replaces the payload field's content with it. The re-roll control SHALL be disabled while no dataset difficulty is selected.

#### Scenario: Re-roll fetches a fresh prompt for the same difficulty
- **WHEN** the user has selected a difficulty and triggers the re-roll control
- **THEN** a new dataset prompt for the same difficulty is fetched and the payload field is replaced with it
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-034
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_reroll_fetches_fresh_prompt
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_reroll_fetches_fresh_prompt -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Re-roll is disabled without a selected difficulty
- **WHEN** the difficulty selector shows the "Manual payload" placeholder
- **THEN** the re-roll control is disabled
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-035
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_reroll_disabled_for_manual_payload
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_reroll_disabled_for_manual_payload -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Dataset entry id on benchmark result rows
When a benchmark run's payload was seeded from a dataset entry, each of that run's result rows SHALL display the seeded entry's `id`. For runs with no dataset entry id stored (a payload entered manually without a picker pick), the result rows SHALL display no dataset entry id.

#### Scenario: Dataset-seeded runs show the entry id
- **WHEN** the user selects a dataset prompt and completes a benchmark run
- **THEN** each result row of the run displays the dataset entry's `id` that seeded the run
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-036
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_result_row_shows_dataset_id
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_result_row_shows_dataset_id -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Manual-payload runs show no entry id
- **WHEN** a benchmark completes with a manually entered payload and no dataset difficulty selected
- **THEN** the result rows display no dataset entry id
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-037
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_result_row_no_id_for_manual_payload
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_result_row_no_id_for_manual_payload -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Dataset fetch failure handling
When a dataset prompt fetch (from the difficulty picker or the re-roll control) fails, the interface SHALL display an error message and SHALL turn the injection control back off if the failed fetch had turned it on. With a transcript displayed and no benchmark models selected, the "Run benchmark" control SHALL remain disabled after a failed fetch.

#### Scenario: A failed fetch blocks the run
- **WHEN** a transcript is displayed, no benchmark models are selected, and the user selects a difficulty whose dataset prompt fetch fails (for example because the dataset is absent)
- **THEN** the interface displays an error message and the "Run benchmark" control remains disabled
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-038
  - **File:** tests/e2e/test_benchmark_difficulty_picker.py::test_fetch_failure_blocks_run
  - **Command:** uv run python -m pytest tests/e2e/test_benchmark_difficulty_picker.py::test_fetch_failure_blocks_run -q
  - **Pass:** exit code 0, no skipped tests
