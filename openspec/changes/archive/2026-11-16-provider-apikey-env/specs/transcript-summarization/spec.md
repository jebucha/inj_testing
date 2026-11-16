# Spec Delta

## MODIFIED Requirements

### Requirement: Provider configuration file
The application SHALL read the summarization provider configuration from a JSON file at the `PROVIDERS_CONFIG` path (default `providers.json`). The file SHALL contain a top-level `provider` object mapping ids to objects with a display name, `options` (`baseURL` required, `apiKey` optional, `apiKeyEnv` optional), and a `models` object keyed by model id in file order. Unknown fields SHALL be ignored and it SHALL be re-read per request. A missing file, malformed JSON, or no usable provider means "not configured".

#### Scenario: Providers are read from the file
- **WHEN** the config file lists provider `radai` with `options.baseURL` set and one model, and a request needs the provider list
- **THEN** the provider list contains provider `radai` with its display name and model id
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-001
  - **File:** tests/test_transcript_summarization.py::test_providers_read_from_config_file
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_providers_read_from_config_file -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Config path taken from environment
- **WHEN** `PROVIDERS_CONFIG` points to a file containing a provider and the default `providers.json` does not exist
- **THEN** the provider list is built from the file the environment variable names
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-002
  - **File:** tests/test_transcript_summarization.py::test_config_path_from_environment
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_config_path_from_environment -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Edits take effect without a restart
- **WHEN** a provider is removed from the config file after the application has served a request
- **THEN** the next request that needs the provider list no longer contains that provider
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-003
  - **File:** tests/test_transcript_summarization.py::test_config_edit_takes_effect_without_restart
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_config_edit_takes_effect_without_restart -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Malformed config is not configured
- **WHEN** the config file contains invalid JSON
- **THEN** the application is treated as not configured for summarization, no request crashes, and the failure is visible in the log without the file contents being echoed into an HTTP response
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-004
  - **File:** tests/test_transcript_summarization.py::test_malformed_config_treated_as_not_configured
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_malformed_config_treated_as_not_configured -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unknown fields are ignored
- **WHEN** the config file contains fields the application does not use (for example `$schema` or a per-provider `npm` field)
- **THEN** the providers listed in the file are still usable
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-005
  - **File:** tests/test_transcript_summarization.py::test_unknown_config_fields_ignored
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_unknown_config_fields_ignored -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Missing display name falls back to the provider id
- **WHEN** a provider entry has no `name` field, or its `name` is empty
- **THEN** the provider is still usable and its display name is the provider id
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-038
  - **File:** tests/test_transcript_summarization.py::test_missing_display_name_falls_back_to_id
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_missing_display_name_falls_back_to_id -q
  - **Pass:** exit code 0, no skipped tests

## ADDED Requirements

### Requirement: Provider API key from environment
A provider entry MAY name the bearer token's environment variable via an optional `options.apiKeyEnv` string. When present, that variable's value SHALL be the provider's API key, resolved from the process environment on each config read, never cached, taking precedence over a literal `options.apiKey`. When the variable is unset or empty, the provider SHALL remain usable as keyless and the application SHALL log a warning event carrying the provider id and the variable name, never any key value.

#### Scenario: Env-named key is sent as the bearer token
- **WHEN** the config file defines a provider with `options.apiKeyEnv` naming a variable whose value is set and non-empty in the process environment, and the summarize endpoint calls that provider
- **THEN** the backend request carries the variable's value as the bearer token
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-062
  - **File:** tests/test_transcript_summarization.py::test_api_key_env_resolved_as_bearer
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_api_key_env_resolved_as_bearer -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: apiKeyEnv takes precedence over a literal apiKey
- **WHEN** a provider entry carries both a literal `options.apiKey` and `options.apiKeyEnv` naming a variable with a different value, and the provider list is read
- **THEN** the provider's effective API key is the variable's value, not the literal
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-063
  - **File:** tests/test_transcript_summarization.py::test_api_key_env_precedes_literal_key
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_api_key_env_precedes_literal_key -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Unset or empty variable degrades to keyless with a warning
- **WHEN** a provider entry carries `options.apiKeyEnv` naming a variable that is unset or set to an empty string in the process environment, and the provider list is read
- **THEN** the provider is still usable with no API key, one warning event records the provider id and the variable name without any key value, and no request crashes
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-064
  - **File:** tests/test_transcript_summarization.py::test_api_key_env_missing_degrades_to_keyless
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_api_key_env_missing_degrades_to_keyless -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Resolved env key never appears in the provider listing
- **WHEN** the config file defines a provider with `options.apiKeyEnv` whose variable is set, and `GET /api/providers` is requested
- **THEN** the response lists the provider's id, display name, and model ids, and contains neither the resolved key nor the variable's value anywhere in the response body
- **Test Requirement**
  - **ID:** T-TRANSCRIPT-SUMMARIZATION-065
  - **File:** tests/test_transcript_summarization.py::test_api_key_env_absent_from_provider_listing
  - **Command:** python -m pytest tests/test_transcript_summarization.py::test_api_key_env_absent_from_provider_listing -q
  - **Pass:** exit code 0, no skipped tests
