# Design

## Context

`app/summarize.py` holds a single constant, `DEFAULT_SUMMARY_TIMEOUT = 120.0`, consumed by `summary_timeout()`, which resolves the `SUMMARY_TIMEOUT` env override at call time (non-numeric values fall back to the default). Both LLM paths — `summarize_with_provider` (`POST /api/summarize`) and `call_with_preset` (`POST /api/llm-call`) — pass that value into `_call_chat_completions`, so a single constant edit resizes both. The 120 s figure was sized for fast LAN 27B-class hardware (see archived `add-transcript-summary` design); a slower real-world host (LM Studio serving a 35B-class model) produced a `llm_call_failed … [timeout]` at exactly 120 s while the model was still producing a valid result.

## Goals / Non-Goals

**Goals:**
- Slow local inference machines complete summarization and benchmark calls without an env workaround.
- Keep the existing `SUMMARY_TIMEOUT` override semantics untouched (read at call time, non-numeric falls back).

**Non-Goals:**
- No per-provider or per-call timeout configuration (deferred; see Decisions).
- No change to the 2-worker `SUMMARIZE_EXECUTOR` bound, output token cap, or input cap.
- No UI changes (including not distinguishing the benchmark's error text).

## Decisions

1. **Raise the shared default constant to 300.0** rather than adding a second default for the benchmark path. Both paths share `_call_chat_completions` and the same hardware; the timeout is a property of the machine, not of the feature.
2. **300 s, not "no timeout" or a much larger value.** A non-responding backend is still a failure that must eventually surface as a 502 so the UI can show the retry banner; 300 s is roughly 2.5× the observed worst-case on the slow host and keeps the hung-backend blast radius (see Risks) bounded and predictable.
3. **Keep the env override as the escape hatch in both directions.** Hosts that need longer (or shorter) timeouts use `SUMMARY_TIMEOUT`; no code path branches on the value.
4. **Update all prose that states 120 s** (`app/main.py` pool comments, `README.md`, `docs/summarize.{md,html}`, `docs/model_discovery.{md,html}`) so docs and code cannot drift apart — the project treats those docs as mirrors of the code.

## Risks / Trade-offs

- [A hung backend now pins a pool worker and the HTTP request for up to 300 s instead of 120 s] → With the 2-worker shared pool, two hung calls can make subsequent LLM requests queue for several minutes. Accepted: the pool is already bounded and queued requests wait rather than fail; the README documents the env var for hosts that want a tighter cap.
- [Operators on fast hardware lose the faster failure signal (3× longer to confirm a dead backend)] → The failure log event still carries `reason=timeout` and `duration_ms`, and the `SUMMARY_TIMEOUT` override restores the 120 s behavior per host.
- [Docs/comments in already-archived changes still say 120 s] → Intentionally untouched: archived changes are historical records, not living documentation.

## Migration Plan

Single commit: constant + comments + docs + two tests. No config, data, or API migration; `SUMMARY_TIMEOUT` deployments are unaffected. Rollback is reverting the commit. Per the project convention, this ships a user-visible change, so the app's minor version is bumped with `uv version --bump minor` before archive.

## Open Questions

(None)
