# Tasks

## 1. Transcript panel (T-WEB-INTERFACE-018)

- [x] 1.1 Update the `.transcript-panel` rule in `app/static/style.css`: replace `max-height: 60vh` with `height: 14rem`, add `min-height: 4rem` and `resize: vertical` (keep `overflow-y: auto`), and leave no `max-height` cap. Verify by running the app (`uv run python -m app.main`) and confirming the panel renders at ~14rem by default, shows the bottom-right resize grip, and a long transcript scrolls inside it.
- [x] 1.2 Add `test_transcript_panel_compact_and_resizable` to `tests/e2e/test_ui.py` implementing T-WEB-INTERFACE-018: after a successful fetch, assert `getComputedStyle` of `#transcript-panel` reports `resize: vertical` and a `min-height` of `4rem`, that the default rendered height is the fixed `14rem` and is smaller than the `scrollHeight` of a long transcript (proving internal scrolling), and that the panel does not grow with content height. Then set an explicit inline height, reload the page, fetch again, and assert the panel is back at `14rem` (no persistence). Add the usual per-test `"""T-WEB-INTERFACE-018"""` docstring and extend the module header's ID range (`.. 017` → `.. 018`). Verify with `uv run python -m pytest tests/e2e/test_ui.py::test_transcript_panel_compact_and_resizable -q` (exit 0).

## 2. Summary panel (T-TRANSCRIPT-SUMMARIZATION-061)

- [x] 2.1 Update the `.summary-text` rule in `app/static/style.css`: replace `max-height: 40vh` with `height: 10rem`, add `min-height: 4rem` and `resize: vertical` (keep `overflow-y: auto`), and leave no `max-height` cap. Verify by running the app and confirming the summary panel renders at ~10rem by default with the resize grip, and a long summary scrolls inside it.
- [x] 2.2 Add `test_summary_panel_compact_and_resizable` to `tests/e2e/test_summarization.py` implementing T-TRANSCRIPT-SUMMARIZATION-061: set `server["stub"].summary` to a multi-line summary long enough to overflow `10rem`, trigger summarize, then assert the same computed-style contract as 1.2 for `#summary-text` (computed `resize: vertical`, `min-height` of `4rem`, fixed `10rem` default height smaller than the summary's `scrollHeight`). Repeat the no-persistence check (set an explicit inline height, reload, fetch, summarize again, assert the panel is back at `10rem`), add the `"""T-TRANSCRIPT-SUMMARIZATION-061"""` docstring, and extend the module header's ID range (`.. 036, 040` → `.. 036, 040, 061`). Verify with `uv run python -m pytest tests/e2e/test_summarization.py::test_summary_panel_compact_and_resizable -q` (exit 0).

## 3. Regression checks (existing behavior, not new requirements)

- [x] 3.1 Re-run the full e2e suite and confirm the pre-existing `test_long_transcript_scrolls` (T-WEB-INTERFACE-006) and all summarization/injection UI tests still pass: `uv run python -m pytest tests/e2e/ -q`.
- [x] 3.2 Run the non-e2e suite to confirm no collateral breakage: `uv run python -m pytest tests/ -q --ignore=tests/e2e` (exit 0).

## Workflow follow-up

- Bump the app's minor version before archiving (user-visible change): `uv version --bump minor` — never hand-edit `pyproject.toml`.
- Validate the implemented change in a fresh session with `openspec-validate-change` before archiving; the validation report goes under `openspec/changes/resizable-transcript-summary-panels/validations/`.
- Archive the change once validation passes (`openspec-archive-change`).
