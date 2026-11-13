# Spec Delta

## MODIFIED Requirements

### Requirement: Summary panel and copy
On a successful summarization, the interface SHALL display the summary in a dedicated panel with a copy action; the panel SHALL stay hidden until shown, clear when a new transcript is displayed, and load a previously saved summary when the saved transcript has one. When auto-summarize is enabled and a freshly fetched transcript already has a saved summary, the panel SHALL also load and show it. The copy action SHALL copy the full summary with a visible "Copied!" confirmation. Failed summarizations SHALL display a cause-specific error message. Summary text SHALL be inserted as plain text only, never HTML. The panel SHALL have a fixed default height of `10rem` and SHALL NOT enforce a maximum height; a summary taller than the default height SHALL scroll inside the panel. The panel SHALL expose the browser's native vertical resize control in its bottom-right corner (`resize: vertical`, matching the injection payload textarea), SHALL allow the user to enlarge it without an enforced maximum height and to reduce it no further than a `4rem` minimum height, and a resized height SHALL NOT persist across a page reload.

#### Scenario: Summary shown on success
- **WHEN** a summarize request succeeds
- **THEN** the summary panel is visible, shows the summary text, and its copy action is available
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-030
  - **File:** tests/e2e/test_summarization.py::test_summary_shown_on_success
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_summary_shown_on_success -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Copy summary to clipboard
- **WHEN** a summary is displayed and the user triggers the summary copy action
- **THEN** the full summary text is on the clipboard and the action shows a "Copied!" confirmation
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-031
  - **File:** tests/e2e/test_summarization.py::test_copy_summary_to_clipboard
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_copy_summary_to_clipboard -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: New transcript clears the summary
- **WHEN** a summary is displayed and the user fetches a different transcript (or clicks another saved transcript)
- **THEN** the summary panel no longer shows the previous summary
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-032
  - **File:** tests/e2e/test_summarization.py::test_new_transcript_clears_summary
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_new_transcript_clears_summary -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Saved summary loaded with its transcript
- **WHEN** a saved transcript with an existing summary file is clicked in the list
- **THEN** the transcript is displayed and the summary panel shows the saved summary
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-033
  - **File:** tests/e2e/test_summarization.py::test_saved_summary_loaded_with_transcript
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_saved_summary_loaded_with_transcript -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Saved transcript without summary shows no panel
- **WHEN** a saved transcript without a summary file is clicked in the list
- **THEN** the transcript is displayed and the summary panel stays hidden
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-034
  - **File:** tests/e2e/test_summarization.py::test_no_summary_panel_without_saved_summary
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_no_summary_panel_without_saved_summary -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Summarization error shown
- **WHEN** a summarize request fails with the `PROVIDER_ERROR`, `NOT_CONFIGURED`, or `INVALID_PROVIDER` error code
- **THEN** an error message specific to that cause is displayed in the error region, no summary panel content is shown, and the page remains usable with the Summarize button re-enabled
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-035
  - **File:** tests/e2e/test_summarization.py::test_summarize_error_shown
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_summarize_error_shown -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Markup-like summary content is not rendered
- **WHEN** a summary contains HTML-like markup (for example a `<script>` tag)
- **THEN** the markup is displayed as plain text, not rendered or executed
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-036
  - **File:** tests/e2e/test_summarization.py::test_summary_markup_shown_as_text
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_summary_markup_shown_as_text -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Compact default height with vertical resize control
- **WHEN** a summary is displayed in the panel
- **THEN** the summary panel occupies its fixed `10rem` default height, exposes the browser's vertical resize control in its bottom-right corner, cannot be reduced below a `4rem` minimum height, scrolls a summary taller than the default height inside itself instead of stretching, and after a page reload and a fresh summarization is back at the `10rem` default height (a resized height does not persist)
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-061
  - **File:** tests/e2e/test_summarization.py::test_summary_panel_compact_and_resizable
  - **Command:** python -m pytest tests/e2e/test_summarization.py::test_summary_panel_compact_and_resizable -q
  - **Pass:** exit code 0, no skipped tests
