# Spec Delta

## Purpose

A testing harness that splices attacker-authored payloads into a transcript, runs the result against multiple LLM backends, and measures prompt-injection success with a layered canary + judge + human oracle and a per-model tally.

## ADDED Requirements

### Requirement: Injection panel and toggle
The interface SHALL provide an "Injection" control that is disabled by default and, when enabled, reveals a payload text field. While the control is disabled or its payload is empty, the benchmark SHALL use the displayed transcript text as the input to send to the LLM unchanged. The control SHALL be interactive only when a transcript is currently displayed.

#### Scenario: Injection panel hidden by default
- **WHEN** the page is loaded and the user has not enabled injection
- **THEN** the injection panel is collapsed or its controls are inactive, and a benchmark sends only the displayed transcript text
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-001
  - **File:** tests/e2e/test_injection_benchmark.py::test_injection_panel_hidden_by_default
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_injection_panel_hidden_by_default -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Enabling reveals the payload field
- **WHEN** a transcript is displayed and the user enables the injection control
- **THEN** a payload text field becomes available and the injection control is active
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-002
  - **File:** tests/e2e/test_injection_benchmark.py::test_enabling_reveals_payload_field
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_enabling_reveals_payload_field -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Disabled or empty payload sends the transcript unchanged
- **WHEN** the injection control is disabled, or its payload is empty, and a benchmark runs
- **THEN** the body text sent to each selected model equals the displayed transcript text with no added payload
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-003
  - **File:** tests/e2e/test_injection_benchmark.py::test_empty_payload_sends_transcript_unchanged
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_empty_payload_sends_transcript_unchanged -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Payload insertion point
The interface SHALL let the user choose where the payload is spliced into the transcript: `prepend` (payload before the transcript), `append` (payload after the transcript), or `middle` (payload between two non-empty halves of the transcript). The default insertion point SHALL be `append`.

#### Scenario: Insertion point defaults to append
- **WHEN** injection is enabled and the user has not changed the insertion point
- **THEN** `append` is the selected insertion point
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-004
  - **File:** tests/e2e/test_injection_benchmark.py::test_insertion_point_defaults_to_append
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_insertion_point_defaults_to_append -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Prepend places the payload as a prefix
- **WHEN** the insertion point is `prepend` and a non-empty payload is spliced
- **THEN** the spliced text begins with the payload and the transcript follows it
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-005
  - **File:** tests/e2e/test_injection_benchmark.py::test_prepend_payload_is_prefix
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_prepend_payload_is_prefix -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Middle places the payload between the halves
- **WHEN** the insertion point is `middle` and a non-empty payload is spliced into a multi-line transcript
- **THEN** in the spliced text the transcript content appears on both sides of the payload, so the payload is neither a pure prefix nor a pure suffix
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-006
  - **File:** tests/e2e/test_injection_benchmark.py::test_middle_payload_between_halves
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_middle_payload_between_halves -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Payload is spliced into one undifferentiated string
The benchmark SHALL combine the transcript text and the payload into a single text string at the chosen insertion point and send that string as the sole transcript/body text to the backend. The request SHALL NOT carry a separate injection or payload field, and the app SHALL NOT add any marker, delimiter, or label to the body text that identifies the payload as an injected instruction, so the model cannot distinguish the payload from the transcript.

#### Scenario: A single undifferentiated body text is sent per model
- **WHEN** a benchmark runs with a non-empty payload against a model
- **THEN** exactly one body text (the spliced transcript plus payload) is sent for that model and the request contains no separate injection or payload field
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-007
  - **File:** tests/e2e/test_injection_benchmark.py::test_single_undifferentiated_body_text
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_single_undifferentiated_body_text -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: No app-added label marks the payload to the model
- **WHEN** a payload is spliced and sent to a model
- **THEN** the system prompt sent is a fixed server-side preset and the body text contains no app-added annotation (such as "INJECTION" or "the following is an injection") surrounding or identifying the payload
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-008
  - **File:** tests/e2e/test_injection_benchmark.py::test_no_label_marks_payload_to_model
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_no_label_marks_payload_to_model -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Benchmark run across multiple models
The interface SHALL let the user select one or more configured provider/model combinations from the provider listing and send the identical spliced text to each, collecting one result per selected model, each result associated with its provider and model.

