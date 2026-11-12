"""E2E model-management tests (T-SUMMARIZATION-MODEL-MANAGEMENT-029 .. 041).

A real uvicorn instance of the app runs in-process (thread) with the upstream
fetch chain stubbed (as in test_ui.py) and both backend seams replaced by
recording stubs — app/summarize._call_chat_completions and
app/model_discovery._get_provider_models — so no real LLM traffic happens.
The provider config is a temporary file wired in via PROVIDERS_CONFIG; the
app reads it per request, so tests can edit or remove it between requests.
The transcript directory (and with it provider_overrides.json) is a fresh
per-test directory via TRANSCRIPT_DIR, so overlay state never accumulates
across tests of the module-scoped server.

Run:  python -m pytest tests/e2e/ -q
(One-time:  python -m playwright install chromium)
"""

import json
import os
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from app import chain as chain_mod
from app import model_discovery
from tests.e2e.test_ui import (
    StubChain,
    _free_port,
    _lan_ip,
    _wait_ready,
)

# Two providers with differing effective model counts: the default one
# (alpha, keyless local backend) with two models, and a second one (beta)
# that carries an apiKey.
PROVIDER_CONFIG = {
    "provider": {
        "alpha": {
            "name": "Alpha Local",
            "options": {"baseURL": "http://127.0.0.1:41411/v1"},
            "models": {"model-a1": "Model A1", "model-a2": "Model A2"},
        },
        "beta": {
            "name": "Beta Remote",
            "options": {
                "baseURL": "http://127.0.0.1:41412/v1",
                "apiKey": "sekret-key-123",
            },
            "models": {"model-b1": "Model B1"},
        },
    },
    "default": "alpha",
}


def write_provider_config(path: Path, config=PROVIDER_CONFIG) -> Path:
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


class DiscoveryStub:
    """Recording stand-in for model_discovery._get_provider_models.

    Sits at the HTTP seam (design D6): it returns the backend's parsed
    JSON body, so list_models' real parsing and log emission run.
    """

    def __init__(self):
        self.calls = []
        self.models = ["model-d1", "model-d2"]
        self.failure = None

    def reset(self):
        self.calls = []
        self.models = ["model-d1", "model-d2"]
        self.failure = None

    def set_failure(self, reason, detail):
        self.failure = (reason, detail)

    def __call__(self, url, api_key, timeout):
        self.calls.append({"url": url, "api_key": api_key, "timeout": timeout})
        if self.failure is not None:
            raise model_discovery.ModelDiscoveryError(*self.failure)
        return {
            "object": "list",
            "data": [{"id": m, "object": "model"} for m in self.models],
        }


# --- fixtures -----------------------------------------------------------------


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    from app import main as app_main
    import uvicorn

    stub = StubChain()
    original_chain = chain_mod.default_chain
    chain_mod.default_chain = stub
    discovery_stub = DiscoveryStub()
    original_models = model_discovery._get_provider_models
    model_discovery._get_provider_models = discovery_stub

    config_file = write_provider_config(
        Path(tmp_path_factory.mktemp("provider-config")) / "providers.json"
    )
    transcript_dir = Path(tmp_path_factory.mktemp("transcripts"))
    original_config_env = os.environ.get("PROVIDERS_CONFIG")
    original_transcript_env = os.environ.get("TRANSCRIPT_DIR")
    os.environ["PROVIDERS_CONFIG"] = str(config_file)
    os.environ["TRANSCRIPT_DIR"] = str(transcript_dir)

    port = _free_port()
    lan_ip = _lan_ip()
    config = uvicorn.Config(app_main.app, host="0.0.0.0", port=port,
                            log_level="warning")
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    _wait_ready(port)

    yield {
        "port": port,
        "stub": stub,
        "discovery_stub": discovery_stub,
        "config_file": config_file,
        "transcript_dir": transcript_dir,
        "ip_base": f"http://127.0.0.1:{port}",
        "localhost_base": f"http://localhost:{port}",
    }

    uvicorn_server.should_exit = True
    thread.join(timeout=10)
    chain_mod.default_chain = original_chain
    model_discovery._get_provider_models = original_models
    if original_config_env is None:
        os.environ.pop("PROVIDERS_CONFIG", None)
    else:
        os.environ["PROVIDERS_CONFIG"] = original_config_env
    if original_transcript_env is None:
        os.environ.pop("TRANSCRIPT_DIR", None)
    else:
        os.environ["TRANSCRIPT_DIR"] = original_transcript_env


