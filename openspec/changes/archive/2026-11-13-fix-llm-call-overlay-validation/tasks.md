# Tasks

## 1. Endpoint fix

- [x] 1.1 In `app/main.py`, switch `llm_call_endpoint` from `load_providers()` to `_merged_provider_config()` (same composition `summarize_endpoint` uses) and carry the "merged config is the single source" comment; verify all existing endpoint tests still pass: `uv run python -m pytest tests/test_llm_call_endpoint.py tests/test_transcript_summarization.py -q`
- [x] 1.2 Add `test_llm_call_accepts_added_model` (T-PROMPT-INJECTION-BENCHMARK-039) to `tests/test_llm_call_endpoint.py`, mirroring the `test_summarize_accepts_added_model` pattern: write `provider_overrides.json` into the fixture's tmp transcript dir adding a model to provider `alpha`, POST `/api/llm-call` with that model, assert 200 with the stub's output and that the dispatch stub was invoked exactly once with the overlay model id and `alpha`'s configured base URL; verify: `uv run python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_accepts_added_model -q`

## 2. Integration verification

- [x] 2.1 Run the full non-e2e suite and verify it passes with no skips: `uv run python -m pytest tests/ -q --ignore=tests/e2e`
- [x] 2.2 Run the e2e suite and verify it passes with no skips: `uv run python -m pytest tests/e2e/ -q` (chromium prerequisite: `uv run python -m playwright install chromium`)

## Workflow follow-up

- Bump the app's minor version before archiving (user-visible bug fix): `uv version --bump minor`.
