# Design

## Context

- `docs/` holds 23 committed, pre-rendered HTML pages plus `style.css`, generated
  from `.md` by `docs/generate.py` (stdlib + `markdown`, deterministic, byte-
  identical output for unchanged input). Each page is a self-contained shell with
  its own sticky sidebar navigation and a relative reference to `style.css`.
- `app/main.py` builds the FastAPI app: API routes, then
  `app.mount("/", StaticFiles(directory=app/static, html=True))` registered last
  so the API routes win. FastAPI's default interactive docs are enabled —
  Swagger at `/docs`, plus `/redoc` and `/openapi.json`; the run-1 security audit
  flagged this exposure.
- The UI is `app/static/index.html` (~160 lines of static markup),
  `app/static/app.js` (one ~1,676-line IIFE that binds every element by ID at
  load), and `app/static/style.css`. Vanilla JS, no build step, no framework.
- E2E tests run Playwright against an in-process uvicorn with a stubbed fetch
  chain; the common viewport is 1024x640 and one test uses 420x640 to assert no
  horizontal overflow. API tests use `TestClient(create_app())`.
- The `Dockerfile` copies only `app/` and `data/` into the image — `docs/` is
  not shipped today.

## Goals / Non-Goals

**Goals:**

- `/docs/` serves the committed docs; the Swagger/Redoc/OpenAPI routes are gone.
- A shell rewrite that adds the Transcripts/Docs views while the Transcripts
  view's behavior is unchanged — every existing e2e test keeps passing.
- The Docs view displays the docs in a full-height iframe of `/docs/`.
- The docs pages that describe the changed artifacts stay accurate.

**Non-Goals:**

- No restructuring of `app.js` feature logic — the existing IIFE content stays
  as-is; only shell markup, CSS, and a small navigation section are added.
- No persistence of the selected view, no docs search, no runtime rendering of
  the `.md` sources — the committed `.html` files are the served source.
- No changes to the `docs/generate.py` pipeline itself.
- No SPA framework, ES modules, or CDN dependencies.

## Decisions

**D1: A second `StaticFiles` mount at `/docs`, registered before the root `/`
mount.**
`app.mount("/docs", StaticFiles(directory=DOCS_DIR, html=True))` with
`DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"`. Starlette matches
routes in registration order and the root `/` mount would otherwise swallow
`/docs/`, so the docs mount goes above it (both after the API routes).
`html=True` serves `index.html` as the `/docs/` directory index. The
`/docs` → `/docs/` redirect is a registered `GET /docs` route: with the root
static mount present, Starlette 1.10 matches `/docs` against that mount
before `redirect_slashes` (or the `StaticFiles` directory 307) could fire, so
without the route `/docs` would 404. Alternative considered: a custom route
reading the file and returning `HTMLResponse` — rejected, `StaticFiles`
provides MIME types and 404s for free and matches the existing mount pattern. A
missing `docs/` directory fails fast at `create_app()` time (Starlette
validates the mount directory at startup); that is the intended behavior — the
directory is committed to the repo and shipped by D7, and a hard startup error
is preferable to a silent 404 for the docs.

**D2: Retire the interactive OpenAPI UI:
`FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`.**
With `docs_url=None` nothing intercepts the `/docs` route, so the docs site
owns the whole path; this also closes the run-1 audit finding in one line each.
`/docs` without the trailing slash 307s to the docs landing page. Alternative:
keep Swagger and serve the docs at `/code-docs/` — rejected: it leaves the audit
finding open and puts the docs behind an awkward URL.

**D3: The Docs view is a full-height `<iframe src="/docs/">`.**
The doc pages are full documents with their own sidebar and stylesheet; an
iframe is the only approach that displays them unchanged, keeps the docs' own
sidebar navigation functional, and satisfies the project's convention that
content enters the app DOM via `textContent` only (no docs HTML is injected into
the application document at all). The iframe fills the main pane height, so the
docs get their own scroll context — the "fresh window" feel the user described.
Alternative: a link list in the pane loading one page at a time — rejected: each
page is a complete shell with a sidebar, so in-pane single-page rendering would
require stripping or duplicating the shell.

**D4: Shell structure — app-level frame, view-specific header content.**
The frame is: app header (brand "inj-testing", "Show logs" toggle, log panel) →
body row of left nav (two items) + main pane. The existing `.container` content
moves into `<section id="view-transcripts">` unchanged, including the "YouTube
Transcript" h1 and subtitle, which are view-specific and live inside the
Transcripts view. `<section id="view-docs" hidden>` holds a small toolbar (the
open-in-new-window link) and the iframe. The log viewer stays app-level, where
the `log-viewer` spec and its tests expect it.

