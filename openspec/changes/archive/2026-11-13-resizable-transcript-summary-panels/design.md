# Design

## Context

The injection payload box is the reference behavior: `<textarea id="injection-payload" rows="3">` styled with `resize: vertical` in `app/static/style.css` — a ~3-line default and the browser's native bottom-right resize grip.

The two panels to change are `<pre>` elements in the same stylesheet:

- `.transcript-panel` (`#transcript-panel`): `max-height: 60vh; overflow-y: auto` — grows with content up to 60vh, not resizable.
- `.summary-text` (`#summary-text`): `max-height: 40vh; overflow-y: auto` — same pattern at 40vh.

No JavaScript sets panel heights (`app/static/app.js` only resets `scrollTop`), so this is a CSS-only change plus e2e assertions. The project is a vanilla JS/CSS UI with no build step, and e2e tests run in headless Chromium via Playwright.

## Goals / Non-Goals

**Goals:**

- Both display panels: small fixed default height, native bottom-right vertical resize grip, scroll when content overflows — matching the injection payload textarea.
- Existing e2e behavior (notably `test_long_transcript_scrolls`) keeps passing unchanged.

**Non-Goals:**

- Persisting a resized height across page reloads (no `localStorage`) — the textarea is non-persistent; consistency was chosen over persistence.
- Horizontal resizing (`resize: vertical` only, as with the textarea).
- Any other panel: injection preview (`30vh`), log panel (`40vh`), saved-transcript list (`40vh`), benchmark outputs — all keep their current sizing.
- Custom pointer/touch drag handling (would only be needed if the CSS route proves unsupported in a browser the user actually targets).

## Decisions

**D1: CSS `resize: vertical` on the two `<pre>` panels, not a JS drag handle.**
`resize` applies to any element with `overflow` other than `visible`; both panels already set `overflow-y: auto`. Chromium (the e2e target) and Firefox support this on non-textarea elements, and the grip is pixel-identical to the one the user already accepts on the textarea. A custom JS handle (handle element + pointerdown/move/up listeners, ~40 lines) was considered as a fallback for browsers without non-textarea `resize` support (Safari is the one not verified here); it was rejected as unnecessary complexity for a no-build-step UI. If the grip turns out to be missing in a real browser the user relies on, that is the fallback.

**D2: Fixed default `height`, not content-driven sizing.**
The grip only takes effect once the element has a determinate height; content-driven height plus a `max-height` cap is exactly what leaves the transcript at 60vh for long content. Fixed heights reproduce the textarea's `rows="3"` compact default. Agreed values: `.transcript-panel { height: 14rem }` (~9 lines at 0.95rem font, 1.55 line-height, plus padding) and `.summary-text { height: 10rem }` (~6 lines). A `min-height: 4rem` floor on both prevents the grip from collapsing a panel to a useless sliver.

**D3: Remove the `max-height` caps (60vh / 40vh).**
CSS-driven resizing honors `max-height`, so the old caps would block the user from growing a panel beyond what it could already reach — the opposite of resizing without a cap. The textarea has no cap, and neither panel gets one.

**D4: No persistence.**
Deliberate parity with the injection payload textarea; adding `localStorage` would be a new behavior the user did not ask for.

**D5: E2E verifies CSS state, not a simulated grip drag.**
The native resize grip is a user-agent shadow element, not a DOM node, so Playwright cannot grab it. The new tests assert the observable contract instead: `getComputedStyle(el).resize === 'vertical'`, the default rendered height is determinate and compact (`clientHeight` is smaller than the `scrollHeight` of long content, proving the fixed default plus internal scrolling), `min-height` is present, and a resized height is not restored after a reload (the test sets an explicit inline height, reloads, re-fetches, and expects the default height back — there is no persistence to restore). The existing `test_long_transcript_scrolls` continues to cover the scroll path end-to-end. New tests: `test_transcript_panel_compact_and_resizable` (T-WEB-INTERFACE-018, `tests/e2e/test_ui.py`) and `test_summary_panel_compact_and_resizable` (T-TRANSCRIPT-SUMMARIZATION-061, `tests/e2e/test_summarization.py`).

## Test Strategy

- **E2E UI (primary):** Playwright with headless Chromium against an in-process uvicorn instance whose upstream fetch chain is stubbed (`tests/e2e/test_ui.py`, `tests/e2e/test_summarization.py`). New tests `test_transcript_panel_compact_and_resizable` (T-WEB-INTERFACE-018) and `test_summary_panel_compact_and_resizable` (T-TRANSCRIPT-SUMMARIZATION-061); run one with `uv run python -m pytest tests/e2e/test_ui.py::test_transcript_panel_compact_and_resizable -q`, the whole file with `uv run python -m pytest tests/e2e/ -q`.
- **Regression (non-e2e):** `uv run python -m pytest tests/ -q --ignore=tests/e2e` — the change is CSS-only, so this is an unchanged-code guard.
- **Assertion style:** computed-style and relationship checks only (`resize`, `min-height`, determinate `clientHeight`, `clientHeight < scrollHeight`), never pixel-exact equality, so the tests hold across fonts and DPI (D5).

## Risks / Trade-offs

- [Safari may ignore `resize` on non-textarea elements (not verified in this session)] → e2e target is Chromium and Firefox supports the property; if a user reports a missing grip in their browser, fall back to the JS handle described in D1 without changing the specs.
- [Short transcripts now show a fixed-height box with whitespace below the text] → intended: a consistent compact default, with the grip to shrink or grow it.
- [Computed-height e2e assertions can be brittle across font/DPI environments] → assert relationships (determinate `clientHeight`, `clientHeight < scrollHeight` for long content, `resize`/`min-height` computed values), never pixel-exact equality.
- [Without `max-height`, a user can drag a panel tall enough to scroll the page] → same behavior as the textarea today; accepted.

## Migration Plan

Single static stylesheet change plus two new e2e tests; deploying the app is all that is required. Rollback is reverting the CSS rules. No API, data, or dependency migration.
