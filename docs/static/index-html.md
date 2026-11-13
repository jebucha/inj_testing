# `app/static/index.html` — the single static page

## Purpose

The entire web UI's markup: one page, no framework, no build step, no CDN.
It defines the DOM contract that `app.js` consumes — every id the script
reaches for — and the visible structure. The page is an application frame:
an app header (the `inj-testing` brand, the "Show logs" toggle, and the log
viewer), a left-pane navigation with two items ("Transcripts" and "Docs"),
and a main pane holding two view sections. The Transcripts view
(`#view-transcripts`) contains the entire original interface — the "YouTube
Transcript" title and subtitle, the fetch form, the error banner, the result
section (transcript panel, summary panel, and the injection-benchmark
panel), and the saved-transcripts section. The Docs view (`#view-docs`,
hidden by default) displays the code documentation in an embedded iframe.

## Public surface

The asset set is exactly three files referenced with absolute paths:
`/style.css`, `/app.js`, and this page (served by the static mount at `/`).
The effective API is the id/class contract with `app.js`:

- Fetch flow: `url-input`, `fetch-form`, `fetch-btn`, `fetch-spinner`,
  `fetch-label`.
- Result: `error-banner`, `result`, `video-title`, `video-language`,
  `transcript-panel`, `copy-btn`, `download-btn`.
- Summarization: `provider-picker`, `summarize-btn`, `summarize-spinner`,
  `summary-panel`, `summary-text`, `summary-copy-btn`, `auto-summarize`
  (the Auto-summarize checkbox, inside its `auto-summarize-label`),
  `auto-summarize-note` (the subdued inline failure note, hidden until an
  automatic summarization fails).
- Saved list: `saved-list`, `saved-empty`, `saved-count`,
  `saved-refresh-btn`.
- Injection benchmark (a `section` inside the result section, below the
  summary panel): `injection-toggle` (the enable checkbox, inside
  `injection-toggle-label`), `injection-point` (the `prepend`/`middle`/
  `append` select, defaulting to `append`), `injection-payload` (the payload
  `<textarea>`, hidden until the toggle is on), `injection-preview` (the
  spliced-text preview `<pre>`), `difficulty-picker` (the Difficulty select —
  a selectable "Manual payload" placeholder plus `easy`/`medium`/`hard`),
  `benchmark-reroll` (the re-roll button), `difficulty-error` (the hidden
  inline error status line for a failed dataset pick), `benchmark-models`
  (the multi-select), `benchmark-judge` (the judge provider/model select),
  `benchmark-run` (+ `benchmark-spinner` and its `benchmark-label`),
  `benchmark-results`, `benchmark-tally` (the per-model table), and
  `benchmark-rows` (the per-model result rows).
- Log viewer: `logs-toggle`, `log-panel`.
- Application frame and view navigation: `app-header`, `app-brand`,
  `app-body`, `app-nav`, `nav-transcripts`, `nav-docs` (the two navigation
  items; the active one carries `aria-current="page"` and the `active`
  class), `app-main`, `view-transcripts` (the Transcripts view section,
  default visible), `view-docs` (the Docs view section, `hidden` by
  default), `docs-toolbar`, `docs-open-new` (the open-in-new-window link),
  and `docs-frame` (the iframe whose `src` is `/docs/`).

## Invariants

- **No build step, no framework, no CDN.** The file is hand-maintained
  markup; anything requiring a transpiler or a third-party script is
  off-limits for this app.
- **The `hidden` attribute is the visibility contract**, and the CSS rule
  `[hidden] { display: none !important; }` in `style.css` keeps it
  authoritative even for styled elements. `app.js` toggles only `hidden`.
- **The log panel is app-level, in the app header's second row** — not
  inside either view and not at the bottom of the page flow — so opening it
  never requires scrolling and it stays available in both views. The header
  is a column of rows (brand + toggle on the first row, panel on the
  second), with row gap providing the spacing.
- **The frame is header → body row of left nav + main pane.** The view
  sections live inside `app-main`; the Transcripts view is the default
  (visible) view and holds the whole original interface unchanged, including
  the "YouTube Transcript" h1 and subtitle, which are view-specific (they
  belong to the Transcripts view, not the app header).
