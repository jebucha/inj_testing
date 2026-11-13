# web-interface Specification

## Purpose

A single-page web interface where the user pastes a YouTube URL, fetches the transcript with visible loading and error states, reads the result, and copies it to the clipboard with visible confirmation — working over plain HTTP and HTTPS alike.

## Requirements

### Requirement: Web page availability
The application SHALL serve a single-page user interface at the root path over plain HTTP, with no build step, no client-side framework, and no external CDN dependencies.

#### Scenario: Root path serves the UI
- **WHEN** the browser requests `GET /`
- **THEN** the page loads and renders the URL input, fetch button, transcript area, and copy button without any external network resources
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-001
  - **File:** tests/e2e/test_ui.py::test_root_serves_ui
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_root_serves_ui -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Transcript request flow
The interface SHALL let the user paste a YouTube URL and request the transcript by clicking the fetch button or pressing Enter in the input field. While a request is in flight, the fetch button SHALL be disabled and a visible loading indicator SHALL be shown.

#### Scenario: Fetch with button
- **WHEN** the user pastes a valid YouTube URL and clicks the fetch button
- **THEN** the button becomes disabled with a loading indicator until the response arrives
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-002
  - **File:** tests/e2e/test_ui.py::test_fetch_button_shows_loading
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_fetch_button_shows_loading -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Fetch with Enter key
- **WHEN** the user presses Enter in the URL input field containing a valid YouTube URL
- **THEN** the transcript request is sent, identical to clicking the fetch button
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-003
  - **File:** tests/e2e/test_ui.py::test_fetch_with_enter_key
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_fetch_with_enter_key -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Empty input
- **WHEN** the user triggers a fetch while the input field is empty
- **THEN** no request is sent and no error is displayed
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-004
  - **File:** tests/e2e/test_ui.py::test_empty_input_sends_no_request
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_empty_input_sends_no_request -q
  - **Pass:** exit code 0, no skipped tests

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

### Requirement: Copy transcript button
The interface SHALL provide a "Copy transcript" button that copies the full plain transcript to the clipboard using the asynchronous Clipboard API when available, and SHALL fall back to a legacy copy method (hidden textarea plus `execCommand("copy")`) when the Clipboard API is unavailable, such as over plain HTTP. After a successful copy the button SHALL display visible confirmation (for example, "Copied!").

#### Scenario: Copy over HTTPS or localhost
- **WHEN** the Clipboard API is available and the user clicks "Copy transcript"
- **THEN** the full transcript is on the clipboard and the button shows a "Copied!" confirmation
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-007
  - **File:** tests/e2e/test_ui.py::test_copy_over_localhost
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_copy_over_localhost -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Copy over plain HTTP
- **WHEN** the app is reached at `http://<server-ip>:<port>` where the Clipboard API is unavailable, and the user clicks "Copy transcript"
- **THEN** the full transcript is still copied to the clipboard via the legacy fallback and the button shows a "Copied!" confirmation
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-008
  - **File:** tests/e2e/test_ui.py::test_copy_over_plain_http
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_copy_over_plain_http -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: No transcript yet
- **WHEN** no transcript has been fetched successfully in the current session
- **THEN** the copy button is disabled
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-009
  - **File:** tests/e2e/test_ui.py::test_copy_disabled_before_fetch
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_copy_disabled_before_fetch -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Error display
For a failed fetch, the interface SHALL display a human-readable error message specific to the failure cause (invalid URL, video unavailable, no captions, upstream failure, busy) in a visible error region, SHALL keep the URL input editable, and SHALL re-enable the fetch button when the response arrives.

#### Scenario: Invalid URL error shown
- **WHEN** the user pastes a non-YouTube URL and fetches
- **THEN** an error message identifying the input as not a valid YouTube URL is displayed and the input remains editable
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-010
  - **File:** tests/e2e/test_ui.py::test_invalid_url_error_shown
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_invalid_url_error_shown -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Video unavailable error shown
- **WHEN** the fetch fails with the video-unavailable error code
- **THEN** an error message explains that the video is unavailable (private, deleted, or region-locked)
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-011
  - **File:** tests/e2e/test_ui.py::test_video_unavailable_error_shown
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_video_unavailable_error_shown -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: No captions error shown
- **WHEN** the fetch fails with the no-captions error code
- **THEN** an error message explains that the video has no available captions
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-012
  - **File:** tests/e2e/test_ui.py::test_no_captions_error_shown
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_no_captions_error_shown -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Upstream failure error shown
- **WHEN** the fetch fails with the upstream-failure error code
- **THEN** an error message suggests that YouTube may be rate-limiting or blocking the server and that retrying later may succeed
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-013
  - **File:** tests/e2e/test_ui.py::test_upstream_failure_error_shown
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_upstream_failure_error_shown -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Busy error shown
- **WHEN** the fetch fails with the busy error code because another fetch is already in flight
- **THEN** an error message says the server is busy and to try again in a moment
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-014
  - **File:** tests/e2e/test_ui.py::test_busy_error_shown
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_busy_error_shown -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Result header layout
The interface SHALL render the video title on its own line above the action toolbar, bounding the title's visible height to at most two lines and truncating overflow with a visible ellipsis, while exposing the complete untruncated title as plain text via the title element's DOM text and a hover tooltip attribute. The action toolbar SHALL wrap onto additional lines within the page width instead of narrowing the title into a column beside it.

