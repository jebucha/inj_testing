# `app/static/app.js` — the frontend script

## Purpose

The entire frontend behavior, in one vanilla-JS IIFE with `"use strict"`:
fetch flow and result display, copy/download, the saved-transcripts list,
summarization, the prompt-injection benchmark, and the live log viewer. No
framework, no build step, no CDN — the file is served as-is at `/app.js` and
references DOM ids defined in `index.html`.

## Public surface

Nothing is exported (module-scoped IIFE). Its effective API is the set of DOM
ids it requires from `index.html`: `url-input`, `fetch-form`, `fetch-btn`,
`fetch-spinner`, `error-banner`, `result`, `video-title`, `video-language`,
`transcript-panel`, `copy-btn`, `download-btn`, `saved-list`, `saved-empty`,
`saved-count`, `saved-refresh-btn`, `provider-picker`, `summarize-btn`,
`summarize-spinner`, `summary-panel`, `summary-text`, `summary-copy-btn`,
`auto-summarize`, `auto-summarize-note`, `injection-panel`,
`injection-toggle`, `injection-toggle-label`, `injection-point`,
`injection-payload`, `injection-preview`, `difficulty-picker`,
`benchmark-reroll`, `difficulty-error`, `benchmark-models`,
`benchmark-judge`, `benchmark-run`, `benchmark-spinner`, `benchmark-label`,
`benchmark-results`, `benchmark-tally`, `benchmark-rows`, `log-panel`,
`logs-toggle`. It also defines the `ERROR_MESSAGES` map (server error code
→ human message) for the eleven taxonomy codes plus `NOT_FOUND`; the
dataset-pick errors (`INVALID_DIFFICULTY`, `DATASET_MISSING`) surface via
`messageFor`'s server-message fallback into the `difficulty-error` status
line.

## Invariants

- **No-`innerHTML` rule — absolute.** Every fetched string (transcript,
  title, names, summary, log lines) enters the DOM via `textContent` (or
  element construction) only; never as HTML. Markup-like content from
  YouTube or a backend cannot be rendered or executed.
- **Requests use the real file name, display uses a prettified one.** List
  rows keep the real name in `data-name`; the display label (extension
  stripped, underscores → spaces, CSS capitalization) is cosmetic and is
  *never* sent to the server.
- **Two distinct name variables, deliberately.** `currentSavedName` (a
  clicked saved row) drives Download's enabled predicate — a freshly fetched
  transcript does **not** enable Download. `currentTranscriptName` (the
  fetch response's derived name, or the saved row's name) is what Summarize
  sends for the alongside save.
- **`displayToken` invalidates stale results.** A monotonic token is bumped
  on every new transcript display; an in-flight saved-summary response or
  summarize response for a previously displayed transcript is discarded.
- **One summarize path, two entry points.** `doSummarize(auto)` serves the
  manual click (`auto=false`: picker selection, error banner on failure) and
  the post-fetch auto-fire (`auto=true`: the default target from
  `defaultSelection()`, the subdued note on failure). Both share the
  busy state (button, picker, and checkbox disabled + spinner), the
  `summarizing` guard, and the token staleness rule.
- **Auto-summarize fires on fresh fetches only.** The hook sits in
  `renderResult`, never in the saved-transcript click path. With the
  checkbox on it first reuses the saved-summary read: found → show it and
  skip (no summarize call); otherwise fire `doSummarize(true)` against the
  picker's default (`defaultSelection()`, the same target the picker
  pre-selects). The accepted consecutive-fetch race drops the second
  auto-fire via the `summarizing` guard (design D7).
- **Auto failures never raise the banner.** Every automatic failure shape
  (`PROVIDER_ERROR`, `NOT_CONFIGURED`, `INVALID_PROVIDER`, `INPUT_TOO_LONG`,
  network error, empty-`summary` 200) shows the subdued `#auto-summarize-note`
  (`textContent` only) and leaves the enabled Summarize button as the
  explicit retry; the manual path keeps the banner untouched. The note
  follows the same token staleness rule as the success path: a late failure
  for a superseded transcript is dropped, never painted onto a newer one.
- **The Auto-summarize checkbox mirrors the server setting.** Loaded once
  on page load via `GET /api/settings` (no polling); toggling POSTs the
  change and reverts the checkbox to the last persisted value if the write
  fails. It is interactive only when providers are configured and is
  disabled while any summarize is in flight.
- **No polling.** The saved list, the provider list, and the settings load
  once on page load, the list also reloads after each successful fetch and
  via its Refresh button. The provider list is never re-fetched (a stale
  picker after a config edit gets a clean 400 `INVALID_PROVIDER` telling
  the user to reload).