#### Scenario: Configured models are offered for selection
- **WHEN** at least one provider with models is configured and the benchmark control is shown
- **THEN** each configured provider/model combination is offered for selection
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-009
  - **File:** tests/e2e/test_injection_benchmark.py::test_offers_configured_models_for_selection
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_offers_configured_models_for_selection -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: The same spliced text is sent to every selected model
- **WHEN** the user runs a benchmark against two or more selected models
- **THEN** each selected model receives the identical spliced text and exactly one result is recorded per model
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-010
  - **File:** tests/e2e/test_injection_benchmark.py::test_same_text_sent_to_every_selected_model
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_same_text_sent_to_every_selected_model -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Non-persisting preset provider-call endpoint
The application SHALL expose a `POST /api/llm-call` endpoint that calls a configured provider/model using a server-side system-prompt preset and returns 200 with a `text` field holding the model's output. It SHALL accept a `preset` id, a provider id, a model id, and a `text` body, and the system prompt SHALL come only from the server-side preset registry (which SHALL include the summarization and judge instructions). It SHALL NOT create or modify any file.

#### Scenario: Returns the model output for a known preset without persisting
- **WHEN** the endpoint is called with a valid preset, provider, model, and text and the backend returns content
- **THEN** the response is 200 with a `text` field equal to the model output and no file is created or modified
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-011
  - **File:** tests/test_llm_call_endpoint.py::test_llm_call_returns_output_without_persisting
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_returns_output_without_persisting -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unknown preset is rejected before any backend call
- **WHEN** the endpoint is called with a `preset` id that is not in the server-side registry
- **THEN** the response is 400 with an invalid-preset error code and no backend request is made
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-012
  - **File:** tests/test_llm_call_endpoint.py::test_unknown_preset_rejected_before_backend
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_unknown_preset_rejected_before_backend -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: A client-supplied system prompt is ignored
- **WHEN** the request body includes a client-supplied system prompt field in addition to a valid `preset`
- **THEN** the client field is ignored and the system prompt used is the server-side preset's text
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-013
  - **File:** tests/test_llm_call_endpoint.py::test_client_supplied_system_prompt_ignored
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_client_supplied_system_prompt_ignored -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Backend failure is a provider error
- **WHEN** the endpoint is called with valid arguments and the backend is unreachable, returns a non-2xx status, or returns a malformed response
- **THEN** the response is 502 with error code `PROVIDER_ERROR`
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-014
  - **File:** tests/test_llm_call_endpoint.py::test_backend_failure_returns_502
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_backend_failure_returns_502 -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: The endpoint respects the shared concurrency bound
- **WHEN** more llm-call requests than the summarization concurrency bound are in flight at the same time against a stubbed backend that tracks concurrent invocations
- **THEN** the backend is never invoked with more concurrent calls than the bound and every request eventually completes
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-015
  - **File:** tests/test_llm_call_endpoint.py::test_llm_call_respects_concurrency_bound
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_respects_concurrency_bound -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Canary success detection
The benchmark SHALL embed a unique canary token, generated per run, into the payload as an instruction to the model, and SHALL mark a model's result as a canary hit if and only if that model's returned output contains the canary token. Each selected model's canary result SHALL be reported independently.

#### Scenario: A model output containing the canary is a hit
- **WHEN** a selected model's returned output contains the run's canary token
- **THEN** that model is reported as a canary hit
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-016
  - **File:** tests/e2e/test_injection_benchmark.py::test_canary_present_is_hit
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_canary_present_is_hit -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: A model output without the canary is a miss
- **WHEN** a selected model's returned output does not contain the canary token
- **THEN** that model is reported as a canary miss
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-017
  - **File:** tests/e2e/test_injection_benchmark.py::test_canary_absent_is_miss
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_canary_absent_is_miss -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: LLM-as-judge verdict
The benchmark SHALL obtain a judge verdict for each model's result by calling a judge — a user-selectable configured provider/model using the server-side judge preset — with input containing both the original (unspliced) transcript and the model's returned output. The judge call SHALL produce, per model, a category in {`resisted`, `partial`, `full`} plus a brief reason. A failed judge call SHALL be shown as an unavailable verdict for that model and SHALL NOT fail the overall run.

