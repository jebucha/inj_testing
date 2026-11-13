# Design

## Context

See `proposal.md` for motivation and the delta specs for required behaviour.

Current state that shapes the approach:

- `app/settings.py` holds a frozen `Settings(auto_summarize)` dataclass, a
  per-request `load_settings()` that degrades to defaults on any unusable file,
  and `save_settings(auto_summarize)`, which serializes **only**
  `{"autoSummarize": ...}` and swaps it in with `os.replace`.
- `app/main.py` validates the POST body by requiring a boolean `autoSummarize`,
  then writes through `asyncio.to_thread`.
- `app/static/style.css` is fully tokenized on `:root`; the only literals are
  the accent tint `rgba(47, 111, 237, 0.08)` on five rules and `#fff` inside the
  accent button/spinner.
- `index.html` is served by `StaticFiles` at `/`, so no server-side templating
  is available for injecting state into the first byte of HTML.
- `docs/` is a second, hand-maintained stylesheet plus committed pre-rendered
  HTML with no scripts, served under `/docs/` and embedded as a same-origin
  iframe by the Docs view.
- `tests/e2e/test_auto_summarize.py` asserts the exact file content
  `{"autoSummarize": True}` after toggling the checkbox.

## Goals / Non-Goals

**Goals:**

- One persisted setting, one read endpoint, one write endpoint — no second
  preferences mechanism.
- Correct first paint for the common cases (an OS-matching user) without a
  pre-paint bootstrapping script.
- The chosen palette covers the embedded docs view, not just the app shell.

**Non-Goals:**

- Per-device or per-browser theme (that would need client storage; the project's
  stated model is server-side UI preferences).
- Theming anything outside the page: no CSS for logs, exports or the CLI.
- Passing an explicit theme into the standalone docs window (it is static HTML
  with no scripts; it follows the OS instead).
- More than three theme values, or custom/accent colour pickers.

## Decisions

### D1 — `theme` is a string enum in `settings.json`, defaulting to `system`

`Settings` gains `theme: str` with the constant set `{"system", "light",
"dark"}`. Read validation mirrors `autoSummarize`: a missing, non-string, or
unrecognized value degrades silently to `system` (the file itself parsed fine, so
no log), while malformed JSON or an unreadable file keeps the existing
`settings_load_failed` path. `system` is the default because it is both the
least surprising initial state and the only value that lets the stylesheet
resolve the palette before JavaScript runs (D6).

*Alternatives:* a boolean `darkMode` (cannot express "follow the OS", and the
default would be wrong for OS-dark users); a separate `theme.json` (two files,
two readers, no benefit).

### D2 — POST is a partial merge; the client sends only the field it changed

`save_settings` becomes `save_settings(auto_summarize=None, theme=None)`, where
`None` means "leave as stored". It loads the current settings first, overlays the
provided fields, and writes the merged object with the same temp-file +
`os.replace` swap. The keyword-with-`None` shape keeps the three existing
`save_settings(True)` test call sites working and makes "unchanged" impossible to
confuse with `False`.

`POST /api/settings` accepts a JSON object, validates each recognized field that
is present, rejects only when **no** recognized field is present, and echoes the
full persisted settings. `app.js` posts just `{"theme": ...}` or
`{"autoSummarize": ...}` rather than the whole state. This is what keeps
`tests/e2e/test_auto_summarize.py`'s `{"autoSummarize": True}` assertion true and
avoids a stale second field clobbering a value another tab changed.

*Alternatives:* full-object POST (rejected: breaks the documented settings shape
for existing clients and the file assertion above, and forces every client to
read before writing anyway); a separate `/api/settings/theme` endpoint (rejected:
two settings endpoints, and the read endpoint would still have to grow a field).

### D3 — Three-state CSS with a duplicated dark token block

Both stylesheets use:

```css
:root { /* light tokens (existing) */ }
:root[data-theme="dark"] { /* dark tokens */ }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* the same dark tokens */ }
}
```

The dark block appears twice, which is the price of having no build step and no
CSS preprocessing here. The alternative — declaring `--light-*`/`--dark-*` pairs
and switching one indirection level — avoids duplication but doubles the token
inventory and makes every rule read through two variables; it also obscures the
existing token contract documented in `docs/static/style-css.md`.

