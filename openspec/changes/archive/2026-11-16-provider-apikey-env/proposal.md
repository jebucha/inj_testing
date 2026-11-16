# Proposal

## Why

The provider config file (`providers.json`, operator-owned and read-only) currently only supports a literal `options.apiKey` string, so a bearer token must be written into the file the operator keeps out of git. Operators who already manage secrets in an env file (exported or wired into the deployment environment) have to duplicate the token by hand into the config file whenever it changes.

## What Changes

- The provider config file format gains an optional `options.apiKeyEnv` field: a string naming an environment variable whose value is used as the bearer token for that provider.
- When `apiKeyEnv` is present it takes precedence over a literal `apiKey`; the variable is resolved from the process environment at config-parse time (per request, with the existing no-caching read).
- An unset or empty variable degrades the provider to keyless (usable, backend call carries no auth header) and logs a warning event carrying the provider id and variable name — never any value.
- A resolved env-derived key is subject to the same secret-free guarantees as a literal key: it never appears in `GET /api/providers`, logs, or HTTP responses.
- `providers.json.example` and the docs (`docs/providers.md`, README) are updated with the new field; `.gitignore` gains an entry for the operator env file (`env`), which currently holds a live token untracked and unprotected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `transcript-summarization`: a new "Provider API key from environment" requirement is added (env-var reference, precedence over literal `apiKey`, keyless degradation with log event when the variable is unset or empty), and the existing "Provider configuration file" requirement is updated to include the optional `options.apiKeyEnv` field in the config-file format description.

## Impact

- `app/providers.py` — `apiKeyEnv` resolution in the provider parser; new warning log event.
- `tests/` — unit tests for resolution, precedence, and unset/empty degradation (existing `tests/test_transcript_summarization.py` area).
- Docs: `docs/providers.md`, `docs/providers-json-example.md`, `README.md`, `providers.json.example`; `.gitignore` (entry for `env`).
- No new dependencies, no API response shape changes, no compose/Dockerfile changes (env-file wiring is operator-side, outside this change).
