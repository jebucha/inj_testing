# Spec Delta

## ADDED Requirements

### Requirement: Theme setting values
The `theme` setting SHALL accept exactly three values: `system` (the default), `light`, and `dark`. A write that carries a `theme` value outside this set SHALL be rejected with 400 and error code `INVALID_BODY` without writing the file. A write body MAY carry keys outside the recognized setting fields; those keys SHALL be ignored and SHALL never be persisted.

#### Scenario: Unrecognized theme value is rejected
- **WHEN** `POST /api/settings` is called with `{"theme": "sepia"}`
- **THEN** the response is 400 with error code `INVALID_BODY` and the settings file content is unchanged
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-012
  - **File:** tests/test_settings.py::test_settings_theme_invalid_value_rejected
  - **Command:** python -m pytest tests/test_settings.py::test_settings_theme_invalid_value_rejected -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unknown keys are ignored
- **WHEN** `POST /api/settings` is called with `{"theme": "dark", "unexpected": 1}`
- **THEN** the response is 200 with `theme` dark, the settings file contains the theme and no `unexpected` key, and a later read returns theme dark
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-013
  - **File:** tests/test_settings.py::test_settings_unknown_keys_ignored
  - **Command:** python -m pytest tests/test_settings.py::test_settings_unknown_keys_ignored -q
  - **Pass:** exit code 0, no skipped tests

## MODIFIED Requirements

### Requirement: Settings read endpoint
The application SHALL expose a read-only `GET /api/settings` endpoint returning 200 with an `autoSummarize` boolean field and a `theme` string field, read from `settings.json` in the transcript directory at request time so edits on disk take effect without a restart.

#### Scenario: Stored flag is returned
- **WHEN** `settings.json` in the transcript directory contains `{"autoSummarize": true}` and `GET /api/settings` is requested
- **THEN** the response is 200 with `autoSummarize` true
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-001
  - **File:** tests/test_settings.py::test_settings_read_returns_stored_flag
  - **Command:** python -m pytest tests/test_settings.py::test_settings_read_returns_stored_flag -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Stored theme is returned
- **WHEN** `settings.json` in the transcript directory contains `{"theme": "dark"}` and `GET /api/settings` is requested
- **THEN** the response is 200 with `theme` dark
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-010
  - **File:** tests/test_settings.py::test_settings_read_returns_stored_theme
  - **Command:** python -m pytest tests/test_settings.py::test_settings_read_returns_stored_theme -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Missing or unrecognized theme reads as system
- **WHEN** `settings.json` contains no `theme` key, or a `theme` that is not one of `system`, `light`, or `dark`, and `GET /api/settings` is requested
- **THEN** the response is 200 with `theme` system and no request fails
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-011
  - **File:** tests/test_settings.py::test_settings_read_missing_theme_defaults_system
  - **Command:** python -m pytest tests/test_settings.py::test_settings_read_missing_theme_defaults_system -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Settings edits take effect without a restart
- **WHEN** `settings.json` is changed on disk after the application has served a `GET /api/settings` request
- **THEN** the next `GET /api/settings` reflects the new file content
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-004
  - **File:** tests/test_settings.py::test_settings_edit_takes_effect_without_restart
  - **Command:** python -m pytest tests/test_settings.py::test_settings_edit_takes_effect_without_restart -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Settings default when unusable
A missing settings file, an unreadable file, malformed JSON, or a non-boolean `autoSummarize` value SHALL yield `autoSummarize: false` and `theme: "system"` from `GET /api/settings` — a safe default, never an error response. A malformed or unreadable file SHALL additionally be recorded in the log, and file contents SHALL NOT be echoed into the response.

#### Scenario: Missing settings file defaults to off
- **WHEN** the transcript directory contains no `settings.json` and `GET /api/settings` is requested
- **THEN** the response is 200 with `autoSummarize` false and `theme` system, and no file is created
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-002
  - **File:** tests/test_settings.py::test_settings_read_missing_file_defaults_off
  - **Command:** python -m pytest tests/test_settings.py::test_settings_read_missing_file_defaults_off -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unusable settings file is not an error
- **WHEN** `settings.json` contains invalid JSON or a non-boolean `autoSummarize` value and `GET /api/settings` is requested
- **THEN** the response is 200 with `autoSummarize` false and `theme` system, the failure is visible in the log for the malformed-JSON case without the file contents appearing in the response, and no request crashes
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-003
  - **File:** tests/test_settings.py::test_settings_read_unusable_file_defaults_off
  - **Command:** python -m pytest tests/test_settings.py::test_settings_read_unusable_file_defaults_off -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Settings write endpoint
The application SHALL expose `POST /api/settings` accepting a JSON object carrying any subset of the recognized setting fields (`autoSummarize` boolean, `theme` string). The named fields SHALL be merged into the currently stored settings, persisted to `settings.json` in the transcript directory, and echoed back as the full persisted settings with 200: `autoSummarize` and `theme` are both always present in the response, with unset fields reported at their defaults. A body that is not a JSON object, whose recognized fields hold invalid values, or that carries no recognized field at all SHALL be rejected with 400 and error code `INVALID_BODY` without writing the file.

#### Scenario: Write persists and echoes the flag
- **WHEN** `POST /api/settings` is called with `{"autoSummarize": true}`
- **THEN** the response is 200 with `autoSummarize` true and `theme` system, `settings.json` in the transcript directory contains the setting, and a subsequent `GET /api/settings` returns true
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-005
  - **File:** tests/test_settings.py::test_settings_write_persists_and_echoes
  - **Command:** python -m pytest tests/test_settings.py::test_settings_write_persists_and_echoes -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Partial write leaves the other field untouched
- **WHEN** `settings.json` stores `{"autoSummarize": true, "theme": "dark"}` and `POST /api/settings` is called with `{"theme": "light"}`
- **THEN** the response is 200 with `theme` light and `autoSummarize` true, and a subsequent read returns both values
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-014
  - **File:** tests/test_settings.py::test_settings_write_merges_partial_body
  - **Command:** python -m pytest tests/test_settings.py::test_settings_write_merges_partial_body -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Invalid body is rejected without a write
- **WHEN** `POST /api/settings` is called with a non-object body, with a non-boolean `autoSummarize`, with an unrecognized `theme` value, or with no recognized setting field at all
- **THEN** the response is 400 with error code `INVALID_BODY` and the settings file content is unchanged
- **Test Requirement**
  - **ID:** T-APP-SETTINGS-006
  - **File:** tests/test_settings.py::test_settings_write_invalid_body_rejected
  - **Command:** python -m pytest tests/test_settings.py::test_settings_write_invalid_body_rejected -q
  - **Pass:** exit code 0, no skipped tests
