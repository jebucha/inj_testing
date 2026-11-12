# Proposal

## Why

The repository was renamed to `inj_testing` (the GitHub remote is already
`ssh://git@github.com/jebucha/inj_testing`), and the app has grown from a
YouTube-transcript fetcher into a prompt-injection testing harness, but the
project's self-identifying name everywhere else is still `yt-transcript`:
the compose image/container name, the uv project name, the FastAPI title,
the docs branding, and the README's deployment commands. Operators, docs,
and tooling metadata disagree with the actual project identity.

## What Changes

- Rename all live, project-named identifiers from `yt-transcript` to
  `inj-testing`:
  - `docker-compose.yml`: `image:` and `container_name:` (plus header and
    comment references, including the `/etc/yt-transcript/providers.json`
    VPS example path)
  - `pyproject.toml` project name, with `uv.lock` regenerated via `uv lock`
  - `app/main.py` `FastAPI(title=...)` (OpenAPI docs title)
  - `app/fetchers.py` temp-directory prefix
  - `Dockerfile` header comment
  - `app/static/index.html` page title (confirmed with the user: the browser
    tab title becomes `inj-testing` even though it previously described the
    feature)
  - `README.md` `# yt-transcript` document heading, deployment one-liners,
    the prose fixed-container-name mention, `docker logs` examples, and the
    `/etc/yt-transcript/providers.json` example path
- Regenerate code docs: update the `docs/generate.py` shell template and the
  `docs/*.md` source files that name the project, then regenerate all
  committed HTML pages deterministically via `uv run python docs/generate.py`
  (including the `docs/style.css` comment).
- **BREAKING (operational, not API):** the compose image and container are
  renamed. An existing deployment has a running `yt-transcript` container
  that compose will not manage under the new name; the README's `###
  Compose (primary)` section gains a migration note (remove the
  old-named container, then rebuild and re-run). No HTTP API, data
  format, or behavior changes.
- Deliberately **not** renamed (out of scope, confirmed with the user):
  - `openspec/changes/archive/**` — historical record of past changes that
    cite the name as it was at the time
  - `security-audits/run-1/**` — reports about the older, separate
    `yt_transcript` repository and checkout
  - `/var/lib/yt-transcripts` — a plural directory name meaning
    "transcripts", a different concept from the project name

## Capabilities

### New Capabilities

(None — no new behavior; `skip_specs: true` is set in `.openspec.yaml`.)

### Modified Capabilities

(None — no spec-level requirement changes; none of the ten existing
capabilities reference the project name.)

## Impact

- Files: `docker-compose.yml`, `pyproject.toml`, `uv.lock`,
  `app/main.py`, `app/fetchers.py`, `Dockerfile`, `app/static/index.html`,
  `README.md`, `docs/generate.py`, `docs/style.css`, four `docs/*.md`
  source files, and the 20 regenerated `docs/*.html` outputs.
- No API, database, or runtime behavior change; no dependency change.
- Existing containerized deployments must follow the one-time migration
  note (remove the old-named container, rebuild, re-run).
- Version: minor bump per the AGENTS.md pre-archive convention (user-visible
  naming change).
