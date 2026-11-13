# Spec Delta

## ADDED Requirements

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