@pytest.fixture(scope="module")
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(autouse=True)
def _reset_stub(server):
    """Fresh stub state (scenario + call logs) for every test."""
    server["stub"].calls = []
    server["stub"].set_success()
    server["discovery_stub"].reset()
    yield


@pytest.fixture(autouse=True)
def _clean_transcript_dir(server, tmp_path, monkeypatch):
    """A fresh per-test transcript directory: the overlay file never
    accumulates across tests (the server is module-scoped, the directory is
    resolved per request)."""
    fresh = tmp_path / "transcripts"
    fresh.mkdir()
    monkeypatch.setenv("TRANSCRIPT_DIR", str(fresh))
    yield


@pytest.fixture()
def provider_config_file(server):
    """The shared config file; rewrites are restored after the test (the
    app reads the file per request)."""
    original = server["config_file"].read_text(encoding="utf-8")
    yield server["config_file"]
    server["config_file"].write_text(original, encoding="utf-8")


@pytest.fixture()
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


# --- helpers ------------------------------------------------------------------


def _wait_section(page):
    page.wait_for_selector(
        "#mm-provider-list .mm-provider-row", timeout=10_000
    )


def _panel(page, provider_id):
    page.click(
        f"#mm-provider-list .mm-provider-row[data-provider-id='{provider_id}']"
        " .mm-manage-btn"
    )
    panel = page.locator(
        f"#mm-provider-list .mm-panel[data-provider-id='{provider_id}']"
    )
    panel.wait_for(timeout=10_000)
    return panel


def _count_text(page, provider_id):
    return page.locator(
        f"#mm-provider-list .mm-provider-row[data-provider-id='{provider_id}']"
        " .mm-provider-count"
    ).text_content()


def _wait_count(page, provider_id, text):
    page.wait_for_function(
        """(text) =>
           document.querySelector(
             "#mm-provider-list .mm-provider-row[data-provider-id='"""
        + provider_id
        + """'] .mm-provider-count"
           ).textContent === text""",
        arg=text,
        timeout=10_000,
    )


def _model_ids_in_panel(page, provider_id):
    rows = page.locator(
        f"#mm-provider-list .mm-panel[data-provider-id='{provider_id}']"
        " .mm-model-row"
    )
    return [
        rows.nth(i).locator(".mm-model-id").text_content()
        for i in range(rows.count())
    ]


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-029 .. 031: the section ------------------


