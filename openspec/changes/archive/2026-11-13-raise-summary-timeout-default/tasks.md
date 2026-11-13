# Tasks

## 1. Code

- [x] 1.1 In `app/summarize.py`, change `DEFAULT_SUMMARY_TIMEOUT` from `120.0` to `300.0` and rewrite the adjacent sizing comment (no longer "sized for local 27B-class models"; state the 300 s default for slower local inference hardware, `SUMMARY_TIMEOUT` still the override). Verify with `uv run python -c "from app.summarize import DEFAULT_SUMMARY_TIMEOUT; assert DEFAULT_SUMMARY_TIMEOUT == 300.0"`
- [x] 1.2 In `app/main.py`, update the two pool comments that state "120 s" (lines ~62 and ~71) to "300 s". Verify with `grep -n "120 s" app/main.py` returning nothing
- [x] 1.3 In `tests/test_transcript_summarization.py`, add `test_default_summary_timeout_is_300` (T-TRANSCRIPT-SUMMARIZATION-059): with `SUMMARY_TIMEOUT` unset, drive `summarize_with_provider` against the existing stubbed dispatch and assert the backend call was made with a 300.0 s timeout. Verify with `uv run python -m pytest tests/test_transcript_summarization.py::test_default_summary_timeout_is_300 -q` (exit 0, no skipped)
- [x] 1.4 In `tests/test_llm_call_endpoint.py`, add `test_llm_call_uses_default_timeout` (T-TRANSCRIPT-SUMMARIZATION-060): with `SUMMARY_TIMEOUT` unset, POST `/api/llm-call` and assert the recorded dispatch call carried the same 300.0 s default timeout as summarization. Verify with `uv run python -m pytest tests/test_llm_call_endpoint.py::test_llm_call_uses_default_timeout -q` (exit 0, no skipped)
- [x] 1.5 Update the stale "120 s" comment in `tests/test_transcript_summarization.py` (~line 943) to 300 s. Verify with `grep -n "120 s" tests/test_transcript_summarization.py` returning nothing

## 2. Docs

- [x] 2.1 In `README.md`, update the `SUMMARY_TIMEOUT` environment-variable row: default `120` → `300`, and adjust the sizing note ("sized for local 27B-class models" → default sized for slower local inference hardware; lower it for fast backends or raise it further if needed). Verify by reading the row
- [x] 2.2 In `docs/summarize.md` and `docs/summarize.html`, update both "default 120 s" / "120.0" references to 300 s / 300.0. Verify with `grep -n "120" docs/summarize.md docs/summarize.html` returning nothing
- [x] 2.3 In `docs/model_discovery.md` and `docs/model_discovery.html`, update "a 120 s summarize must not block" to "a 300 s summarize must not block". Verify with `grep -n "120" docs/model_discovery.md docs/model_discovery.html` returning nothing

## 3. Verification

- [x] 3.1 Run the unit + API + logging suite: `uv run python -m pytest tests/ -q --ignore=tests/e2e` — all pass (existing env-override and constant-referencing tests stay green)
- [x] 3.2 Run the e2e suite: `uv run python -m pytest tests/e2e/ -q` — all pass (no UI or error-message changes, but the suite exercises the summarize/benchmark flows end to end)
- [x] 3.3 Confirm no living file still states the 120 s default: `grep -rn "120 s\|120\.0\|120" app/ README.md docs/ tests/` returns only historical/archived matches (openspec archive, security-audits) or unrelated numerics
