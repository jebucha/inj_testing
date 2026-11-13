# Proposal

## Why

The UI has exactly one palette (a light theme hard-coded as custom properties on
`:root`), so anyone working in a dark environment gets a bright page with no way
to change it. Because the stylesheet is already fully tokenized, a second palette
is cheap; what is missing is a way to choose it. The application already persists
UI preferences server-side through `settings.json`, so the theme belongs in that
same mechanism instead of a new one.

## What Changes

- Add a `theme` setting with three values — `system` (default), `light`, `dark` —
  persisted in the existing `settings.json` alongside `autoSummarize`.
- `GET /api/settings` returns `theme`; a missing or unrecognized value reads as
  `system` (never an error), matching how a non-boolean `autoSummarize` behaves.
- `POST /api/settings` accepts a **partial** body: any subset of the recognized
  setting fields is merged into the stored settings and returns the full
  persisted settings. A body carrying no recognized field is still
  `400 INVALID_BODY`. **Behaviour change for an existing requirement:** the
  current write requirement rejects a body whose `autoSummarize` is missing; that
  clause is amended, not dropped — existing `{"autoSummarize": true}` clients
  keep working unchanged.
- Add a three-way theme control (`System` / `Light` / `Dark`) to the application
  header, which applies the choice immediately and persists it through the
  settings endpoints; a failed write reverts the control to the last persisted
  value, matching the auto-summarize checkbox.
- Add a dark palette to `app/static/style.css` that also follows the operating
  system's `prefers-color-scheme` while the setting is `system`, and give the
  native form controls a matching `color-scheme` so checkboxes, selects,
  textareas and scrollbars are legible in dark mode.
- Add the same dark palette to the standalone docs site (`docs/style.css`), and
  keep the embedded Docs view (an iframe) in step with the app's explicit choice.
  Docs opened in a separate browser window follow the operating system.

## Capabilities

### New Capabilities

None — theming is a setting (existing `app-settings` capability) and a UI
behaviour (existing `web-interface` capability).

### Modified Capabilities

- `app-settings`: the settings shape gains a `theme` enum (default `system`);
  the read endpoint returns it; the write endpoint becomes a partial-merge
  update over the recognized fields, and the invalid-body rule moves from
  "`autoSummarize` missing" to "no recognized field present".
- `web-interface`: the UI gains a persistable theme choice — a header control, a
  light/dark/system palette applied to the whole page, OS-following behaviour in
  `system` mode, and the embedded docs view tracking the app's explicit choice.

## Impact

- **Code**: `app/settings.py` (setting model, validation, merge-write),
  `app/main.py` (`GET`/`POST /api/settings`), `app/static/index.html` (header
  control), `app/static/app.js` (load, apply, persist, docs-iframe sync),
  `app/static/style.css` (dark palette), `docs/style.css` (dark palette).
- **APIs**: `GET /api/settings` response gains `theme`; `POST /api/settings`
  accepts and returns the full settings object and no longer requires
  `autoSummarize`. Additive for existing clients; no path or status-code change.
- **Storage**: `settings.json` gains a `"theme"` key. Existing files without it
  read as `system`; no migration or rewrite-on-read.
- **Docs**: `README.md` settings-shape paragraph, the `app/static/style.css`,
  `app/static/index.html`, `app/static/app.js`, `app/main.py` and
  `app/settings.py` pages under `docs/` (regenerated with `docs/generate.py`).
- **Tests**: `tests/test_settings.py` (module + endpoint coverage for the merge
  contract and the theme enum) and Playwright e2e coverage for the applied
  palette, `system` following the OS, persistence across reloads and the
  narrow-viewport header layout.
- **Version**: user-visible change, so a minor version bump before archiving.
