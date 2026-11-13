"""E2E benchmark difficulty-picker tests (T-PROMPT-INJECTION-BENCHMARK-031
.. 038).

The same in-process uvicorn + stubbed fetch chain + recording chat-
completions stub pattern as tests/e2e/test_injection_benchmark.py: a real
uvicorn instance of the app runs in a thread with the upstream fetch chain
stubbed and the dispatch seam replaced by a recording stub, so no real LLM
traffic happens. The provider config is a temporary file wired in via
PROVIDERS_CONFIG; the picker scenarios run against a small fixture dataset
wired via BENCHMARK_DATASET, and the fetch-failure scenario points the same
variable at a nonexistent path (the endpoint resolves it per request, so
the swap is per-test).

Run:  python -m pytest tests/e2e/ -q
(One-time:  python -m playwright install chromium)
"""

import json
import os
import threading

import pytest
from playwright.sync_api import sync_playwright

from app import chain as chain_mod
from app import summarize as summarize_mod
from tests.e2e.test_injection_benchmark import (
    LlmStub,
    PROVIDER_CONFIG,
    _select_benchmark_models,
    _wait_rows,
)
from tests.e2e.test_ui import (
    DEFAULT_PAYLOAD,
    StubChain,
    _fetch,
    _free_port,
    _wait_ready,
    _wait_result,
)

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# The small fixture dataset: two easy entries (so a re-roll can return a
# different prompt), one each of medium and hard.
DATASET_ENTRIES = [
    {"id": "easy-1", "difficulty": "easy", "prompt": "EASY_PROMPT_ONE"},
    {"id": "easy-2", "difficulty": "easy", "prompt": "EASY_PROMPT_TWO"},
    {"id": "medium-1", "difficulty": "medium", "prompt": "MEDIUM_PROMPT_ONE"},
    {"id": "hard-1", "difficulty": "hard", "prompt": "HARD_PROMPT_ONE"},
]
EASY_PROMPTS = {e["prompt"] for e in DATASET_ENTRIES if e["difficulty"] == "easy"}
ALL_DATASET_IDS = {e["id"] for e in DATASET_ENTRIES}

BENCHMARKS_URL = "/api/benchmarks"


# --- fixtures -----------------------------------------------------------------


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    from app import main as app_main
    import uvicorn

    stub = StubChain()
    llm_stub = LlmStub()
    original_chain = chain_mod.default_chain
    chain_mod.default_chain = stub
    original_dispatch = summarize_mod._call_chat_completions
    summarize_mod._call_chat_completions = llm_stub

    tmp = tmp_path_factory.mktemp("benchmark-picker")
    config_file = tmp / "providers.json"
    config_file.write_text(json.dumps(PROVIDER_CONFIG, indent=2), encoding="utf-8")
    transcript_dir = tmp / "transcripts"
    transcript_dir.mkdir()
    dataset_file = tmp / "benchmark.jsonl"
    dataset_file.write_text(
        "\n".join(json.dumps(e) for e in DATASET_ENTRIES) + "\n",
        encoding="utf-8",
    )
    original_env = {
        key: os.environ.get(key)
        for key in ("PROVIDERS_CONFIG", "TRANSCRIPT_DIR", "BENCHMARK_DATASET")
    }
    os.environ["PROVIDERS_CONFIG"] = str(config_file)
    os.environ["TRANSCRIPT_DIR"] = str(transcript_dir)
    os.environ["BENCHMARK_DATASET"] = str(dataset_file)

    port = _free_port()
    config = uvicorn.Config(app_main.app, host="0.0.0.0", port=port, log_level="warning")
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    _wait_ready(port)

    yield {
        "port": port,
        "stub": stub,
        "llm_stub": llm_stub,
        "dataset_file": dataset_file,
        # The fetch-failure scenario points BENCHMARK_DATASET here.
        "missing_dataset": tmp / "absent-benchmark.jsonl",
        "localhost_base": f"http://localhost:{port}",
    }

    uvicorn_server.should_exit = True
    thread.join(timeout=10)
    chain_mod.default_chain = original_chain
    summarize_mod._call_chat_completions = original_dispatch
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="module")
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(autouse=True)
def _reset_stub(server):
    """Fresh stub state (scenario + call logs) for every test."""
    server["stub"].calls = []
    server["stub"].set_success()
    server["llm_stub"].reset()
    yield


@pytest.fixture
def browser(playwright):
    b = playwright.chromium.launch()
    yield b
    b.close()


@pytest.fixture()
def page(browser, server):
    """Page served over http://localhost (secure context)."""
    context = browser.new_context(viewport={"width": 1024, "height": 640})
    pg = context.new_page()
    pg.goto(server["localhost_base"] + "/")
    yield pg
    context.close()


@pytest.fixture
def missing_dataset(server, monkeypatch):
    """Point BENCHMARK_DATASET at a nonexistent path for this test only."""
    monkeypatch.setenv("BENCHMARK_DATASET", str(server["missing_dataset"]))
    yield


# --- helpers --------------------------------------------------------------------


def _payload_value(page):
    return page.locator("#injection-payload").input_value()


def _wait_payload(page, value=None):
    """Wait for the payload field to hold a value (or one specific value)."""
    if value is None:
        page.wait_for_function(
            "() => document.getElementById('injection-payload').value !== ''",
            timeout=10_000,
        )
    else:
        page.wait_for_function(
            "(v) => document.getElementById('injection-payload').value === v",
            arg=value,
            timeout=10_000,
        )


# --- T-PROMPT-INJECTION-BENCHMARK-031 .. 033: picker and manual deselect --------


