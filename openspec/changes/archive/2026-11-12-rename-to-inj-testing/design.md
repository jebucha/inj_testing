# Design

## Context

The project is named `yt-transcript` in its tooling and docs, while the git
remote is already `jebucha/inj_testing` and the app is now a
prompt-injection testing harness (see proposal.md — Why). No functional
default in code depends on the name: `grep -rn 'etc/yt-transcript'` over the
Python sources finds nothing (the `PROVIDERS_CONFIG` default is the
working directory's `providers.json`), and none of the ten capabilities in
`openspec/specs/` reference the name. The rename is therefore purely
identifier/branding work with no *functional* behavior change (the only
user-visible effect is the renamed tab title).

## Goals / Non-Goals

**Goals:**

- Every live, project-named identifier reads `inj-testing`.
- Docs stay regenerable: committed HTML always derives from the Markdown
  sources via `docs/generate.py`, never edited by hand.
- An existing deployment can migrate with one documented step and can
  roll back cleanly.

**Non-Goals:**

- No API, data-format, or runtime behavior changes.
- No rewriting of historical records (archived OpenSpec changes,
  security-audit reports) — see decision 1.
- No rename of the plural data-directory name `yt-transcripts`.

## Decisions

1. **Rename only project-named identifiers; leave historical records
   untouched.** `openspec/changes/archive/**` cites `yt-transcript` as the
   name *at the time of those changes* — rewriting it falsifies the record.
   `security-audits/run-1/**` targets a different, older artifact: the
   `yt_transcript` (underscore) repository at
   `github.com/jebucha/yt_transcript`. `/var/lib/yt-transcripts` (README
   example) is a directory name meaning "transcripts", not the project
   name. All three stay. — *Alternative considered:* a global find-and-
   replace over the whole tree; rejected because it corrupts historical
   and foreign artifacts.

2. **Edit `pyproject.toml`'s `name` directly, then regenerate `uv.lock`
   with `uv lock`.** The AGENTS.md "never hand-edit pyproject.toml" rule
   governs dependency pins (which go through `uv add`); the project *name*
   is not a dependency and has no CLI equivalent. The lock stores the
   project name under `name = "…"` and must be regenerated, not edited by
   hand; the diff is expected to contain only the name line.

3. **Docs change flows through the generator.** Edit the two template
   strings in `docs/generate.py`, the four `docs/*.md` sources that name
   the project (`index.md`, `deploy/compose-yml.md`,
   `deploy/Dockerfile.md`, `providers-json-example.md`), and the
   `docs/style.css` comment, then run `uv run python docs/generate.py` to
   regenerate all committed HTML. The generator is deterministic
   (unchanged Markdown → byte-identical HTML), so the regenerated diff must
   contain only the renamed string. No `.html` file is edited directly.

4. **Rename the browser-tab title; keep the H1 and source comment as a
   feature description.** The user confirmed (during exploration) that
   `app/static/index.html`'s `<title>YouTube Transcript</title>` becomes
   `inj-testing`, matching the project name rather than the legacy feature
   description. The page's visible `<h1>YouTube Transcript</h1>` and the
   `app/static/app.js` header comment are deliberately **not** renamed:
   they describe the tool's function (fetching a YouTube transcript), not
   the project name, so they stay — only the tab title carries the project
   identity. This keeps the user-visible change limited to the confirmed
   tab title.

5. **Document the one-time deployment migration.** Renaming
   `container_name` orphans a running `yt-transcript` container: compose
   will create `inj-testing` and will not manage the old one. The
   README's `### Compose (primary)` section gains a note: remove the
   old-named container (`docker rm -f yt-transcript`, podman equivalent),
   then `docker compose up -d --build`. No in-app
   compatibility shim (e.g. a second container name alias) is added — the
   app is a single self-hosted instance; an alias would be complexity for
   one manual step.

## Risks / Trade-offs

- [Running deployment keeps an orphaned old-named container after the
  rename] → README migration note (decision 5); the old container is
  harmless while running but must be removed deliberately.
- [`uv lock` diff contains more than the name line (e.g. a uv version
  stamp)] → task verifies the lock diff is name-only; if not, investigate
  before committing.
- [Regenerated HTML drifts beyond the rename (generator or Markdown
  changed out-of-band)] → task verifies the HTML diff contains only the
  `yt-transcript` → `inj-testing` substitutions against the committed
  baseline.
- [Stray live references missed by a one-pass grep] → final verification
  task re-greps the tree (excluding `openspec/changes/archive/` and
  `security-audits/`) for `yt-transcript` and requires zero live hits.

## Migration Plan

1. Apply the rename and regenerate lock + docs in one commit (plus the
   minor version bump per AGENTS.md).
2. On each deployment: `docker rm -f yt-transcript` (or `podman rm -f`) to
   remove the orphaned old-named container, then `docker compose up -d
   --build` (image and container rebuild under the new name). Removing the
   old container first avoids a host-port bind conflict, since both the old
   and new containers publish `${PORT:-8000}`.
3. Smoke test per the README (UI 200, transcript fetch, `docker logs
   inj-testing`).
4. Rollback: revert the commit and rebuild — the rename has no data
   migration, so reverting fully restores the previous image/container
   names.
