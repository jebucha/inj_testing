# `app/static/style.css` — the stylesheet

## Purpose

The single self-contained stylesheet for the UI: the design tokens
(custom properties on `:root`, in light and dark palettes), the
application-frame layout (app header, left-pane navigation, view panes, and
the narrow-viewport collapse), and the class styles for every region `app.js`
drives. No web fonts, no CDN, no external references of any kind — the app's
no-CDN constraint applies to CSS as firmly as to JS.

## Public surface

Design tokens: `--bg`, `--panel`, `--text`, `--muted`, `--accent`,
`--accent-dark`, `--error-*`, `--border`, and `--accent-tint` (the
translucent accent used for hover/active fills). Each palette also sets
`color-scheme` so the native form controls and scrollbars the browser
renders match it. The light tokens live on `:root`; the identical dark token
set is duplicated in `:root[data-theme="dark"]` (an explicit Dark choice)
and inside `@media (prefers-color-scheme: dark)` over
`:root:not([data-theme="light"])` (the system case). Class/element contract
with `index.html` / `app.js`: `.container` (the single 760px column),
`.header` / `.header-row`, `.row`, `.url-input`, `.btn` / `.btn-quiet`,
`.spinner`, `.error-banner`, `.result-*`, `.video-title`,
`.video-language`, `.transcript-panel`, `.provider-picker`,
`.auto-summarize-label` (the checkbox label; dims with the input's
`:disabled` via `:has()`), `.auto-note` (the muted auto-summarize failure
note), `.summary-*`, `.saved-*` (`.saved-row` is the button-styled list
item), `.injection-panel` / `.injection-controls` (the benchmark panel and its
flex control row), `.injection-toggle-label` (dims with the toggle's
`:disabled` via `:has()`), `.injection-point` / `.difficulty-picker` / `.benchmark-judge` (the
single-select controls), `.difficulty-error` (the inline error status line),
`.benchmark-label`, `.benchmark-models` (the
multi-select), `.injection-payload`, `.injection-preview` (the dashed
spliced-text preview), `.benchmark-tally` (the per-model results table),
`.benchmark-rows` / `.bench-row` / `.bench-row-title` / `.bench-output` /
`.bench-meta` / `.bench-human-label` / `.bench-human` (the per-model result
rows), `.log-panel`, and the application frame: `.app-header` /
`.app-header-row` / `.app-brand` (the brand + actions row over the log
panel), `.app-header-actions` (the right-aligned control group: the theme
select and the log toggle), `.theme-picker` (the theme select, same select
treatment as `.provider-picker`), `.app-body` (the nav + main-pane row),
`.app-nav` / `.nav-item` (the
left navigation column; `.nav-item.active` is the active-view state),
`.app-main` (the view-pane column), `.view` (a view section), `#view-docs` /
`.docs-toolbar` / `#docs-frame` (the Docs view: a toolbar row over an
iframe that fills the remaining pane height).

## Invariants

- **Self-contained.** No `@import`, no web fonts, no external URLs; the
  font stacks are the system stack for text and `ui-monospace`/Menlo/Consolas
  for the log panel and transcript pre blocks.
- **`[hidden] { display: none !important; }` is load-bearing.** It keeps the
  `hidden` attribute authoritative even for styled elements (buttons and
  panels with display rules), so `app.js`'s visibility contract can never be
  silently defeated by a class — including the `#view-docs` section, which
  has its own `display: flex` rule but must stay invisible while `hidden`.
- **The page is a full-height flex column: app header, then the
  nav + main-pane row.** `body` is `display: flex; flex-direction: column;
  min-height: 100vh`, so the frame fills the viewport when content is short
  while long Transcripts content still grows the page. `.app-body` is a
  row (`display: flex`) whose `.app-nav` is a fixed 200px column and whose
  `.app-main` is the flexing view-pane column.
- **The Docs view's iframe fills the main pane.** `#view-docs` is a flex
  column; the toolbar owns the top strip and `#docs-frame` is
  `flex: 1; min-height: 0`, so the iframe takes the pane's full width and
  remaining height and gives the docs their own scroll context.