def test_picker_defaults_to_manual_payload(page):
    """T-PROMPT-INJECTION-BENCHMARK-031"""
    picker = page.locator("#difficulty-picker")
    # the placeholder option is present and is the one selected
    assert picker.input_value() == "manual"
    selected = picker.locator("option[selected]")
    assert selected.count() == 1
    assert selected.get_attribute("value") == "manual"
    # the payload field is untouched
    assert _payload_value(page) == ""


def test_selecting_difficulty_populates_payload(page):
    """T-PROMPT-INJECTION-BENCHMARK-032"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    page.select_option("#difficulty-picker", "easy")
    _wait_payload(page)
    payload = _payload_value(page)
    assert payload in EASY_PROMPTS

    # the injection control is enabled: checked, and the payload field
    # shown and editable
    assert page.locator("#injection-toggle").is_checked()
    assert not page.locator("#injection-payload").is_hidden()
    assert not page.locator("#injection-payload").is_disabled()

    # the preview shows the prompt spliced into the transcript at the
    # default insertion point (append: transcript, then the payload)
    preview = page.locator("#injection-preview")
    assert not preview.is_hidden()
    assert DEFAULT_PAYLOAD["text"] in preview.inner_text()
    assert preview.inner_text().endswith(payload)


def test_manual_payload_preserves_text(page):
    """T-PROMPT-INJECTION-BENCHMARK-033"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    page.select_option("#difficulty-picker", "easy")
    _wait_payload(page)
    kept = _payload_value(page)
    assert kept in EASY_PROMPTS

    page.select_option("#difficulty-picker", "manual")

    # the field retains its content unchanged...
    assert _payload_value(page) == kept
    # ...and remains editable
    assert not page.locator("#injection-payload").is_disabled()
    page.click("#injection-payload")
    page.keyboard.press("End")
    page.type("#injection-payload", "!")
    assert _payload_value(page) == kept + "!"


# --- T-PROMPT-INJECTION-BENCHMARK-034 .. 035: re-roll ----------------------------


def test_reroll_fetches_fresh_prompt(page):
    """T-PROMPT-INJECTION-BENCHMARK-034"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    page.select_option("#difficulty-picker", "easy")
    _wait_payload(page)

    with page.expect_response(
        lambda r: r.url.endswith(BENCHMARKS_URL + "?difficulty=easy")
    ) as info:
        page.click("#benchmark-reroll")
    data = info.value.json()
    assert data["difficulty"] == "easy"
    assert data["prompt"] in EASY_PROMPTS

    # the payload field is replaced with the freshly fetched prompt
    _wait_payload(page, data["prompt"])
    assert _payload_value(page) == data["prompt"]


def test_reroll_disabled_for_manual_payload(page):
    """T-PROMPT-INJECTION-BENCHMARK-035"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    # the default placeholder: the re-roll control is disabled
    assert page.locator("#benchmark-reroll").is_disabled()

    # a dataset difficulty selected: enabled
    page.select_option("#difficulty-picker", "hard")
    _wait_payload(page)
    assert not page.locator("#benchmark-reroll").is_disabled()

    # back to the placeholder: disabled again
    page.select_option("#difficulty-picker", "manual")
    assert page.locator("#benchmark-reroll").is_disabled()


# --- T-PROMPT-INJECTION-BENCHMARK-036 .. 037: result-row dataset id --------------


def test_result_row_shows_dataset_id(page):
    """T-PROMPT-INJECTION-BENCHMARK-036"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    with page.expect_response(
        lambda r: r.url.endswith(BENCHMARKS_URL + "?difficulty=medium")
    ) as info:
        page.select_option("#difficulty-picker", "medium")
    data = info.value.json()
    _wait_payload(page, data["prompt"])

    _select_benchmark_models(page, "Alpha Local — model-a1", "Alpha Local — model-a2")
    page.click("#benchmark-run")
    _wait_rows(page, 2)

    rows = page.locator(".bench-row")
    assert rows.count() == 2
    # each result row of the run displays the seeded entry's id
    for i in range(2):
        assert data["id"] in rows.nth(i).text_content()


def test_result_row_no_id_for_manual_payload(page):
    """T-PROMPT-INJECTION-BENCHMARK-037"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    # a manual payload: the picker is left on its placeholder
    assert page.locator("#difficulty-picker").input_value() == "manual"
    page.check("#injection-toggle")
    page.fill("#injection-payload", "MANUALLY_TYPED_PAYLOAD")
    _select_benchmark_models(page, "Alpha Local — model-a1")
    page.click("#benchmark-run")
    _wait_rows(page, 1)

    row_text = page.locator(".bench-row").first.text_content()
    for dataset_id in ALL_DATASET_IDS:
        assert dataset_id not in row_text
    assert "Dataset:" not in row_text


# --- T-PROMPT-INJECTION-BENCHMARK-038: failed fetch ------------------------------


def test_fetch_failure_blocks_run(page, server, missing_dataset):
    """T-PROMPT-INJECTION-BENCHMARK-038"""
    _fetch(page, VIDEO_URL)
    _wait_result(page)

    # fresh panel: no benchmark models selected, so the run control is
    # disabled before the pick is attempted
    assert page.locator("#benchmark-run").is_disabled()

    page.select_option("#difficulty-picker", "easy")

    # the failed fetch shows an error message in the status line...
    page.wait_for_function(
        "() => !document.getElementById('difficulty-error').hidden",
        timeout=10_000,
    )
    assert page.locator("#difficulty-error").inner_text()

    # ...and the toggle this fetch turned on is turned back off, so the
    # existing enable logic keeps "Run benchmark" disabled
    assert not page.locator("#injection-toggle").is_checked()
    assert page.locator("#benchmark-run").is_disabled()