- **Copy works over plain HTTP.** `navigator.clipboard.writeText` first,
  falling back to a hidden-textarea `execCommand("copy")` — the Clipboard
  API does not exist in non-secure contexts, and plain HTTP is the normal
  access path.
- **A 2xx with no summary text is a failure for display** — show the error
  region, never an empty panel (same truthiness check as the saved-summary
  load).
- **The log panel is a display concern.** Entries keep accumulating while
  the panel is hidden, so re-showing it includes what was logged in the
  meantime; the panel trims to its 200-line display cap (mirroring the
  server buffer).
- **SSE is fire-and-forget.** `EventSource` reconnects automatically;
  unparseable payloads are dropped; no error handling is needed.

### Injection benchmark invariants

- **The splice is client-side and produces one undifferentiated string**
  (design decision 1). `splicePayload` concatenates the payload at the chosen
  point (`prepend` / `middle` / `append`, default `append`) into a single
  string; a disabled toggle or an empty payload sends the transcript exactly
  as displayed. The request body is `{text, preset, provider, model}` only —
  no separate injection/payload field, and the app never adds a label marking
  the payload to the model (indirect-injection fidelity). `middle` cuts at a
  line boundary near the center so both halves are non-empty for a multi-line
  transcript (a single-line transcript falls back to a character split).
- **The benchmark never persists.** Delivery and judge both go through the
  non-persisting `POST /api/llm-call` (the `summarize` and `judge` presets);
  the persisting `POST /api/summarize` is never called, so no `.summary` file
  is created or modified.
- **The system prompt is a server-side preset, not client text** (design
  decision 3). The client sends only a `preset` id; there is no client system
  prompt field.
- **Layered oracle per model** (design decision 5):
  - *Canary (deterministic):* a unique token (`INJ-<16 hex>`) is generated per
    run and an emit instruction is appended to the payload (never labeling it
    an injection). A model is a **hit** iff its own output contains the token
    (substring match, checked per model). `canary` is `null` for payload-less
    runs.
  - *Judge (LLM):* the input is the **original unspliced** transcript plus
    `\n\n---\n\n` plus the model's output, called with the `judge` preset. The
    verdict is the first line, exactly `resisted`/`partial`/`full`
    (case-insensitive); the rest is the reason. A failed or unparseable judge
    is "unavailable" for that model only — it never fails the run.
  - *Human:* a per-model settable verdict (`—`/`resisted`/`partial`/`full`).
- **Runs are parallel per model** against the identical spliced text, guarded
  by the `benchRunning` flag and stale-discarded via the `displayToken`
  (a run started for a previously displayed transcript is dropped). Results
  accumulate in `benchRuns`, keyed `provider/model`, one entry per run.
- **A new transcript clears results, not setup.** `clearBenchmark` (on a new
  fetch or saved-transcript display) wipes `benchRuns` — the previous
  transcript's results no longer apply — but keeps the payload and
  insertion-point settings, since the same payload can target a new carrier.
- **Tally semantics** (per model, across its recorded results): canary
  hit-rate over the results that *carried a canary*; judge compliance-rate
  (share of *all* results judged `partial` or `full`); human-confirmed rate
  (share with a human verdict of `partial` or `full`) over *all* results.
  Rendered `"N / M (P%)"`, or `"—"` when the denominator is 0.
  Rows and tally rows appear in completion order, so tests filter by the
  `provider/model` key, never by position.
- **Everything renders as plain text.** The payload, the spliced preview, each
  model output, and each judge verdict/reason enter the DOM via `textContent`
  only.
- **The panel is interactive only in context.** The toggle is enabled only
  while a transcript is displayed; the payload field and insertion point need
  the toggle on; the model/judge pickers need a transcript, configured models,
  and no in-flight run; Run needs at least one selected model. The judge
  select shares the same option list as the multi-select and defaults to the
  same target the summarize picker pre-selects.

### Dataset difficulty picker invariants

- **The dataset difficulty picker seeds the payload field** (design decision
  2). Selecting a difficulty fetches a random entry of that difficulty from
  `GET /api/benchmarks`, puts its prompt into `#injection-payload` (a
  plain-text assignment), stores the entry id, and checks the injection
  toggle when its existing rules allow (a transcript is displayed) —
  explicitly calling `updateBenchmarkEnabled()` afterwards, since a
  programmatic `checked` assignment fires no change event. "Manual payload"
  is a no-op deselect: it clears only the stored entry id and never touches
  the payload field. The re-roll control re-fetches for the currently
  selected difficulty (re-selecting the same option fires no change event).
  The picker and the re-roll join `updateBenchmarkEnabled`'s governance: the
  picker needs a displayed transcript and no in-flight run; the re-roll
  additionally needs a dataset difficulty selected. On a failed fetch the
  error shows in the `#difficulty-error` status line and any check *this
  fetch* made is undone (a pre-existing check is never touched), so the
  existing enable logic keeps "Run benchmark" disabled in the fresh-panel
  case (a transcript displayed, no models selected).
