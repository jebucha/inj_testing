# Design

## Context

See proposal.md for motivation. Current state that shapes the approach:

- `app/main.py` already composes the effective config via the `_merged_provider_config()` helper (`apply_overrides(load_providers(), load_overrides())`) in `GET /api/providers` and `POST /api/summarize`; the benchmark pickers are built from that merged listing.
- `llm_call_endpoint` is the only provider-validating endpoint still on raw `load_providers()`, so it rejects exactly the pairs the UI offers — a file/overlay split that no other request path has.
- The overlay (design D2 of the archived `add-summarization-model-management` change) carries model ids only: it can never change a provider's base URL or API key, and it cannot introduce a provider.

## Goals / Non-Goals

**Goals:**
- Make `POST /api/llm-call` accept the same provider/model pairs as `POST /api/summarize` and the pickers, so UI-added models work as the model under test and as the judge.
- Keep the SSRF boundary intact: the server still only addresses operator-configured base URLs.

**Non-Goals:**
- No change to which endpoints validate against the file config deliberately: the add/remove endpoints require the provider to exist in the file (the overlay never introduces providers), and discovery resolves the base URL from the file config.
- No UI, error-code, preset-registry, or config-format changes.
- No behavior change for file-config models or for unknown provider/model rejections (still 400 `INVALID_PROVIDER`).

## Decisions

### D1: Validate against the merged config, reusing the existing helper

`llm_call_endpoint` switches `config = await asyncio.to_thread(load_providers)` to `config = await asyncio.to_thread(_merged_provider_config)` — the same composition `summarize_endpoint` uses — and carries the same "merged config is the single source" comment. The rest of the endpoint (rejection order, executor, response shape) is untouched.

- *Rejected: special-case overlay ids in the check.* It would duplicate the merge logic per endpoint and recreate the drift that caused this bug; the helper is the one-line, already-tested composition.
- *Rejected: validate file-only and tell the UI to hide overlay models from the benchmark pickers.* The model-management capability's purpose is to extend the selectable set for configured providers; hiding them from the benchmark defeats the feature and would split the two pickers' option lists from the summarize picker.

### D2: No security-surface change, stated as a testable consequence

Because `apply_overrides` never alters `base_url`/`api_key` (provider set and credentials come only from the file config), accepting overlay model ids cannot widen which URLs the server addresses. The new regression test asserts the backend stub was invoked with the provider's configured base URL for an overlay model — pinning that consequence.

## Risks / Trade-offs

- [An overlay id that the backend does not actually serve now reaches the backend] → The backend's own 4xx surfaces as 502 `PROVIDER_ERROR` with `llm_call_failed`, the same path as any mistyped file model; the overlay's own bounds (≤200 chars, ≤50 per provider, no control chars) already bound the id space.
- [Another endpoint later regresses the same file/overlay split] → The merged helper is now the composition used by every provider-consuming request path; future provider-aware endpoints should follow the `summarize_endpoint` pattern.

## Migration Plan

None. Deploy the new image; existing overlays (e.g. `provider_overrides.json`) start working with the benchmark immediately, and removing them is unchanged. Rollback is redeploying the previous image, which restores the (buggy) file-only validation with no data changes.