- **Narrow viewports collapse the nav to a horizontal tab row.** At
  `@media (max-width: 800px)` (mirroring the docs' own breakpoint)
  `.app-body` becomes a column and `.app-nav` a full-width row of equal
  (`flex: 1`) centered items above the content, so a 420px viewport shows
  no horizontal overflow.
- **The app header is a column of rows** (`.app-header`,
  `flex-direction: column`, `align-items: stretch`): brand + the
  `.app-header-actions` group (theme select, log toggle) in the first row
  (`.app-header-row`, `space-between`), the log panel as the second row.
  Spacing between rows comes from the column's `gap`, not from the panel's
  `margin-top` — the panel sits close beneath the toggle when opened and
  contributes no height when hidden. The Transcripts view keeps its own
  slim `.header` (title + subtitle only) beneath it.
- **The header row wraps rather than overflows.** `.app-header-row` carries
  `flex-wrap: wrap`: at a 420px viewport the actions group may drop to a
  second line, but no element ever extends past the viewport (the
  narrow-viewport overflow sweep relies on this).
- **Three-state palette, duplicated dark block.** The light tokens live on
  `:root` with `color-scheme: light`; the dark token set appears twice —
  under `:root[data-theme="dark"]` (an explicit Dark choice set by
  `app.js`) and under `:root:not([data-theme="light"])` inside
  `@media (prefers-color-scheme: dark)` (the system case). In system mode
  the attribute is absent, so the media query decides and OS preference
  changes re-resolve with no JavaScript. The duplication is the price of
  the no-build constraint: there is no preprocessing step to generate one
  dark block from the other, so it must be kept in sync by hand — and the
  docs site carries its own copy in `docs/style.css`.
- **Every long region scrolls internally with a bounded height:** the
  transcript panel `max-height: 60vh`, the summary text and saved list
  `40vh`, the log panel `40vh`, the injection spliced-text preview `30vh` —
  opening any of them never grows the page without bound.
- **Buttons are keyboard- and state-honest:** `.btn:disabled` dims and
  forbids; `.saved-row` keeps `:focus-visible` outlines; hover states apply
  only to `:not(:disabled)`.
- **Long content wraps, never overflows:** `overflow-wrap: anywhere` on
  titles, transcript, saved names, and the log panel.

## Log events emitted

None (markup-adjacent styles only).

## Error codes raised/handled

None.

## Design decisions

Resolved from the archived change design docs:

- `2026-10-29-youtube-transcript` **D6** — the no-build, no-CDN front-end
  constraint this file obeys.
- `2026-11-02-add-saved-transcript-list` **decision 6** — the saved section's
  treatment: bounded scrollable `<ul>` matching the existing
  `.transcript-panel` treatment, button-styled rows, the cosmetic
  `text-transform: capitalize` on `.saved-name` (accepted trade-off:
  acronym-like words are lowercased cosmetically; the real name is always
  what is requested and downloaded).
- `2026-11-06-move-log-panel-into-header` **D2/D3** — the column-of-rows
  header (`align-items: stretch` so rows span the full width) and the
  row-gap spacing that replaced the old `.log-panel { margin: 32px 0 0; }`.
- `add-prompt-injection-benchmark` **decision 1** and **decision 5** — the
  injection-benchmark panel's treatment: the flex control row, the bounded
  spliced-text preview, and the per-model tally table + result rows that the
  layered oracle (canary/judge/human) populates, all following the existing
  region conventions (bounded scroll, keyboard/state-honest controls).
- `benchmark-difficulty-picker` **decision 4** — the difficulty select and
  re-roll join the control row reusing the existing classes, and the
  `.difficulty-error` status line is a muted inline failure note (hidden
  except on failure), not the error banner.
- `add-docs-view` **D3** (the Docs view: the toolbar row over
  `#docs-frame`, which fills the main pane height so the docs get their own
  scroll context), **D4** (the app-level frame: the full-height flex-column
  body, the 200px left nav column beside the flexing main pane, the brand +
  log viewer in the app header), and **D6** (the `@media (max-width: 800px)`
  collapse of the nav into a horizontal tab row, mirroring the docs' own
  narrow-layout breakpoint and keeping the 420px overflow contract green).
- `add-theme-setting` **D3** (the three-state palette: light tokens on
  `:root`, the duplicated dark block, `--accent-tint` replacing the five
  hard-coded accent-tint literals, `color-scheme` per palette) and **D6**
  (the `.theme-picker` select reusing the `.provider-picker` treatment, and
  `flex-wrap: wrap` on `.app-header-row` as the narrow-viewport safety
  valve).

## Cross-links

- [`index.html`](index-html.html) — the markup it styles
- [`app.js`](app-js.html) — the script that toggles the classes and `hidden`
