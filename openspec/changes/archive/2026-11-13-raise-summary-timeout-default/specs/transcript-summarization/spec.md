# Spec Delta

## ADDED Requirements

### Requirement: Backend call timeout default
Every LLM backend call — the summarize call from `POST /api/summarize` and the preset call from `POST /api/llm-call` — SHALL be bounded by a call timeout (connect + read) that defaults to 300 seconds and SHALL be overridable via the `SUMMARY_TIMEOUT` environment variable, read at call time; a non-numeric value SHALL fall back to the default. Timeout failures SHALL surface as a 502 `PROVIDER_ERROR`.

#### Scenario: Default backend call timeout is 300 seconds
- **WHEN** the app calls the configured backend for `POST /api/summarize` while `SUMMARY_TIMEOUT` is not set
- **THEN** the backend call is made with a 300 second timeout
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-059
  - **File:** tests/test_transcript_summarization.py::test_default_summary_timeout_is_300
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_default_summary_timeout_is_300 -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Preset provider call uses the same default timeout
- **WHEN** the app calls the configured backend for `POST /api/llm-call` while `SUMMARY_TIMEOUT` is not set
- **THEN** the backend call is made with the same 300 second default timeout as summarization
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-060
  - **File:** tests/test_llm_call_endpoint.py::test_llm_call_uses_default_timeout
  - **Command:** python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_uses_default_timeout -q
  - **Pass:** exit code 0, no skipped tests
