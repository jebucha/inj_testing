# Tasks

> Tasks 2.1–2.4 and 3.1 are documentation and verification tasks implementing the proposal's Impact section; they intentionally have no direct spec requirement.

## 1. Core: `apiKeyEnv` resolution in the provider reader

- [x] 1.1 In `app/providers.py` `_parse_provider`, read `options.apiKeyEnv`: when it is a non-empty string, resolve it against the process environment; a set, non-empty value becomes the provider's `api_key` and takes precedence over a literal `options.apiKey`; a non-string `apiKeyEnv` is ignored with fallback to the literal key or `None`. Verify with `uv run python -m pytest tests/test_transcript_summarization.py -q` (existing tests still pass).
- [x] 1.2 In the same parser, when `apiKeyEnv` names a variable that is unset or set to an empty string, leave `api_key` as `None` (keyless) and emit exactly one warning event `provider_api_key_env_missing` via `get_logger()` carrying `provider` (provider id) and `variable` (variable name) and nothing else. Verify with `uv run python -m pytest tests/test_transcript_summarization.py -q` (existing tests still pass).
- [x] 1.3 Add unit test `tests/test_transcript_summarization.py::test_api_key_env_resolved_as_bearer`: config with `options.apiKeyEnv` naming a monkeypatched set variable results in the resolved value being the bearer token on the backend call (T-TRANSCRIPT-SUMMARIZATION-062). Verify: `uv run python -m pytest tests/test_transcript_summarization.py::test_api_key_env_resolved_as_bearer -q` passes.
- [x] 1.4 Add unit test `tests/test_transcript_summarization.py::test_api_key_env_precedes_literal_key`: entry carrying both a literal `apiKey` and `apiKeyEnv` with a different value resolves to the variable's value (T-TRANSCRIPT-SUMMARIZATION-063). Verify: `uv run python -m pytest tests/test_transcript_summarization.py::test_api_key_env_precedes_literal_key -q` passes.
- [x] 1.5 Add unit test `tests/test_transcript_summarization.py::test_api_key_env_missing_degrades_to_keyless`: variable unset and variable set to empty string both leave the provider usable with `api_key is None`, each producing exactly one `provider_api_key_env_missing` warning event carrying the provider id and variable name and no key value, with no request crashing (T-TRANSCRIPT-SUMMARIZATION-064). Verify: `uv run python -m pytest tests/test_transcript_summarization.py::test_api_key_env_missing_degrades_to_keyless -q` passes.
- [x] 1.6 Add unit test `tests/test_transcript_summarization.py::test_api_key_env_absent_from_provider_listing`: `GET /api/providers` for a provider using `apiKeyEnv` with the variable set contains neither the resolved key nor the variable's value (T-TRANSCRIPT-SUMMARIZATION-065). Verify: `uv run python -m pytest tests/test_transcript_summarization.py::test_api_key_env_absent_from_provider_listing -q` passes.

## 2. Documentation and examples

- [x] 2.1 Extend `providers.json.example` with a second example provider demonstrating `options.apiKeyEnv` (keeping the file strict JSON — no comments), and document the same in `docs/providers-json-example.md`. Verify: the example file still parses as valid JSON (`uv run python -c "import json; json.load(open('providers.json.example'))"`) and both docs mention `apiKeyEnv`.
- [x] 2.2 Update `docs/providers.md`: document `apiKeyEnv` resolution semantics (sibling field, env wins over literal, unset/empty degrades to keyless, resolved at each config read) and the new `provider_api_key_env_missing` warning event in the "Log events emitted" section, including the note that env values are fixed at process start while the config file hot-reloads. Verify: `docs/providers.md` contains the new event name and both semantics.
- [x] 2.3 Update the README provider-config section to mention `apiKeyEnv` and operator-side env wiring (compose `env_file:` or shell export). Verify: the README references `apiKeyEnv`.
- [x] 2.4 Add `env` to `.gitignore` (the operator env file holding live tokens). Verify: `git check-ignore env` exits 0 and `git status --short` no longer lists `env` as untracked.

## 3. Integration check

- [x] 3.1 Run the full non-e2e suite `uv run python -m pytest tests/ -q --ignore=tests/e2e` and verify it passes with no skipped summarization tests.