**D5: View switching toggles `hidden`; the Transcripts content never leaves the
DOM.**
`app.js` binds every element by ID at load and keeps in-memory state (fetched
transcript, in-flight summarization), so switching is a `hidden`-attribute
toggle plus an active marker on the nav item (`aria-current="page"`, matching
the docs' own convention, plus a CSS class). A fetched transcript is still
displayed after a round trip through the Docs view. The switching logic is a
small section (~50 lines) in the existing single `app.js` IIFE — the no-build-
step single-script convention is preserved. No view persistence, consistent
with the existing non-persistent resize behavior.

**D6: Narrow viewports — collapse the nav at 800px.**
`@media (max-width: 800px)` switches the body row to a column: the nav becomes
a horizontal tab row above the content. 800px mirrors the docs' own narrow-
layout breakpoint. This keeps the existing 420px e2e overflow test meaningful
and green.

**D7: Ship the docs in the Docker image.**
`COPY docs ./docs` in the `Dockerfile`, placed with the other content copies
(before `useradd`/`chown` so the unprivileged user owns the files). The e2e and
dev servers run from the repo root, so only the container was missing the
files.

**D8: Keep the doc pages describing changed artifacts accurate.**
The rewrite changes `app/static/*`, `app/main.py`, and the `Dockerfile`; the
doc pages that describe them (`docs/static/index-html.md`,
`docs/static/app-js.md`, `docs/static/style-css.md`,
`docs/deploy/Dockerfile.md`, and `docs/main.md` — endpoint surface and the
static-mount ordering invariant) are updated to match, and the docs landing
page (`docs/index.md`) is updated to point at the served `/docs/` path instead
of opening files from disk. Then `uv run python docs/generate.py` regenerates
all committed `.html` (deterministic — unchanged pages come out
byte-identical).

## Test Strategy

- **E2E (primary for the UI):** new `tests/e2e/test_docs_view.py` implementing
  T-WEB-INTERFACE-019..026: default view, switch to Docs (Transcripts content
  hidden, Docs active), return to Transcripts with a fetched transcript still
  displayed, view selection not persisting across a reload, iframe present with
  the docs landing src and sized to fill the main pane, no docs markup in the
  application document outside the iframe, the docs' own navigation rendered
  inside it (Playwright `frame_locator`), open-in-new-window link via
  `expect_popup`, and the 420px collapse with a new document-wide
  no-horizontal-overflow sweep. The module defines its own fixtures,
  duplicating the self-contained harness from `test_ui.py` (including the
  stubbed fetch chain); the file header's ID range is `.. 019..026`.
- **API-level (primary for serving):** new `tests/test_docs_serving.py`
  implementing T-CODE-DOCS-001..005 with `TestClient(create_app())`: landing
  200 + nav present, linked pages (including a subdirectory page) 200, no
  http(s) resource references in the served HTML, `/docs` landing on the docs
  site, and 404 for `/openapi.json` and `/redoc`.
- **Regression:** full e2e suite (`uv run python -m pytest tests/e2e/ -q`) and
  non-e2e suite (`uv run python -m pytest tests/ -q --ignore=tests/e2e`) — the
  shell rewrite must not move any existing behavior; layout-sensitive existing
  assertions (toolbar wrapping, log panel fit, the 420px overflow sweep, and the
  420x640 `.result-actions` vertical fit, T-WEB-INTERFACE-017) are the watch
  items because the nav narrows the content area at 1024px and the collapsed
  nav row adds vertical chrome at 420px.

## Risks / Trade-offs

- [The left nav narrows the content area at the 1024px test viewport and, at
  420x640, the collapsed horizontal nav row adds vertical chrome that could
  push `.result-actions` below the viewport (asserted by
  T-WEB-INTERFACE-017)] → run the full e2e suite early in implementation and
  iterate on CSS; test intent is never weakened to absorb a layout regression.
- [The iframe introduces a nested scroll context — long doc pages scroll inside
  the iframe, not the page] → intended: it is the "fresh window" isolation the
  user asked for; the iframe height fills the pane so the docs use the whole
  main area.
- [Retiring `/openapi.json` removes a machine-readable API surface] → no
  in-repo consumer; the audit recommended retirement; called out as BREAKING in
  the proposal.
- [The docs `.md` pages for the UI artifacts can drift from the rewritten
  shell] → task D8 updates the four stale pages before regenerating;
  regeneration is deterministic, so a diff shows exactly which HTML changed.
- [e2e asserts on the iframe's document content] → the e2e server serves the
  real `docs/` from the repo root, same as dev; if the docs site ever gains
  external resources the self-contained test (T-CODE-DOCS-003) fails first.

## Migration Plan

Ship the release with the new app; `docs/` travels with the repo and a Docker
image rebuild picks it up (D7). Rollback is reverting the change — no data,
schema, or state migration. Before archiving: minor version bump
(`uv version --bump minor`, user-visible change) and validation in a fresh
session per the project workflow.
