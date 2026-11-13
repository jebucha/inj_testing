# Spec Delta

## ADDED Requirements

### Requirement: Theme selection control
The application header SHALL provide a theme control offering exactly three choices — System, Light, and Dark — initialized from the stored `theme` setting, defaulting to System when no readable setting exists. Changing the choice SHALL apply the new theme immediately, persist it through `POST /api/settings`, and on a failed write SHALL revert the control to the last value the server confirmed. The control SHALL NOT cause horizontal overflow at a 420px viewport.

#### Scenario: Control reflects the default on load
- **WHEN** the page loads with no stored theme setting
- **THEN** the theme control offers System, Light, and Dark and shows System as the selected choice
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-027
  - **File:** tests/e2e/test_ui.py::test_theme_control_defaults_to_system
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_theme_control_defaults_to_system -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Choosing Dark applies and persists the theme
- **WHEN** the user selects Dark in the theme control and the settings write succeeds
- **THEN** the page renders with the dark palette immediately, `settings.json` stores theme dark, and after a page reload the control still shows Dark and the page still renders the dark palette
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-028
  - **File:** tests/e2e/test_ui.py::test_theme_dark_applies_and_persists
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_theme_dark_applies_and_persists -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Failed theme write reverts the control
- **WHEN** the settings write fails after the user selects Dark
- **THEN** the theme control returns to the last persisted choice, the page renders that persisted theme, and settings.json is unchanged
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-029
  - **File:** tests/e2e/test_ui.py::test_theme_write_failure_reverts_control
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_theme_write_failure_reverts_control -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Theme application
The selected theme SHALL govern every surface of the page and the native form controls and scrollbars the browser renders. In System mode the page SHALL follow the operating system's light or dark preference, including changes made without a reload. An explicit Light or Dark choice SHALL override the operating system preference. The embedded docs view SHALL render in the application's theme; the docs site opened in its own window SHALL follow the operating system preference.

#### Scenario: System mode follows a dark operating system
- **WHEN** the page loads with no stored theme and the operating system prefers dark
- **THEN** the page renders the dark palette, and the checkbox and select controls render in a dark scheme matching it
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-030
  - **File:** tests/e2e/test_ui.py::test_theme_system_follows_dark_os
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_theme_system_follows_dark_os -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Explicit Light overrides a dark operating system
- **WHEN** the stored theme is Light and the operating system prefers dark
- **THEN** the page renders the light palette
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-031
  - **File:** tests/e2e/test_ui.py::test_theme_explicit_light_overrides_dark_os
  - **Command:** python -m pytest tests/e2e/test_ui.py::test_theme_explicit_light_overrides_dark_os -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Docs view matches the application theme
- **WHEN** the stored theme is Dark and the user opens the Docs view
- **THEN** the documentation page inside the iframe renders with the dark palette, and with the stored theme System the documentation follows the operating system preference
- **Test Requirement**
  - **ID:** T-WEB-INTERFACE-032
  - **File:** tests/e2e/test_docs_view.py::test_docs_view_follows_app_theme
  - **Command:** python -m pytest tests/e2e/test_docs_view.py::test_docs_view_follows_app_theme -q
  - **Pass:** exit code 0, no skipped tests
