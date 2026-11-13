# Proposal

## Why

The default LLM backend-call timeout (120 s) is sized for fast local 27B-class hardware. On a slower inference machine, a real-world run of the injection benchmark's `summarize` preset timed out at exactly 120 s while the model was still producing a valid result, surfacing in the UI as "The summarization backend failed" (`llm_call_failed … [timeout]`, `POST /api/llm-call -> 502`). Operators currently must set `SUMMARY_TIMEOUT` by hand per slow host; the default itself should absorb the slower-hardware case.

## What Changes

- Raise the default backend-call timeout from **120 s to 300 s**. The `SUMMARY_TIMEOUT` env override (read at call time, non-numeric falls back to the default) is unchanged.
- The new default applies to every LLM backend call sharing the dispatch — primary Summarize (`POST /api/summarize`) and the benchmark preset call (`POST /api/llm-call`).
- Update the docs and code comments that state the 120 s sizing: `README.md` environment-variable table, `docs/summarize.md` + `docs/summarize.html`, `docs/model_discovery.md` + `docs/model_discovery.html`, and the pool comments in `app/main.py`.
- No UI, API, concurrency-bound, or output/input limit changes. The 2-worker `SUMMARIZE_EXECUTOR` bound is untouched; a call can now pin its worker for up to 300 s.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `transcript-summarization`: the backend-call timeout is now a stated requirement — default 300 s (connect + read), `SUMMARY_TIMEOUT`-overridable at call time, applied to both `POST /api/summarize` and `POST /api/llm-call`, with a timeout failure still surfacing as 502 `PROVIDER_ERROR` with the `timeout` reason.

## Impact

- **Code**: `app/summarize.py` (`DEFAULT_SUMMARY_TIMEOUT` constant + sizing comment), `app/main.py` (comments only).
- **Tests**: `tests/test_transcript_summarization.py` (new default-value assertion), `tests/test_llm_call_endpoint.py` (new assertion that the llm-call path uses the 300 s default); existing env-override and constant-referencing tests stay green.
- **Docs**: `README.md`, `docs/summarize.{md,html}`, `docs/model_discovery.{md,html}`.
- **Behavioral**: a hung (never-responding) backend now holds a pool worker and the HTTP request for up to 300 s instead of 120 s. With 2 shared workers, two hung backends can make subsequent LLM requests queue for several minutes — an accepted tradeoff, noted in design.
