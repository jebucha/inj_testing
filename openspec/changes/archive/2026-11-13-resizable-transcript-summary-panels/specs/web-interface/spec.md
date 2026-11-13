# Spec Delta

## MODIFIED Requirements

### Requirement: Transcript display
On a successful fetch, the interface SHALL display the transcript text in a scrollable panel, together with the video title and the language used, and SHALL enable the copy button. The interface SHALL insert fetched content (transcript text, video title, language) into the page as plain text only (for example, via `textContent`) and never as HTML, so that markup-like content from YouTube cannot be rendered or executed. The panel SHALL have a fixed default height of `14rem` and SHALL NOT enforce a maximum height; a transcript taller than the default height SHALL scroll inside the panel. The panel SHALL expose the browser's native vertical resize control in its bottom-right corner (`resize: vertical`, matching the injection payload textarea), SHALL allow the user to enlarge it without an enforced maximum height and to reduce it no further than a `4rem` minimum height, and a resized height SHALL NOT persist across a page reload.

#### Scenario: Successful result shown
- **WHEN** the transcript request succeeds
- **THEN** the transcript text, the video title, and the language are displayed and the copy button is enabled
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-005
  - **File:** tests/e2e/test_ui.py::test_result_shown_and_copy_enabled
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_result_shown_and_copy_enabled -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Long transcript
- **WHEN** the transcript exceeds the visible height of the panel
- **THEN** the panel scrolls without the page layout breaking
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-006
  - **File:** tests/e2e/test_ui.py::test_long_transcript_scrolls
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_long_transcript_scrolls -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Compact default height with vertical resize control
- **WHEN** a transcript is displayed in the panel
- **THEN** the panel occupies its fixed `14rem` default height, exposes the browser's vertical resize control in its bottom-right corner, cannot be reduced below a `4rem` minimum height, scrolls a transcript taller than the default height inside itself instead of stretching, and after a page reload and a fresh fetch is back at the `14rem` default height (a resized height does not persist)
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-018
  - **File:** tests/e2e/test_ui.py::test_transcript_panel_compact_and_resizable
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_transcript_panel_compact_and_resizable -q
  - **Pass:** exit code 0, no skipped tests