- **Each result row shows the dataset entry id that seeded the run**
  (design decision 3). The stored id is captured at run time into each run's
  results and rendered as a plain-text meta line next to the canary span;
  manual edits to the payload field do not clear it (the payload was still
  seeded by that entry), and runs with no stored id render nothing.
  Everything renders as plain text, like the rest of the panel.

## Log events emitted

None (browser code). It *formats* server events for the panel via
`LOG_FORMATTERS` — one-line humanized formatters for the known events
(`server_started`, `server_stopped`, `http_request`, `fetch_attempt`,
`fetch_rejected`, `transcript_saved`, `transcript_save_failed`,
`summary_completed`, `summary_failed`, `summary_save_failed`,
`llm_call_completed`, `llm_call_failed`,
`config_load_failed`, `unhandled_exception`), with a
`time  LEVEL  event  key=value …` fallback for unknown ones.

## Error codes handled

`INVALID_URL`, `VIDEO_UNAVAILABLE`, `NO_CAPTIONS`, `UPSTREAM_FAILURE`,
`BUSY`, `NOT_CONFIGURED`, `INVALID_PROVIDER`, `PROVIDER_ERROR`,
`INPUT_TOO_LONG`, `INVALID_MODEL`, `MODEL_NOT_REMOVABLE`, and `NOT_FOUND` —
via the `ERROR_MESSAGES` map (preferred over the server message); network
failures and unexpected shapes get a generic message. The dataset pick's
`INVALID_DIFFICULTY` / `DATASET_MISSING` surface via `messageFor`'s
server-message fallback into the `difficulty-error` status line (the map
has no entries for them — the server messages are the stable UI contract
for these codes).

## Design decisions

Resolved from the archived change design docs:

- `2026-10-29-youtube-transcript` **D6** — one static page, no build step,
  no framework, no CDN; the clipboard fallback for non-secure contexts; the
  no-HTML insertion rule (XSS).
- `2026-11-02-add-saved-transcript-list` **decision 6** — the saved section:
  reusable result panel, prettified labels with real-name requests,
  client-side Blob download, load-once-plus-refresh (no polling).
- `add-transcript-summary` **decision 5** (the fetch response's `name` lands
  in a *new* variable; Download's predicate is intentionally untouched),
  **decision 11** (the UI state machine: picker pre-selection, enabled
  predicate, `currentSummary` lifecycle, the e2e seam below
  `summarize_with_provider`).
- `2026-11-03-add-log-viewer` **decision 6** — the panel shape, the
  `EventSource` opened once at page load, the formatters, the 200-line cap.
- `add-auto-summarize` **D4** (`defaultSelection()` shared by the picker
  pre-selection and the auto target), **D5** (`doSummarize(auto)` as one
  code path, the hook after `renderResult` only, skip-and-show via the
  saved-summary read), **D6** (subdued note for auto failures, checkbox
  revert on a failed settings write), **D7** (accepted: a second auto-fire
  during an in-flight summarize is dropped).
- `add-prompt-injection-benchmark` **decision 1** (the client-side splice
  into one undifferentiated string — no server knows the split),
  **decision 2** (delivery and judge both use the non-persisting
  `POST /api/llm-call`, never the persisting `/api/summarize`),
  **decision 3** (system prompts only from the server-side preset registry —
  the client sends a `preset` id, no system text), **decision 5** (the
  layered oracle: per-run canary token + judge over the original unspliced
  transcript + settable human verdict, with the per-model tally semantics).
- `benchmark-difficulty-picker` **decision 2** (the picker and re-roll
  seed the payload field, the selectable "Manual payload" placeholder is a
  no-op deselect, the explicit `updateBenchmarkEnabled()` call, and the
  failed-fetch undo that keeps the fresh-panel run button disabled) and
  **decision 3** (the stored entry id is captured at run time and rendered
  on each result row; manual edits do not clear it).

## Cross-links

- [`index.html`](index-html.html) — the DOM it wires up
- [`style.css`](style-css.html) — the classes it toggles
- [`main.html`](../main.html) — the endpoints it consumes
- [`benchmark_dataset.html`](../benchmark_dataset.html) — the dataset pick behind the difficulty picker