def test_section_visible_before_transcript(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-029"""
    _wait_section(page)
    # visible with providers configured and no transcript displayed
    assert page.locator("#model-management").is_visible()
    assert page.locator("#result").is_hidden()
    names = page.locator("#mm-provider-list .mm-provider-name")
    assert [
        names.nth(i).text_content() for i in range(names.count())
    ] == ["Alpha Local", "Beta Remote"]


def test_section_lists_providers_and_counts(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-030"""
    _wait_section(page)
    rows = page.locator("#mm-provider-list .mm-provider-row")
    assert rows.count() == 2
    names = [
        rows.nth(i).locator(".mm-provider-name").text_content()
        for i in range(rows.count())
    ]
    counts = [
        rows.nth(i).locator(".mm-provider-count").text_content()
        for i in range(rows.count())
    ]
    assert names == ["Alpha Local", "Beta Remote"]
    assert counts == ["2 models", "1 model"]


def test_section_empty_without_providers(page, server, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-031"""
    # The config is read per request: pointing the variable at a missing
    # file makes the app "not configured" without a restart.
    monkeypatch.setenv(
        "PROVIDERS_CONFIG", str(server["config_file"].parent / "missing.json")
    )
    page.reload()
    page.wait_for_selector("#mm-empty:not([hidden])", timeout=10_000)
    # the empty state is shown and no manage actions are offered
    assert page.locator("#mm-empty").is_visible()
    assert page.locator("#mm-provider-list .mm-provider-row").count() == 0
    assert page.locator("#mm-provider-list .mm-manage-btn").count() == 0


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-032 .. 036: the manage panel --------------


def test_manual_add_from_panel(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-032"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    panel.locator(".mm-add-input").fill("model-ax")
    panel.locator(".mm-add-btn").click()

    # the count increases...
    _wait_count(page, "alpha", "3 models")
    # ...and the model appears in the provider's added list (with Remove)
    ids = _model_ids_in_panel(page, "alpha")
    assert ids == ["model-a1", "model-a2", "model-ax"]
    assert page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-remove-btn"
    ).count() == 1
    # the manual input is cleared after the add
    assert panel.locator(".mm-add-input").input_value() == ""


def test_discovered_model_can_be_added(page, server):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-033"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    panel.locator(".mm-refresh-btn").click()
    discovered = page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-discovered-row"
    )
    discovered.first.wait_for(timeout=10_000)
    assert discovered.count() == 2  # the stub's model-d1 / model-d2

    discovered.filter(has_text="model-d1").locator(
        ".mm-discovered-add"
    ).click()

    _wait_count(page, "alpha", "3 models")
    ids = _model_ids_in_panel(page, "alpha")
    assert "model-d1" in ids
    # the other discovered id's button is still offered for it
    assert page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-discovered-row",
        has_text="model-d2",
    ).locator(".mm-discovered-add:enabled").count() == 1


def test_added_model_can_be_removed(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-034"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    panel.locator(".mm-add-input").fill("model-tmp")
    panel.locator(".mm-add-btn").click()
    _wait_count(page, "alpha", "3 models")

    page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-model-row",
        has_text="model-tmp",
    ).locator(".mm-remove-btn").click()

    _wait_count(page, "alpha", "2 models")
    assert "model-tmp" not in _model_ids_in_panel(page, "alpha")


def test_file_models_not_removable(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-035"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    # the config-file models are listed...
    assert _model_ids_in_panel(page, "alpha") == ["model-a1", "model-a2"]
    # ...without any Remove action
    assert page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-remove-btn"
    ).count() == 0
    assert panel.locator(".mm-model-row").count() == 2


def test_markup_model_ids_shown_as_text(page, provider_config_file):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-036"""
    markup = "<img src=x onerror=window.__pwned=1>"
    config = {
        "provider": {
            "alpha": {
                "name": "Alpha <b>Bold</b>",
                "options": {"baseURL": "http://127.0.0.1:41411/v1"},
                "models": {markup: "Markup Model"},
            }
        },
        "default": "alpha",
    }
    provider_config_file.write_text(json.dumps(config), encoding="utf-8")
    page.reload()
    page.wait_for_selector("#mm-provider-list .mm-provider-row", timeout=10_000)
    _panel(page, "alpha")

    # the markup is displayed as plain text...
    section_text = page.locator("#model-management").text_content()
    assert markup in section_text
    assert "<b>Bold</b>" in section_text
    # ...and is not executed
    assert page.locator("#model-management img").count() == 0
    assert page.locator("#model-management b").count() == 0
    assert page.evaluate("() => window.__pwned === undefined")


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-037 .. 038: picker refresh ----------------


def test_added_model_selected_in_picker(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-037"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    panel.locator(".mm-add-input").fill("model-ax")
    panel.locator(".mm-add-btn").click()

    # the picker offers it and selects it for the session
    page.wait_for_function(
        "() => { var sel = document.querySelector("
        "'#provider-picker option:checked'); "
        "return sel && sel.textContent === 'Alpha Local — model-ax'; }",
        timeout=10_000,
    )
    options = page.locator("#provider-picker option")
    labels = [
        options.nth(i).text_content() for i in range(options.count())
    ]
    assert "Alpha Local — model-ax" in labels


def test_removed_model_leaves_picker(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-038"""
    _wait_section(page)
    panel = _panel(page, "alpha")
    panel.locator(".mm-add-input").fill("model-tmp")
    panel.locator(".mm-add-btn").click()
    page.wait_for_function(
        "() => { var sel = document.querySelector("
        "'#provider-picker option:checked'); "
        "return sel && sel.textContent === 'Alpha Local — model-tmp'; }",
        timeout=10_000,
    )

    page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha'] .mm-model-row",
        has_text="model-tmp",
    ).locator(".mm-remove-btn").click()

    page.wait_for_function(
        "() => !Array.prototype.some.call("
        "document.querySelectorAll('#provider-picker option'), "
        "function (o) { return o.textContent === 'Alpha Local — model-tmp'; })",
        timeout=10_000,
    )


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-039 .. 041: errors -------------------------


def test_discovery_failure_shown(page, server):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-039"""
    server["discovery_stub"].set_failure(
        "unreachable", "ConnectionError"
    )
    _wait_section(page)
    before = _count_text(page, "alpha")
    panel = _panel(page, "alpha")
    panel.locator(".mm-refresh-btn").click()

    # a discovery-specific message...
    page.wait_for_selector("#error-banner:not([hidden])", timeout=10_000)
    message = page.locator("#error-banner").text_content()
    assert "Could not refresh the model list" in message
    # ...not the summarization PROVIDER_ERROR text
    assert "summarization backend failed" not in message
    # the effective model list is unchanged...
    assert _count_text(page, "alpha") == before
    assert "model-d1" not in _model_ids_in_panel(page, "alpha")
    # ...and the section remains usable: a manual add still works
    panel.locator(".mm-add-input").fill("model-after")
    panel.locator(".mm-add-btn").click()
    new_count = str(int(before.split()[0]) + 1) + " models"
    _wait_count(page, "alpha", new_count)
    assert _model_ids_in_panel(page, "alpha")[-1] == "model-after"


def test_invalid_model_error_shown(page):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-040"""
    _wait_section(page)
    before = _count_text(page, "alpha")
    panel = _panel(page, "alpha")
    # over the 200-character id cap
    panel.locator(".mm-add-input").fill("x" * 250)
    panel.locator(".mm-add-btn").click()

    page.wait_for_selector("#error-banner:not([hidden])", timeout=10_000)
    message = page.locator("#error-banner").text_content()
    assert "model id is not valid" in message
    # and no model was added
    assert _count_text(page, "alpha") == before
    assert "x" * 250 not in _model_ids_in_panel(page, "alpha")


def test_write_failure_error_shown(page, tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-041"""
    _wait_section(page)
    # The transcript directory is under a file, so the overlay write
    # deterministically fails.
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    monkeypatch.setenv("TRANSCRIPT_DIR", str(blocker / "sub"))

    panel = _panel(page, "alpha")
    panel.locator(".mm-add-input").fill("model-wf")
    panel.locator(".mm-add-btn").click()

    page.wait_for_selector("#error-banner:not([hidden])", timeout=10_000)
    message = page.locator("#error-banner").text_content()
    assert "Could not save the model overrides file." in message
    # the section remains usable: nothing was added, the panel is intact
    assert _count_text(page, "alpha") == "2 models"
    assert page.locator(
        "#mm-provider-list .mm-panel[data-provider-id='alpha']"
    ).count() == 1
    assert panel.locator(".mm-add-input").is_enabled()
