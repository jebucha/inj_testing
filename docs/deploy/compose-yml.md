# `docker-compose.yml` — declarative single-service deployment

## Purpose

The Compose file that turns a local or VPS checkout into a running inj-testing
instance in one command (`docker compose up -d --build`). Single service, no
profiles, no build args — deliberately scoped to the subset supported by both
Docker Compose v2 and podman-compose for parity.

## Public surface

- **Service name:** `app` (the only service)
- **Container image:** `inj-testing` (built from `./`)
- **Container name:** `inj-testing` (fixed, matches non-compose usage)
- **Host-side knobs** (via uncommitted `.env` file):

  | Variable | Default | Maps to | Notes |
  |----------|---------|---------|-------|
  | `PORT` | `8000` | Port mapping `${PORT:-8000}:8000` | Host port only; container always listens on 8000 |
  | `TRANSCRIPTS_DIR` | `/home/john/transcripts` | Volume mount `${...}:/transcripts` | Writable host directory; app never creates it |
  | `PROVIDERS_CONFIG` | `./providers.json` | Read-only volume `${...}:/app/providers.json:ro` | JSON config file kept out of git |

- **Container-side environment:** the uncommitted `env` file (a separate,
  git-ignored file — *not* `.env`) is passed into the container with
  `env_file:` so the variables named by the mounted `providers.json`'s
  `options.apiKeyEnv` resolve from the container's process environment
  (`app/providers.py`, per-request resolution). It holds container-side
  variables only (API-key values). The short list form is used (the long form
  with `required: false` is docker-compose-only; see decision 4). No
  `environment:` block is used — see the env-file separation invariant.

- **Healthcheck:** python urllib probe against `http://127.0.0.1:8000/`
  - interval 30s, timeout 5s, retries 3, start_period 5s
- **Log rotation:** json-file driver, max-size 10m, max-file 3 (max ~30 MB)

## Invariants

- **Host/container port decoupling.** The container always binds 8000 regardless
  of `PORT`. This keeps the healthcheck simple (hardcoded to 8000) and prevents
  a mismatch between mapped host port and logged `server_started` port.
- **Container-side paths are fixed.** `/transcripts`, `/app/providers.json` —
  only the host side is overridable via `.env`. A future change that remaps
  container paths must update both the volume mount *and* healthcheck address.
- **`.env` never committed.** It contains machine-local host-side overrides;
  tracked in `.gitignore` (`.env`). It is optional (pure interpolation input;
  both implementations tolerate its absence) and is never passed into the
  container.
- **`env` holds only container-side variables; `env` required.** The `env`
  file (git-ignored) carries the `apiKeyEnv` tokens and nothing else — no
  host-side knobs. Because it is listed in `env_file:`, a missing `env` is a
  hard error for both compose implementations — create it (an empty file is
  fine) before the first `up`.
- **No `environment:` block in this file.** podman-compose v1 feeds a
  service's `environment:` values back into the `${...}` substitution of the
  whole compose file (its `rec_subs`), so pinning a container-side value like
  `PROVIDERS_CONFIG=/app/providers.json` would corrupt the host-side volume
  source (`/app/providers.json:/app/providers.json:ro` → `statfs` failure).
  Container-side values are fixed by the Dockerfile's `ENV` block instead.
  A future change that needs container-side overrides must find a form that
  behaves identically under both implementations.
- **Single-instance only.** The fixed `container_name: inj-testing` means two
  compose projects on one host cannot coexist — acceptable for a single-user
  self-hosted tool.
- **Read-only config mount.** `/app/providers.json` is mounted `ro`; the app's
  per-request config read never modifies it.

## Log events emitted

N/A — this file emits nothing. However, it controls operational behavior:
- Healthcheck failures surface as container restarts (3 retries then down)
- Log rotation limits how much structured log data accumulates (~30 MB max)
- The healthcheck probe (`/`) returns 200 when the static UI is served — this
  confirms the app process is alive but does *not* verify the fetch chain works

## Error codes raised/handled

Failure modes and their observable effects:
- **Missing `env`** — `up` fails in both implementations: compose v2 rejects
  at config load ("env file … not found"), podman-compose rejects at
  container creation ("Env file at … does not exist"); create the file (even
  empty) next to the compose file
- **Port conflict on host** (EADDRINUSE) — compose logs show bind failure; fix by
  changing `PORT` in `.env` or killing the conflicting process
- **Missing TRANSCRIPTS_DIR** on host — container starts but transcript saves fail
  silently with a `config_load_failed` event logged by the app (best-effort behavior)
- **Missing or invalid providers.json** — app emits `config_load_failed`; summarization
  endpoints return `NOT_CONFIGURED`; UI provider picker remains empty; fetch still works

## Design decisions

Resolved from `2026-10-29-add-docker-compose`:
- **decision 1** — host/container port decoupling (`${PORT:-8000}:8000`); keeps healthcheck address hardcoded and unambiguous
- **decision 2** — python urllib probe instead of curl (no curl in slim image) or new `/health` endpoint (out of scope for a compose-only change)
- **decision 3** — json-file log rotation (10m × 3); prevents unbounded VPS disk growth from structured JSON log lines
- **decision 4** — plain compose v2, no `version:` key; filename chosen for podman-compose compatibility over the newer `compose.yaml` convention
- **decision 5** — fixed container name for single-instance assumption and smoke-test parity with documented `docker run` usage

Also from later changes:
- `add-transcript-summary` — provider config mount path `/app/providers.json` aligns with the app's runtime default; summary provider listing endpoint is secret-free (no keys exposed via compose)
- **`env_file:` on a dedicated `env` file, no `environment:` pins** — the
  git-ignored `env` file (the operator env file already reserved in
  `.gitignore` by the `provider-apikey-env` change) is passed into the
  container so `options.apiKeyEnv` variables (live tokens) resolve from the
  container process environment, without any app-side env-file loading (that
  change's operator-side-wiring non-goal). A dedicated file — rather than
  reusing `.env` plus `environment:` pins — is what keeps the two
  implementations in step: podman-compose v1's `rec_subs` substitutes a
  service's `environment:` values into the whole file, which would rewrite
  the host-side `PROVIDERS_CONFIG` volume source to the container path
  (`statfs` failure at `up`); and passing `.env` itself into the container
  would leak host-side knobs (`PORT`, `PROVIDERS_CONFIG`) into the app
  process, breaking decision 1's healthcheck and the fixed config mount
  point. The Dockerfile `ENV` block fixes the container-side values;
  short-list `env_file:` form only, per decision 4's compatibility
  constraint

## Cross-links

- [`Dockerfile`](Dockerfile.html) — builds this image (`build: .`)
- [`providers.json.example`](../providers-json-example.html) — config file shape for the mounted volume
- [`app/providers.py`](../providers.html) — reads `PROVIDERS_CONFIG` per request inside the container
- README.md → Deployment section (quick start, podman commands)
