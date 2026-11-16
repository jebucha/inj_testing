# Design

## Context

`app/providers.py` reads the operator-owned provider config file on every request (never at startup, never cached) and yields a frozen `Provider` dataclass whose `api_key` field is today either a literal string from `options.apiKey` or `None`. The summarize backend attaches the key as a bearer token when present. The module is deliberately FastAPI-free and pure over the config path so it is testable against `tmp_path`. Secrets discipline: file contents and key values never appear in logs or HTTP responses; `GET /api/providers` already excludes `api_key` and `base_url`.

See proposal.md for the motivation (env-file-based secrets, no token duplication into the config file).

## Goals / Non-Goals

**Goals:**
- Allow a provider entry to source its bearer token from a named environment variable.
- Keep the reader pure and FastAPI-free; keep per-request reading with no caching.
- Preserve all existing secret-free guarantees for env-derived keys.
- Zero new runtime dependencies.

**Non-Goals:**
- Loading an env file inside the application (operator-side wiring only: `env_file:` in compose, shell export, or CI secrets).
- Shell-style interpolation or variable composition in any other config field (`baseURL` etc. stay literal).
- Any change to the `provider_overrides.json` overlay (it cannot introduce or change API keys, by existing spec).
- Compose/Dockerfile changes.

## Decisions

**Decision numbering note:** existing code comments in `app/providers.py` (module docstring) and `app/main.py` (`providers_endpoint`) cite "design decision N" referring to the archived `add-transcript-summary` design, where numbers 2 and 3 denote different decisions. New comments added by this change cite this design's decisions by name (for example "keyless degradation"), not by number.

1. **Syntax: sibling field `options.apiKeyEnv`, not interpolation.**
   The field is a string naming an environment variable, read next to the existing `options.apiKey`. A literal key and an env reference are syntactically distinct, so a key that happens to look like `${SOMETHING}` is never misinterpreted, and `apiKey` keeps its exact current type and semantics.
   *Alternatives:* `${VAR}` interpolation inside `apiKey` (familiar, but turns any literal with that shape into a reference and hides which values are secrets); a top-level per-provider field outside `options` (inconsistent with where all other connection options live).

2. **Resolution at parse time in the existing reader; the app never reads an env file.**
   `apiKeyEnv` is resolved against `os.environ` inside `_parse_provider`, so resolution happens on every config read, reusing the existing per-request flow. The `Provider` dataclass is unchanged — `api_key` simply holds the resolved value.
   *Alternatives:* add `python-dotenv` and load an env file in-app (new pinned dependency, blurs the line between app config and deployment secrets, and would need its own reload semantics on top of the per-request file read).

3. **Unset or empty variable → keyless provider plus one warning event.**
   The provider stays in the usable list with `api_key = None` (identical to the existing keyless-backend path, which then sends no auth header), and the reader logs one warning event — `provider_api_key_env_missing` — carrying `provider` (the provider id) and `variable` (the variable name). No key value, variable name aside, ever reaches the log.
   *Alternatives:* drop the provider as unusable (a single typo'd variable name would silently remove a provider from the UI); fail the whole config load (one misspelled variable takes out every provider, contradicting the "unknown fields are ignored" tolerance the format already has).

4. **Precedence: `apiKeyEnv` wins over a literal `apiKey`.**
   When both are present the env value is the effective key. The literal is not consulted, and no error is raised — operators migrating a key out of the file can remove the literal in the same edit, and a leftover literal is inert rather than a conflict.
   A non-string `apiKeyEnv` value (wrong type) is ignored, falling back to the literal `apiKey` or `None`, consistent with the reader's existing degrade-don't-raise posture for malformed option values.

5. **Logging shape follows the module's existing pattern.**
   The warning goes through the same `get_logger()` structured extra-kwargs pattern as `config_load_failed`, at warning level, so it is visible in the existing log stream and viewer without any new plumbing.

## Test Strategy

- The `app/providers.py` reader is unit-tested against `tmp_path` with the process environment monkeypatched (no FastAPI, no network): `apiKeyEnv` resolution, precedence over the literal `apiKey`, keyless degradation with the warning event, and the non-string fallback (tasks 1.1–1.6).
- The listing assertion for env-derived keys is exercised through `GET /api/providers` (task 1.6).
- Every spec scenario carries a Test Requirement block (id/file/command/pass); each command is a single-test invocation expected to finish within the 120-second per-block timeout.
- Integration gate: the full non-e2e suite `uv run python -m pytest tests/ -q --ignore=tests/e2e` (task 3.1). No UI changes in this change, so the e2e suite is unaffected.
- All commands run through `uv run` in the locked uv environment (see AGENTS.md).

## Risks / Trade-offs

- [Operator typos the variable name] → the provider goes keyless and backend calls 401. Mitigated by the `provider_api_key_env_missing` warning naming the exact variable, and by the keyless provider remaining visible in the UI (it is not hidden).
- [Env values are fixed at process start, while the config file hot-reloads per request] → changing only the variable's value requires a container restart even though editing the file does not. Inherent to process-environment semantics; documented in `docs/providers.md` so operators are not surprised.
- [Two ways to supply a key create a "which one counts" question for reviewers] → precedence is explicit (env wins) and covered by a spec scenario; the example file shows one style at a time.
- [A resolved secret now lives in the `Provider` dataclass the same way a literal does] → no new exposure surface: the dataclass never enters logs or responses, and `GET /api/providers` is already secret-free by spec (re-asserted by the new listing scenario).

## Migration Plan

Purely additive; no data migration. Existing config files (literal `apiKey`, or keyless) keep working unchanged. An operator migrates by:

1. Replacing `"apiKey": "<value>"` with `"apiKeyEnv": "<VAR>"` in their (uncommitted) `providers.json`.
2. Ensuring `<VAR>` is in the process environment (e.g. compose `env_file:` or shell export) — operator-side, outside this change.
3. Restarting the app if the variable itself is not already set.

Rollback: revert the code change; any config using `apiKeyEnv` simply degrades to keyless under the old code (unknown fields are ignored), and configs using literal keys are unaffected either way.