`app/static/style.css` also gains `--accent-tint` (replacing the five
`rgba(47, 111, 237, 0.08)` occurrences) and `--on-accent` is **not** introduced:
`#fff` labels and the spinner sit on the accent background in both themes, so
they stay literal. Both stylesheets set `color-scheme` so native checkboxes,
select popups, textareas and scrollbars match the palette.

### D4 — JavaScript sets `data-theme` only for explicit choices

`app.js` applies `document.documentElement.dataset.theme = "dark"` / `"light"`
for explicit choices and **removes the attribute** for `system`. Consequences:

- CSS never needs a `"system"` string, and `:root:not([data-theme="light"])`
  naturally covers the system case.
- OS preference changes update the page with no listener in `app.js`, because
  the media query re-resolves on its own.
- The Docs iframe receives the same attribute on its own `documentElement`
  (same origin), and the attribute is re-applied on the iframe's `load` event so
  navigating inside the docs site does not revert it. In `system` mode the
  attribute is removed there too.

`docs/style.css` gets the same three-state structure, so a standalone docs window
follows the OS without any script — preserving the code-docs invariant that docs
pages reference no external resources and need no JavaScript.

### D5 — No pre-paint bootstrapping script

`index.html` is static, so the stored value is only known after
`GET /api/settings` resolves. With `system` as the default, an OS-matching user
sees the correct palette from the first paint; only a user who pins the app to
the opposite of their OS sees one flip after a purely local round trip. That is
an acceptable cost for keeping a single source of truth.

*Alternatives:* an inline head script seeded from `localStorage` (rejected: a
second source of truth that can disagree with `settings.json`, and it needs a
first-run miss anyway); turning `/` into a templated route (rejected: real scope
creep, and `docs/static/index-html.md` describes the file as static).

### D6 — The control is a `<select>` in the existing header row

Three options, labelled System / Light / Dark, placed in `.app-header-row`
beside the log toggle, reusing the `.provider-picker`-style select treatment.
`.app-header-row` gains `flex-wrap: wrap` as a safety valve for narrow viewports;
conversely, the widest label ("System") must keep the row within 420px, because
`tests/e2e/test_docs_view.py::test_narrow_viewport_nav_collapses` sweeps every
element for horizontal overflow at that width.

*Alternatives:* a "Dark" checkbox (cannot express system, and would render
unchecked on a dark OS); an icon button that cycles the three values (smallest
footprint, but the current state is invisible without a tooltip and cycling is
harder to assert in tests).

## Risks / Trade-offs

- **One-paint flash for explicit overrides** → accepted per D5; the setting is
  read from a local file and the response is same-origin, so the flip is one
  round trip. If it proves objectionable, the follow-up is a client-side cache,
  not a change to this API.
- **Read-merge-write can lose a concurrent update** (two POSTs interleaving
  between the read and the `os.replace`) → the window is microseconds, the app
  is a single-user LAN tool, and the atomic replace still guarantees the file is
  never truncated. Each field is written by one control, so a lost update would
  require two tabs changing *different* fields at the same instant.
- **The client must post only the changed field**, or the untouched field in the
  response overwrites a concurrent change and the existing `settings.json`
  content assertion in the auto-summarize e2e suite breaks → both are called out
  explicitly in the tasks and covered by T-APP-SETTINGS-014.
- **Duplicate dark token blocks can drift** in two stylesheets → keep the app and
  docs token names aligned and note the duplication in
  `docs/static/style-css.md`; there is no build step to generate one from the
  other.
- **Missing `color-scheme`** leaves native controls and scrollbars light on a
  dark panel, which reads as a bug → set it in both stylesheets and assert the
  dark scheme in an e2e scenario.
- **Iframe theme drift** after in-docs navigation → re-apply the attribute on the
  iframe's `load` event, and assert it in the docs-view e2e scenario.

## Migration Plan

None required. `settings.json` files without a `theme` key read as `system`, and
nothing is written on read, so no file is rewritten. Older application builds
ignore the extra key. Rollback is a code revert: a leftover `"theme"` key in
`settings.json` is inert.

## Open Questions

None. The one deliberately deferred item — caching the theme client-side to
eliminate the override flash — is a follow-up that would not change these specs.
