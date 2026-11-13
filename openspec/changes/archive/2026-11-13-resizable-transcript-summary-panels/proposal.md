# Proposal

## Why

The transcript panel and the summary panel grow with their content and consume
up to 60vh / 40vh of the viewport before they start scrolling, while the
injection payload textarea is small by default (~3 lines) and offers a native
bottom-right resize grip for enlarging it. The two display panels
should have the same behavior: compact by default, user-resizable from a
bottom-right grip, so the page stays readable at a glance and the user
controls how much vertical space each panel takes.

## What Changes

- The transcript panel (`#transcript-panel`) renders at a small fixed default
  height (~14rem, roughly 9 lines) instead of growing up to 60vh; transcripts
  longer than that scroll inside the panel.
- The summary panel (`#summary-text`) renders at a small fixed default height
  (~10rem) instead of growing up to 40vh; longer summaries scroll inside it.
- Both panels expose the browser's native bottom-right resize grip for
  vertical resizing, matching the injection payload textarea; the resize can
  grow the panel without an enforced maximum height (the page scrolls if the
  panel grows past the viewport) and shrink it down to a 4rem minimum height.
- Resized heights are not persisted across page reloads — the same non-
  persistent behavior as the injection payload textarea.
- Other panels (injection preview, log panel, saved-transcript list) are out of
  scope and keep their current sizing.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-interface`: The "Transcript display" requirement changes — the
  transcript panel is small by default and is vertically resizable from a
  bottom-right grip, in addition to remaining scrollable.
- `transcript-summarization`: The "Summary panel and copy" requirement
  changes — the summary panel is small by default and is vertically resizable
  from a bottom-right grip.

## Impact

- `app/static/style.css`: sizing rules for `.transcript-panel` and
  `.summary-text` — fixed default heights with a minimum-height floor and
  vertical resizing instead of `max-height` caps.
- `tests/e2e/test_ui.py` and `tests/e2e/test_summarization.py`: new e2e
  assertions covering the default sizing and the resize behavior; the existing
  long-transcript scroll test must keep passing unchanged.
- No changes to HTML structure, JavaScript, APIs, or dependencies.