- **The Docs view holds only its toolbar and the iframe.** The toolbar's
  single control is the open-in-new-window anchor (`href="/docs/"`,
  `target="_blank"`); the documentation is displayed exclusively through
  `#docs-frame`'s `src` — no docs HTML is ever inserted into the
  application's DOM (the docs' own sidebar navigation lives in the iframe's
  document).
- **View switching is `hidden`-toggled and unmarked in state.** The
  `hidden` attribute on the view sections plus the active marker on the nav
  items is the entire contract; nothing about the selected view is stored,
  so a reload always lands on the Transcripts view.
- **Accessibility is structural, not script-added:** `role="alert"` on the
  error banner, `aria-label`s on the input, panels, and provider picker,
  `tabindex="0"` on the scrollable `<pre>` panels, `type="button"` on
  non-submit buttons, `aria-hidden` on the spinners.
- **Buttons start disabled where `app.js` requires it** (copy, download,
  summarize, the provider picker, the auto-summarize checkbox, and the whole
  injection-benchmark control set — the injection toggle, insertion point,
  difficulty picker, re-roll, model/judge pickers, and Run); the script
  enables them as state allows.
- **The result section is hidden until the first transcript** — fresh fetch
  and saved-row display both render into this same single panel. The
  injection panel is a child of it, so it is hidden until a transcript is
  displayed too; the payload field and preview additionally start `hidden`
  and are revealed only while the toggle is on.

## Log events emitted

None (markup). The `log-panel` `<pre>` is where `app.js` appends the
humanized server log lines.

## Error codes raised/handled

None (markup). The `error-banner` element is where `app.js` surfaces them.

## Design decisions

Resolved from the archived change design docs:

- `2026-10-29-youtube-transcript` **D6** — one static page served by
  FastAPI's `StaticFiles`; no framework, no bundler, no CDN.
- `2026-11-02-add-saved-transcript-list` **decision 6** — the saved section
  below `#result`: header over a bounded, scrollable `<ul>`, rows as
  keyboard-accessible `<button>`s.
- `2026-11-03-add-log-viewer` **decision 6** — the `#logs-toggle` button and
  the `#log-panel` `<pre>` (monospace, scrollable, bounded max-height).
- `2026-11-06-move-log-panel-into-header` **D1–D3** — push-down placement in
  the header (normal document flow, not an overlay), the column-of-rows
  header with `align-items: stretch`, and row-gap spacing replacing the old
  `margin-top` while the panel keeps its `max-height: 40vh` internal scroll.
- `add-auto-summarize` **D6** — the `auto-summarize` checkbox next to the
  provider picker and the hidden `auto-summarize-note` `<p>` beneath the
  summarize actions (a muted inline note, not the error banner).
- `add-prompt-injection-benchmark` **decision 1** (the injection panel and
  splice live in the UI, so the panel sits inside the result section and is
  only reachable once a transcript is displayed) and **decision 5** (the
  layered oracle: the models multi-select, the judge select, and the
  per-model tally table + result rows that the canary/judge/human verdicts
  populate).
- `benchmark-difficulty-picker` **decision 2** (the Difficulty select joins
  the control row after the insertion-point select, with a selectable
  "Manual payload" placeholder — not `disabled`, so the deselect path is
  usable) and **decision 4** (the picker and re-roll reuse the existing
  `benchmark-label`/`btn` classes, and the hidden `difficulty-error` status
  line sits beside them).
- `add-docs-view` **D3** (the Docs view is a full-height `<iframe src="/docs/">`
  — the only approach that displays the full-document doc pages unchanged
  and keeps their own sidebar navigation functional, with no docs HTML in
  the app DOM), **D4** (the app-level frame: brand + log viewer in the
  header, left nav with the two view sections in the main pane; the
  view-specific title/subtitle move into the Transcripts view), and **D5**
  (the Transcripts content moves in unchanged; view switching is a
  `hidden` toggle with the `aria-current`/`active` marker, no persistence).

## Cross-links

- [`app.js`](app-js.html) — the script that owns the behavior
- [`style.css`](style-css.html) — the stylesheet that owns the look
- [`main.html`](../main.html) — the static mount that serves this file
