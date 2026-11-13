# Proposal

## Why

The benchmark's `POST /api/llm-call` endpoint validates the provider/model pair against the `providers.json` file config only, while the benchmark model and judge pickers are built from the effective config (file config plus the UI-added model overlay). Every model added through model management is therefore offered for selection but rejected with a 400 `INVALID_PROVIDER` the moment it is used — as the model under test the run shows only the "no longer configured" error and skips the judge; as the judge the summarize pass completes but the judge pass never runs (recorded as "unavailable"). The benchmark is unusable for all UI-added models. The model-management change (2026-11-12) made the merged config the single source for the listing and `POST /api/summarize` but never audited `/api/llm-call`, the other provider-validating endpoint.

## What Changes

- `POST /api/llm-call` validates the provider/model pair against the effective provider config (file config plus overlay), exactly as `POST /api/summarize` already does. UI-added models are accepted exactly like file models, for both the `summarize` and `judge` presets.
- The overlay's scope is unchanged: it still cannot introduce a provider, base URL, or API key, so the endpoint's SSRF boundary (server only addresses operator-configured base URLs) is untouched.
- A regression test proves an overlay-added model is accepted by the endpoint and sent to the backend under its configured base URL.
- No UI change: the pickers already offer overlay models; the rejection disappears.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `prompt-injection-benchmark`: the "Non-persisting preset provider-call endpoint" requirement gains an explicit obligation that the provider/model pair is validated against the effective (merged) provider config, with a new scenario for a UI-added (overlay) model being accepted and a backend call made.

## Impact

- Code: `app/main.py` — `llm_call_endpoint` switches from `load_providers()` to the same merged-config helper the summarize endpoint uses; no other endpoint is affected (add/remove/discovery endpoints deliberately stay file-only).
- Tests: `tests/test_llm_call_endpoint.py` — one new acceptance test following the existing `test_summarize_accepts_added_model` pattern.
- Spec: delta to `prompt-injection-benchmark` (one modified requirement, one added scenario + Test Requirement).
- No API shape, error-code, config-format, or UI changes; no version-visible behavior beyond the bug fix.
