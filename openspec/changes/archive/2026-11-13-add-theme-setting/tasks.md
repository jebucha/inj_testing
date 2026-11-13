# Tasks

## 1. Settings backend: theme field, partial-merge write

- [x] 1.1 Add `theme` to the `Settings` dataclass in `app/settings.py`, with the allowed values `{"system", "light", "dark"}` and `system` as the read default; verify `load_settings()` returns `system` for a missing key, a non-string value, and an unrecognized value
- [x] 1.2 Change `save_settings(auto_summarize=None, theme=None)` to read the current settings, overlay only the provided fields, and write the merged object atomically; verify `save_settings(True)` still writes `{"autoSummarize": true}` and that a theme-only call leaves `autoSummarize` untouched
- [x] 1.3 Extend `GET /api/settings` in `app/main.py` to return `theme` alongside `autoSummarize`; verify with `uv run python -m pytest tests/test_settings.py -q` once the tests in 1.5 exist
- [x] 1.4 Change `POST /api/settings` to accept a partial body: validate each recognized field present, reject with 400 `INVALID_BODY` only when no recognized field is present or a present field is invalid, ignore unknown keys, and echo the full persisted settings; verify `uv run python -m pytest tests/test_settings.py -q`
- [x] 1.5 Add the API and module tests T-APP-SETTINGS-010 .. 014 in `tests/test_settings.py` (stored theme read, missing/unrecognized theme default, partial-merge write, invalid theme value, unknown keys ignored) and update the existing T-001 .. 006 tests for the new response shape; verify `uv run python -m pytest tests/test_settings.py -q` exits 0 with no skips
- [x] 1.6 Update the `app/settings.py` and `app/main.py` pages (`docs/settings.md`, `docs/main.md`) for the new field and merge semantics, then run `uv run python docs/generate.py`; verify the regenerated HTML mentions `theme` and that `uv run python -m pytest tests/test_docs_serving.py -q` still passes

## 2. Application palette and header control

- [x] 2.1 Add a dark token block to `app/static/style.css` in both forms demanded by the three-state rule (attribute selector and the `prefers-color-scheme` media query), replace the five `rgba(47, 111, 237, 0.08)` literals with a `--accent-tint` token, and set `color-scheme` per theme; verify visually with `uv run python -m app.main` that every panel, table, log pane and error banner is legible in both palettes
- [x] 2.2 Add the three-option theme `<select>` (System / Light / Dark) to `.app-header-row` in `app/static/index.html` and let the row wrap; verify at a 420px viewport that no element overflows horizontally by running `uv run python -m pytest tests/e2e/test_docs_view.py::test_narrow_viewport_nav_collapses -q`
- [x] 2.3 Load `theme` in `app.js`, apply explicit choices by setting `data-theme` on the document root and remove the attribute for `system`, and persist changes by posting only `{"theme": ...}`; on a failed write revert the select to the last confirmed value; verify the applied attribute and the posted body by inspection plus the tests in 2.4
- [x] 2.4 Add e2e tests T-WEB-INTERFACE-027 .. 031 in `tests/e2e/test_ui.py` (control defaults to System, Dark applies and survives reload, failed write reverts, `system` follows a dark OS via `browser.new_context(color_scheme="dark")`, explicit Light overrides a dark OS) and confirm the dark scheme reaches the native checkbox and select; verify `uv run python -m pytest tests/e2e/test_ui.py -q`
- [x] 2.5 Confirm the auto-summarize suite is untouched by the merge semantics: `uv run python -m pytest tests/e2e/test_auto_summarize.py -q` (its `{"autoSummarize": True}` file assertion must still hold because the checkbox posts only its own field)
- [x] 2.6 Update `docs/static/style-css.md`, `docs/static/index-html.md` and `docs/static/app-js.md` for the tokens, the header control and the theme logic (including the "dark block is duplicated per stylesheet" note), then run `uv run python docs/generate.py`; verify the pages render the new text and `uv run python -m pytest tests/test_docs_serving.py -q` passes

## 3. Docs site palette and embedded-view sync

- [x] 3.1 Add the same three-state dark palette and `color-scheme` to `docs/style.css`; verify by opening `/docs/` directly in a dark-OS browser context and checking that the sidebar, content panel, tables and code blocks are legible with no script on the page
- [x] 3.2 Sync the Docs view: apply and remove the `data-theme` attribute on the iframe's `documentElement`, re-applying it on the iframe's `load` event so in-docs navigation does not revert the palette; verify with T-WEB-INTERFACE-032 in 3.3
- [x] 3.3 Add e2e test T-WEB-INTERFACE-032 in `tests/e2e/test_docs_view.py` (Dark app theme renders the iframe dark; `system` follows the OS there too); verify `uv run python -m pytest tests/e2e/test_docs_view.py -q`
- [x] 3.4 Confirm the docs site still satisfies its invariants after the stylesheet change: `uv run python -m pytest tests/test_docs_serving.py -q` passes, and the regenerated docs pages are byte-identical to a second `uv run python docs/generate.py` run

## 4. Integration: user-facing docs and full verification

- [x] 4.1 Update the README's settings paragraph to document the `theme` field, the three values, the `system` default and the partial-body write contract; verify the documented `settings.json` shape matches what `POST /api/settings` actually writes by exercising both controls against a running server
- [x] 4.2 Run the full non-e2e suite: `uv run python -m pytest tests/ -q --ignore=tests/e2e`; verify exit code 0 with no skipped tests
- [x] 4.3 Run the full e2e suite: `uv run python -m pytest tests/e2e/ -q`; verify exit code 0 and that the narrow-viewport, log-viewer and docs-view layout tests still pass with the new header control
- [x] 4.4 Validate the change artifacts: `openspec validate "add-theme-setting"`; verify it reports the change as valid

## Workflow follow-up

- Bump the minor version before archiving: `uv version --bump minor`.
- Run validation in a fresh session with a model that did not write the code (`/opsx-validate`), and record the report under `openspec/changes/add-theme-setting/validations/`.
- Archive the change once the validation report is clean.
