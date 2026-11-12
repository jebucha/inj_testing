# `app/provider_overrides.py` — provider overrides store

## Purpose

The writable overlay for UI-added model ids: per-request read and atomic
write of `provider_overrides.json` in the transcript directory, the pure
merge of that overlay into a file-read provider config, and the
read-modify-write add/remove operations behind the model-management
endpoints. The overlay extends the model lists of providers defined in the
read-only `providers.json` — it never introduces a provider, a base URL, or
an API key.

## Public surface

- `overrides_path() -> Path` — `provider_overrides.json` in the transcript
  directory, resolved at call time.
- `load_overrides() -> dict[str, list[str]]` — tolerant per-call read
  (missing file → `{}`; unreadable/malformed → `{}` + one log event).
- `apply_overrides(config, overrides) -> ProviderConfig` — pure merge:
  file models first, then non-duplicate overlay ids; the overlay ids
  actually used are carried in `Provider.added_models`.
- `add_model(provider_id, raw_model) -> (model, effective models)` —
  read-modify-write of an overlay addition under the module lock.
- `remove_model(provider_id, raw_model) -> (model, remaining models)` —
  read-modify-write of an overlay removal under the module lock.
- `validate_model_id(raw) -> str | None` — the id rules, applied to the
  trimmed value.
- `ProviderOverridesWriteError` — the atomic write failed (already logged).
- `ModelNotInOverlayError` — the id is in neither the config file nor the
  overlay (the endpoint maps it to 404 `NOT_FOUND`).
- Bounds: `MAX_MODEL_ID_CHARS` (200), `MAX_ADDED_PER_PROVIDER` (50).

## Invariants

- **No FastAPI imports.** Reader, merge, and writer are pure over
  `persist.transcript_dir()` so they are testable directly against
  `tmp_path`.
- **Overlay scope.** The provider set comes only from the file config:
  overlay keys for unknown providers are ignored (and left on disk). An
  overlay can only extend a file provider's model list.
- **Merge order and provenance.** Effective `models` are the file models in
  order, followed by overlay ids not already present (first occurrence
  wins); `added_models` carries exactly the overlay ids used, in the order
  they appear in `models`, so the listing can expose them as removable.
- **Id rules.** A model id is the trimmed value of a client string:
  non-empty, at most `MAX_MODEL_ID_CHARS` characters, free of control
  characters. Each provider holds at most `MAX_ADDED_PER_PROVIDER` overlay
  additions.
- **Adding is idempotent.** Re-adding an id already in the effective list
  is a no-op (no write, no event, no duplicate). Removing targets overlay
  ids only: a config-file model raises `ModelNotRemovableError`, an id in
  neither set raises `ModelNotInOverlayError`.
- **Read per call, never cached.** Edits on disk take effect on the next
  request without a restart. A missing file is the normal "no additions"
  state with *no* log entry.
- **Atomic writes, process-local lock.** Read-modify-write runs under a
  module-level lock; the write goes to a sibling temp file followed by
  `os.replace` (the `settings.save_settings` pattern), so a crash mid-write
  never leaves a truncated file. A single uvicorn process is the supported
  deployment; multi-process coordination (an OS file lock) is a documented
  non-goal.
- **The file is invisible to the transcript list.** `list_transcripts()`
  lists `.txt` files only, so `provider_overrides.json` never appears in
  `GET /api/transcripts`.

## Log events emitted

- `provider_overrides_load_failed` (error): `path`, `reason`
  (`invalid_json`, `invalid_structure`, or the OS exception type name),
  `detail` (the parse error — never file contents).
- `provider_overrides_save_failed` (error): `path`, `reason`, `detail`.
- `provider_model_added` (info): `provider`, `model`.
- `provider_model_removed` (info): `provider`, `model`.

No event carries an API key, a base URL, the transcript text, or the full
model list.

## Error codes raised/handled

Raises `InvalidModelError` (400 `INVALID_MODEL`, bad id or cap overflow),
`InvalidProviderError` (400 `INVALID_PROVIDER`, defensive re-check of the
provider against the file config), `ModelNotRemovableError` (400
`MODEL_NOT_REMOVABLE`), `ModelNotInOverlayError` (endpoint maps to 404
`NOT_FOUND`), and `ProviderOverridesWriteError` (endpoint maps to 500
`WRITE_FAILED`).

## Design decisions

From `add-summarization-model-management`:

- **D1** — a separate writable overlay file, not a writable `providers.json`
  (secret-bearing, read-only-mounted, operator-authored) and not an
  extended `settings.json` (whose `save_settings` is a blind whole-file
  overwrite).
- **D2** — the effective config is file config plus overlay, with provenance
  carried on `Provider.added_models`; the merge lives here, not in
  `providers.py`, keeping the pure file reader single-purpose.
- **D3** — read-modify-write under a module-level lock with atomic replace;
  only overlay ids are removable.
- **D5** — the validation and bounds live here, next to the store they
  protect.

## Cross-links

- [`providers.py`](providers.html) — the read-only file config this overlay
  extends, and the `Provider` / `ProviderConfig` structures it merges
- [`model_discovery.py`](model_discovery.html) — live model discovery
  against a configured provider's `/models`
- [`main.py`](main.html) — the add/remove/discover endpoints and the
  merged-config validation in `GET /api/providers` and `POST /api/summarize`
- [`settings.py`](settings.html) — the sibling writable-JSON pattern
  (per-request read, temp file + `os.replace`)
- [`persist.py`](persist.html) — `transcript_dir()`, where the overlay lives
