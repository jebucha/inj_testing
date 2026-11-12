# Tasks

## 1. Project tooling identifiers

- [x] 1.1 Change `name = "yt-transcript"` to `name = "inj-testing"` in `pyproject.toml`, run `uv lock` to regenerate the lock, and verify the `uv.lock` diff contains only the project name line (`git diff uv.lock`) and `uv sync` completes cleanly
- [x] 1.2 Rename the `FastAPI(title=...)` value in `app/main.py` to `inj-testing` and verify `uv run python -c "from app.main import app; assert app.title == 'inj-testing'"` exits 0
- [x] 1.3 Change the temp-directory prefix in `app/fetchers.py` from `yt-transcript-` to `inj-testing-` and verify `grep -rn 'yt-transcript' app/ --exclude-dir=__pycache__` returns nothing (stale `.pyc` bytecode is excluded until regenerated)

## 2. Compose, Dockerfile, and UI title

- [x] 2.1 Rename `image:`, `container_name:`, the header comment, and the `/etc/yt-transcript/providers.json` example path in `docker-compose.yml` to the `inj-testing` equivalents and verify `docker compose config` (or `podman compose config` where docker is unavailable) renders the file with the new names
- [x] 2.2 Update the `Dockerfile` header comment from `yt-transcript` to `inj-testing` and verify `grep -n 'yt-transcript' Dockerfile` returns nothing
- [x] 2.3 Change `<title>YouTube Transcript</title>` in `app/static/index.html` to `inj-testing` and verify the e2e UI tests still pass (`uv run python -m pytest tests/e2e/test_ui.py -q`); update any test that asserted the old title, in this same task

## 3. Code docs (regenerable)

- [x] 3.1 Update the two `yt-transcript` strings in the `docs/generate.py` page template and the project name in the four `docs/*.md` sources (`index.md`, `deploy/compose-yml.md`, `deploy/Dockerfile.md`, `providers-json-example.md`) plus the `docs/style.css` comment, and verify `grep -rn 'yt-transcript' docs/` returns only hits inside generated `.html` files (not in `.md` or `generate.py`)
- [x] 3.2 Regenerate the committed HTML with `uv run python docs/generate.py` and verify the `docs/**/*.html` diff against the pre-change baseline contains only the `yt-transcript` → `inj-testing` substitutions (no unrelated drift; the generator is deterministic)

## 4. README

- [x] 4.1 Rename all live `yt-transcript` references in `README.md` (build/run one-liners for docker and podman, `docker logs` examples, the `/etc/yt-transcript/providers.json` VPS example) to `inj-testing` and verify `grep -nE 'yt-transcript([^s]|$)' README.md` returns nothing (the plural-aware pattern does not match the plural `/var/lib/yt-transcripts` directory example, which stays)
- [x] 4.2 Add a one-time migration note to the README `### Compose (primary)` section (under `## Build and run`) for the container rename: remove the orphaned old-named container with `docker rm -f yt-transcript` / `podman rm -f yt-transcript`, then rebuild and start with `docker compose up -d --build`. Verify the note appears in that section and its commands are consistent with the surrounding runbook

## 5. Integration verification

- [x] 5.1 Re-grep the whole tree for the singular project name, excluding `.git`, `.venv`, `__pycache__`, `openspec/changes/archive/`, this change's own directory `openspec/changes/rename-to-inj-testing/` (its proposal/design/tasks/audits quote the old name as the rename source), and `security-audits/`, and verify zero remaining live references. Use a pattern that does not match the plural data-directory name (e.g. `grep -rnE 'yt-transcript([^s]|$)'`), so the by-design plural `/var/lib/yt-transcripts` is not a hit
- [x] 5.2 Run the full test suite (`uv run python -m pytest tests/ -q --ignore=tests/e2e` and `uv run python -m pytest tests/e2e/ -q`) and verify all tests pass
- [x] 5.3 Smoke test the renamed deployment per the README: `docker compose up -d --build` (podman equivalents where docker is unavailable), verify the container `inj-testing` reports healthy, the UI returns 200, and `docker logs inj-testing` shows the startup lines

## 6. Pre-archive

- [x] 6.1 Bump the version before archiving: `uv version --bump minor` (per AGENTS.md — user-visible naming change) and verify `pyproject.toml`'s `version` advanced one minor

## Implementation notes

- **Scope expansion 1 — healthcheck form (user-approved).** `docker-compose.yml` now declares the healthcheck in the `CMD-SHELL` (string) form instead of the exec `CMD` array, with an in-file comment explaining why. Probe semantics are unchanged (urlopen raises on 4xx/5xx and connection failure). Reason: this host's `docker compose` is moby docker-compose 2.26.1 talking to podman's docker-compat API, and that client mangles the exec-form healthcheck into a broken shell string (observed three different mangled forms across runs; the container reported unhealthy). Raw `containers/create` API calls against the podman socket preserve the exec form intact, so the mangle is client-side compose behavior, not podman. The `CMD-SHELL` string passes through verbatim and the container reports healthy. The bug reproduces with the latest upstream compose (v5.7.1, tested via a user-level plugin override, then removed), so no client upgrade fixes it; the string form is the durable workaround and behaves identically under real docker.
- **Scope expansion 2 — podman environment (user-approved).** Enabled the `podman.socket` systemd user unit (`systemctl --user enable --now podman.socket`); previously it was disabled, so the socket at `/run/user/1000/podman/podman.sock` only existed if a service was started manually, and `docker compose` was broken after a reboot. No package changes: podman 5.4.2 is the newest in Debian trixie, and the compose client stays the distro's 2.26.1.
- **5.1 disclosure.** Three remaining `yt-transcript` grep hits in `README.md` are intentional: the one-time migration note must name the old container (`docker rm -f yt-transcript`) so existing users can remove it.

## Workflow follow-up

- Validate in a fresh session with a model that did not write the code, then archive.
