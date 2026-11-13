# `app/model_discovery.py` — model discovery

## Purpose

The backend call behind the model-management UI's "Refresh from backend"
flow: an OpenAI-compatible `GET {baseURL}/models` request to a configured
provider, returning the list of model ids. Discovery is **advisory** — the
operator explicitly adds returned ids through the add endpoint, and a
discovery failure never alters the effective model list. The HTTP dispatch
lives in the module-level `_get_provider_models` seam (mirroring
`summarize._call_chat_completions`) so the e2e harness can replace that
function with a stub while `list_models` keeps running for real.

## Public surface

- `list_models(provider, timeout=None) -> list[str]` — the synchronous
  call; meant to run in a worker thread (the dedicated discovery executor in
  `main.py`).
- `discovery_timeout() -> float` — `MODEL_DISCOVERY_TIMEOUT` (default 15 s)
  read at call time; non-numeric values fall back to the default.
- `ModelDiscoveryError` — a failed /models call with machine-readable
  `reason` (`unreachable`, `timeout`, `http_error`, `malformed_response`)
  and a safe, app-constructed `detail`.
- Constants: `DEFAULT_DISCOVERY_TIMEOUT` (15.0), `MAX_DISCOVERED_MODELS`
  (200).

## Invariants

- **No FastAPI imports.** The call is a plain synchronous function, testable
  directly against a stubbed seam.
- **Plain HTTP via `requests`, per-call `requests.get`** — no shared session
  (thread-safe without locking), no SDK. The bearer token is attached only
  when the provider defines an `apiKey`.
- **Advisory only.** Discovery never writes: it surfaces ids for the UI to
  add via `POST /api/providers/{provider_id}/models`. Rejected: auto-adding
  every discovered model, so an unexpected backend cannot silently expand
  the picker.
- **Secrets stay server-side.** The response and every log event carry model
  id strings only — never the base URL, API key, or response body. Exception
  details are exception *type names* — `str()` of `requests` exceptions
  embeds the URL, which must stay out of the logs.
- **Bounded, filtered parse.** Only dict entries whose `id` is a non-empty
  string are kept; duplicates are removed preserving order; the list is
  capped at `MAX_DISCOVERED_MODELS` so a hostile or broken backend cannot
  flood the response.
- **Dedicated bounded executor.** Discovery runs on its own 2-worker pool in
  `main.py` rather than the summarize pool: a 300 s summarize must not block
  a fast /models call, and a hanging discovery must not starve
  summarization.
- **The file config decides the target.** The endpoint resolves the provider
  against the *file* config (unknown id → 400 `INVALID_PROVIDER`,
  backend-free); the overlay never changes which base URL is contacted.
- **Manual entry is the fallback.** If a backend has no (or a
  non-standard) `/models` endpoint, the UI's manual model-id entry always
  works — discovery is a convenience, not the only path.

## Log events emitted

- `provider_models_refreshed` (info): `provider`, `count`, `duration_ms`.
- `provider_models_refresh_failed` (error): `provider`, `reason`, `detail`.

## Error codes raised/handled

Raises `ProviderError` (502 `PROVIDER_ERROR`) when the call or the parse
fails; handles `ModelDiscoveryError` internally. The endpoint also returns
400 `INVALID_PROVIDER` for a provider id missing from the file config
(backend-free, before any /models call).

## Design decisions

From `add-summarization-model-management`:

- **D6** — a separate FastAPI-free module with its own seam, timeout env,
  failure taxonomy, and dedicated bounded executor; discovery is advisory
  (the rejected-alternative note: no auto-adding of discovered models).

## Cross-links

- [`providers.py`](providers.html) — the read-only file config that decides
  which base URL is contacted
- [`provider_overrides.py`](provider_overrides.html) — the add endpoint that
  persists ids the UI adds from the discovery list
- [`main.py`](main.html) — the `GET /api/providers/{provider_id}/available-models`
  route and the dedicated discovery executor
- [`summarize.py`](summarize.html) — the sibling backend module whose seam
  and failure taxonomy this module mirrors
