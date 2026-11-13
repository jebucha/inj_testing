# Proposal

## Why

The repository already ships a complete pre-rendered code documentation site under
`docs/` (23 self-contained HTML pages, committed), but the running application has
no route and no UI affordance to reach it — readers must open the files from disk.
At the same time, the run-1 security audit flagged that FastAPI's built-in
interactive OpenAPI UI (`/docs`, `/redoc`, `/openapi.json`) is exposed
unauthenticated and costs one line to disable. This change surfaces the docs in
the application and retires the Swagger surface.

## What Changes

- The application serves the committed pre-rendered docs under `/docs/` (landing
  page at `/docs/`, plus every linked page and the docs stylesheet), with no build
  step at serve time.
- FastAPI's built-in interactive API documentation is retired: the Swagger route
  at `/docs`, `/redoc`, and `/openapi.json` no longer exist (closes the run-1
  audit finding). **BREAKING** for any client consuming `/openapi.json`; no
  in-repo consumer exists and the audit recommended retirement.
- The base UI is rewritten as an application shell: a left-pane navigation with
  two views. The "Transcripts" view contains the entire current interface with
  unchanged behavior; the "Docs" view displays the documentation.
- The Docs view displays the docs landing page in a full-height embedded iframe
  (the docs' own sidebar navigation remains functional inside it); no docs HTML
  is ever inserted into the application's DOM. The Docs view also offers a link
  that opens the docs landing page in a new window.
- "Transcripts" is the default view on load; the selected view does not persist
  across a page reload. At narrow viewports (800px or less, matching the
  docs' own), the left navigation collapses to a horizontal tab row above the
  content, with no horizontal overflow at a 420px viewport.
- `Dockerfile` copies `docs/` into the image (today only `app/` and `data/` are
  copied, so the docs would be missing in the container).
- The doc pages that describe the affected artifacts are updated and the
  committed HTML regenerated: `docs/index.md` (the landing page now points at
  the served `/docs/` path instead of opening files from disk), `docs/main.md`
  (endpoint surface and the static-mount ordering), `docs/static/index-html.md`,
  `docs/static/app-js.md`, `docs/static/style-css.md`, and
  `docs/deploy/Dockerfile.md`.
- `README.md` documents the new Docs view and the `/docs/` path.

## Capabilities

### New Capabilities

- `code-docs`: The application serves the committed pre-rendered code
  documentation under `/docs/` and does not expose FastAPI's built-in
  interactive API documentation endpoints.

### Modified Capabilities

- `web-interface`: Application-shell navigation is added — a left-pane
  navigation with "Transcripts" and "Docs" views, the Transcripts default,
  view switching with the Docs view embedding the docs in a full-height iframe
  (plus an open-in-new-window link), and the narrow-viewport navigation
  collapse.

## Impact

- `app/main.py`: docs `StaticFiles` mount at `/docs` (before the root static
  mount); `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`.
- `app/static/index.html`, `app/static/style.css`, `app/static/app.js`: shell
  rewrite (frame, left nav, view panes, Docs view); existing feature logic is
  untouched.
- `Dockerfile`: `COPY docs ./docs`.
- `docs/index.md`, `docs/main.md`, `docs/static/index-html.md`,
  `docs/static/app-js.md`, `docs/static/style-css.md`,
  `docs/deploy/Dockerfile.md` and the regenerated `.html` via
  `uv run python docs/generate.py`.
- `README.md`: usage note for the Docs view and `/docs/`.
- `tests/e2e/`: new view-navigation and Docs-view tests
  (T-WEB-INTERFACE-019..026); existing viewport/layout assertions reviewed for
  the narrower content area.
- New API-level test file for `/docs/` serving and the retired OpenAPI endpoints
  (T-CODE-DOCS-001..005).
- User-visible change: minor version bump at archive time.
