# Spec Delta

## MODIFIED Requirements

### Requirement: Non-persisting preset provider-call endpoint
The application SHALL expose a `POST /api/llm-call` endpoint that calls a provider/model from the effective provider configuration (the provider config file plus UI-added overlay models) using a server-side system-prompt preset and returns 200 with a `text` field holding the model's output. It SHALL accept a `preset` id, a provider id, a model id, and a `text` body, and the system prompt SHALL come only from the server-side preset registry (which SHALL include the summarization and judge instructions). It SHALL NOT create or modify any file.

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

#### Scenario: A UI-added (overlay) model is accepted
- **WHEN** the endpoint is called with a valid preset, provider, model, and text where the model id is present in the UI-added model overlay for that provider but not in the provider config file, and the backend returns content
- **THEN** the backend is called for that provider/model under the provider's configured base URL and the response is 200 with a `text` field equal to the model output
- **Test Requirement**
  - **ID:** T-PROMPT-INJECTION-BENCHMARK-039
  - **File:** tests/test_llm_call_endpoint.py::test_llm_call_accepts_added_model
  - **Command:** uv run python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_accepts_added_model -q
  - **Pass:** exit code 0, no skipped tests