#### Scenario: Long title stays bounded
- **WHEN** a successful fetch returns a video whose title is far longer than the available header width
- **THEN** the title is displayed above the action toolbar, occupies at most two visible lines with an ellipsis, and does not render as a tall narrow vertical column of text
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-015
  - **File:** tests/e2e/test_ui.py::test_long_title_stays_bounded
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_long_title_stays_bounded -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Full title available on hover
- **WHEN** a long title is visually truncated
- **THEN** the title element exposes the complete, untruncated title as plain text via its DOM text and a hover tooltip attribute
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-016
  - **File:** tests/e2e/test_ui.py::test_long_title_tooltip
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_long_title_tooltip -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Action toolbar wraps at narrow widths
- **WHEN** the browser viewport is narrower than the width required to place all action toolbar controls on one line
- **THEN** the controls wrap onto additional lines and remain fully visible within the page width, with no horizontal overflow
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-017
  - **File:** tests/e2e/test_ui.py::test_result_actions_wrap_narrow
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_result_actions_wrap_narrow -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Application view navigation
The interface SHALL render an application frame with a left-pane navigation containing exactly two items, "Transcripts" and "Docs". The Transcripts view SHALL contain the full existing interface and SHALL be the active view on page load. Clicking a navigation item SHALL display the corresponding view, mark that item as active, and hide the other view. The selected view SHALL NOT persist across a page reload.

#### Scenario: Transcripts is the default view
- **WHEN** the page loads
- **THEN** the "Transcripts" navigation item is marked active, the Transcripts content (URL input, fetch button, and the rest of the existing interface) is visible, and the Docs view is hidden
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-019
  - **File:** tests/e2e/test_docs_view.py::test_transcripts_default_view
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_transcripts_default_view -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Switch to the Docs view
- **WHEN** the user clicks the "Docs" navigation item
- **THEN** the Docs view is visible, the Transcripts content is hidden, and the "Docs" item is marked active
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-020
  - **File:** tests/e2e/test_docs_view.py::test_switch_to_docs_view
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_switch_to_docs_view -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Return to the Transcripts view
- **WHEN** the user clicks the "Transcripts" navigation item while the Docs view is visible
- **THEN** the Transcripts content is visible again, the "Transcripts" item is marked active, and a transcript fetched before the switch is still displayed in the result section
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-021
  - **File:** tests/e2e/test_docs_view.py::test_return_to_transcripts_view
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_return_to_transcripts_view -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: View selection does not persist across reload
- **WHEN** the user switches to the Docs view and then reloads the page
- **THEN** the Transcripts view is the active view on load and the Docs view is hidden
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-025
  - **File:** tests/e2e/test_docs_view.py::test_view_selection_not_persisted
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_view_selection_not_persisted -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Docs view embedding
When the Docs view is active, the interface SHALL display the documentation in an embedded iframe pointing at the docs landing page, sized to fill the main pane, and SHALL NOT insert documentation content into the application's DOM as HTML. The Docs view SHALL provide a link that opens the docs landing page in a new window.

#### Scenario: Docs rendered inside the iframe
- **WHEN** the Docs view is active
- **THEN** the visible Docs view contains an iframe whose src is the docs landing path, the iframe is sized to fill the main pane, and the docs' own navigation is rendered inside the iframe's document
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-022
  - **File:** tests/e2e/test_docs_view.py::test_docs_rendered_in_iframe
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_docs_rendered_in_iframe -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Open docs in a new window
- **WHEN** the user clicks the Docs view's open-in-new-window link
- **THEN** a new browser window or tab opens on the docs landing page
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-023
  - **File:** tests/e2e/test_docs_view.py::test_docs_open_in_new_window
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_docs_open_in_new_window -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Documentation content stays out of the app DOM
- **WHEN** the Docs view is active
- **THEN** the application's document contains no documentation markup outside the iframe — the Docs view section holds only its toolbar (the open-in-new-window link) and the iframe, which loads via `src` (no `srcdoc`, no injected docs HTML)
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-026
  - **File:** tests/e2e/test_docs_view.py::test_docs_not_inserted_into_app_dom
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_docs_not_inserted_into_app_dom -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Navigation at narrow viewports
At a viewport width of 800px or less the left-pane navigation SHALL collapse to a horizontal row above the view content, and at a 420px viewport the page SHALL NOT overflow horizontally.

#### Scenario: Navigation collapses at narrow width
- **WHEN** the viewport width is 420px
- **THEN** the two navigation items are laid out in a horizontal row above the view content, and no element overflows the viewport horizontally
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-024
  - **File:** tests/e2e/test_docs_view.py::test_narrow_viewport_nav_collapses
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_narrow_viewport_nav_collapses -q
  - **Pass:** exit code 0, no skipped tests