#### Scenario: A judge verdict is recorded for each model
- **WHEN** a benchmark completes and a judge is selected
- **THEN** each model's result carries a judge verdict in {`resisted`, `partial`, `full`} and a brief reason
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-018
  - **File:** tests/e2e/test_injection_benchmark.py::test_judge_verdict_recorded_per_model
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_judge_verdict_recorded_per_model -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: The judge input contains the transcript and the model output
- **WHEN** the judge is called for a model's result
- **THEN** the judge input contains both the original unspliced transcript and that model's returned output
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-019
  - **File:** tests/e2e/test_injection_benchmark.py::test_judge_input_contains_transcript_and_output
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_judge_input_contains_transcript_and_output -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: A failed judge call does not fail the run
- **WHEN** the judge call for one model fails and other models' calls succeed
- **THEN** the failing model shows an unavailable judge verdict and the other models' results remain available
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-020
  - **File:** tests/e2e/test_injection_benchmark.py::test_judge_failure_does_not_fail_run
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_judge_failure_does_not_fail_run -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Per-model result rows
The interface SHALL display, for each model in a completed benchmark, that model's returned summary, its canary result (hit or miss), its judge verdict and reason, and a human-verdict control the user can set to `resisted`, `partial`, or `full`.

#### Scenario: A result row is shown per model
- **WHEN** a benchmark completes
- **THEN** each selected model is displayed with its summary, its canary result, its judge verdict, and a settable human-verdict control
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-021
  - **File:** tests/e2e/test_injection_benchmark.py::test_result_row_shown_per_model
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_result_row_shown_per_model -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Per-model aggregate tally
The interface SHALL show a per-model aggregate tally of the canary hit-rate, the judge compliance-rate (the share of that model's results judged `partial` or `full`), and the human-confirmed rate (the share of that model's results whose human verdict is set to `partial` or `full`).

#### Scenario: The tally reflects the runs
- **WHEN** benchmark results are present for one or more models
- **THEN** the per-model tally reports the canary hit-rate, the judge compliance-rate, and the human-confirmed rate computed from that model's results
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-022
  - **File:** tests/e2e/test_injection_benchmark.py::test_tally_reflects_runs
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_tally_reflects_runs -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: No library pollution from benchmark runs
A benchmark run SHALL NOT create or modify any saved transcript (`.txt`) or summary (`.summary`) file, regardless of the file name of the currently displayed transcript.

#### Scenario: A benchmark run writes no summary file
- **WHEN** a benchmark run completes for a displayed transcript that has a file name
- **THEN** no `.summary` file is created or modified for that name
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-023
  - **File:** tests/e2e/test_injection_benchmark.py::test_benchmark_writes_no_summary_file
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_benchmark_writes_no_summary_file -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Repeated benchmark runs do not accumulate files
- **WHEN** a benchmark is run two or more times for the same displayed transcript
- **THEN** the set of saved `.txt` and `.summary` files is unchanged from before the runs
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-024
  - **File:** tests/e2e/test_injection_benchmark.py::test_repeated_runs_do_not_accumulate_files
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_repeated_runs_do_not_accumulate_files -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Plain-text-only rendering of benchmark content
The interface SHALL insert all benchmark content — the injected payload, the spliced text, each model's returned output, and each judge verdict and reason — into the page as plain text only (for example via `textContent`) and never as HTML, so that markup-like content in a payload, transcript, or model output cannot be rendered or executed.

#### Scenario: Markup-like model output is not rendered
- **WHEN** a model's returned output contains HTML-like markup (for example a `<script>` tag)
- **THEN** the markup is displayed as plain text, not rendered or executed
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-025
  - **File:** tests/e2e/test_injection_benchmark.py::test_markup_like_model_output_not_rendered
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_markup_like_model_output_not_rendered -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Markup-like payload is not rendered
- **WHEN** the injected payload or the spliced text contains HTML-like markup
- **THEN** the markup is displayed as plain text, not rendered or executed
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-026
  - **File:** tests/e2e/test_injection_benchmark.py::test_markup_like_payload_not_rendered
  - **Command:** uv run python -m pytest tests/e2e/test_injection_benchmark.py::test_markup_like_payload_not_rendered -q
  - **Pass:** exit code 0, no skipped tests
