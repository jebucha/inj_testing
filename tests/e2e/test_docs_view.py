"""E2E tests for the Docs view and application view navigation
(T-WEB-INTERFACE-019 .. 026).

A real uvicorn instance of the app runs in-process (thread) with the upstream
fetch chain stubbed for determinism — no real YouTube traffic. The running
server serves the real `docs/` directory from the repo root, so the Docs view's
iframe loads the same site the app serves at /docs/.

Run:  python -m pytest tests/e2e/ -q
(One-time:  python -m playwright install chromium)
"""

import asyncio
import socket
import threading
import time

import pytest
from playwright.sync_api import sync_playwright

from app import chain as chain_mod
from app.chain import FetchResult
from app.errors import (
    BusyError,
    InvalidUrlError,
    NoCaptionsError,
    UpstreamFailureError,
    VideoUnavailableError,
)

DEFAULT_PAYLOAD = {
    "video_id": "dQw4w9WgXcQ",
    "title": "Test Video Title",
    "text": "This is the transcript of the test video.\nSecond line of the transcript.",
    "language": "en",
    "source": "primary",
}

ERROR_CLASSES = {
    "INVALID_URL": InvalidUrlError,
    "VIDEO_UNAVAILABLE": VideoUnavailableError,
    "NO_CAPTIONS": NoCaptionsError,
    "UPSTREAM_FAILURE": UpstreamFailureError,
    "BUSY": BusyError,
}


class StubChain:
    """Drop-in replacement for chain_mod.default_chain.

    Mirrors the real chain's single-flight semantics (asyncio.Semaphore(1) +
    immediate BusyError) so the BUSY path is exercised realistically.
    """

    def __init__(self):
        self.scenario = {"type": "success", "payload": DEFAULT_PAYLOAD, "delay": 0.0}
        self.calls = []
        self._semaphore = asyncio.Semaphore(1)

    def set_success(self, payload=None, delay=0.0):
        self.scenario = {
            "type": "success",
            "payload": payload or DEFAULT_PAYLOAD,
            "delay": delay,
        }

    def set_error(self, code, message=None):
        self.scenario = {"type": "error", "code": code, "message": message}

    async def run(self, url):
        from app.urls import parse_video_ref

        self.calls.append(url)
        video_id = parse_video_ref(url)  # real parsing: invalid -> 400
        if self._semaphore.locked():
            raise BusyError()
        await self._semaphore.acquire()
        try:
            scenario = self.scenario
            if scenario.get("delay"):
                await asyncio.sleep(scenario["delay"])
            if scenario["type"] == "error":
                raise ERROR_CLASSES[scenario["code"]](scenario.get("message"))
            payload = scenario.get("payload") or DEFAULT_PAYLOAD
            return FetchResult(
                text=payload["text"],
                video_id=payload.get("video_id", video_id),
                title=payload["title"],
                language=payload["language"],
                source=payload.get("source", "primary"),
            )
        finally:
            self._semaphore.release()


# --- fixtures -----------------------------------------------------------------
# Self-contained harness: this module (like every existing e2e module) defines
# its own server/playwright/browser/page fixtures rather than sharing a
# conftest.py.


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _lan_ip() -> str:
    """Best-effort LAN IP (non-loopback, non-secure in the browser)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # UDP connect: no packets sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _wait_ready(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    pytest.fail(f"local server did not become ready on port {port}")


@pytest.fixture(scope="module")
def server():
    from app import main as app_main
    import uvicorn

    stub = StubChain()
    original_chain = chain_mod.default_chain
    chain_mod.default_chain = stub

    port = _free_port()
    lan_ip = _lan_ip()
    config = uvicorn.Config(app_main.app, host="0.0.0.0", port=port, log_level="warning")
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    _wait_ready(port)

    yield {
        "port": port,
        "stub": stub,
        "lan_ip": lan_ip,
        "ip_base": f"http://127.0.0.1:{port}",
        "localhost_base": f"http://localhost:{port}",
    }

    uvicorn_server.should_exit = True
    thread.join(timeout=10)
    chain_mod.default_chain = original_chain


@pytest.fixture(scope="module")
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(autouse=True)
def _reset_stub(server):
    """Fresh stub state (scenario + call log) for every test."""
    server["stub"].calls = []
    server["stub"].set_success()
    yield


@pytest.fixture()
def browser(playwright):
    b = playwright.chromium.launch()
    yield b
    b.close()


@pytest.fixture()
def page(browser, server):
    """Page served over http://localhost at the common 1024x640 viewport."""
    context = browser.new_context(viewport={"width": 1024, "height": 640})
    pg = context.new_page()
    pg.goto(server["localhost_base"] + "/")
    yield pg
    context.close()


def _fetch(page, url):
    page.fill("#url-input", url)
    page.click("#fetch-btn")


def _wait_result(page):
    page.wait_for_selector("#result:not([hidden])", timeout=10_000)


def _assert_no_horizontal_overflow(page):
    """Document-wide sweep: no element in the application document extends
    past the viewport width (horizontal overflow) or into the left margin."""
    overflow = page.evaluate(
        """() => {
             const vw = window.innerWidth;
             const bad = [];
             for (const el of document.querySelectorAll('*')) {
                 const box = el.getBoundingClientRect();
                 if (box.right > vw + 0.5 || box.left < -0.5) {
                     bad.push(
                         (el.id || el.className || el.tagName)
                         + ' left=' + box.left.toFixed(1)
                         + ' right=' + box.right.toFixed(1)
                     );
                 }
             }
             return bad;
         }"""
    )
    assert not overflow, (
        f"elements overflow the viewport horizontally (width "
        f"{page.evaluate('window.innerWidth')}): {overflow[:5]}"
    )


# --- T-WEB-INTERFACE-019 .. 021: view navigation --------------------------------


def test_transcripts_default_view(page, server):
    """T-WEB-INTERFACE-019"""
    # the "Transcripts" item is marked active (aria-current + CSS active class)
    transcripts_nav = page.locator("#nav-transcripts")
    assert transcripts_nav.get_attribute("aria-current") == "page"
    assert "active" in (transcripts_nav.get_attribute("class") or "")
    # the existing interface is visible...
    assert page.locator("#url-input").is_visible()
    assert page.locator("#fetch-btn").is_visible()
    # ...and the Docs view is hidden
    assert page.locator("#view-docs").is_hidden()
    assert page.locator("#view-transcripts").is_visible()


def test_switch_to_docs_view(page, server):
    """T-WEB-INTERFACE-020"""
    page.click("#nav-docs")

    assert page.locator("#view-docs").is_visible()
    # the Transcripts content is hidden
    assert page.locator("#view-transcripts").is_hidden()
    assert not page.locator("#url-input").is_visible()
    assert not page.locator("#fetch-btn").is_visible()
    # and the "Docs" item is marked active, "Transcripts" no longer is
    assert page.locator("#nav-docs").get_attribute("aria-current") == "page"
    assert "active" in (page.locator("#nav-docs").get_attribute("class") or "")
    assert page.locator("#nav-transcripts").get_attribute("aria-current") is None
    assert "active" not in (page.locator("#nav-transcripts").get_attribute("class") or "")


def test_return_to_transcripts_view(page, server):
    """T-WEB-INTERFACE-021"""
    server["stub"].set_success()
    _fetch(page, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    _wait_result(page)
    assert DEFAULT_PAYLOAD["text"] in page.locator("#transcript-panel").inner_text()

    # round trip through the Docs view
    page.click("#nav-docs")
    assert page.locator("#view-docs").is_visible()
    page.click("#nav-transcripts")

    assert page.locator("#view-transcripts").is_visible()
    assert page.locator("#view-docs").is_hidden()
    assert page.locator("#nav-transcripts").get_attribute("aria-current") == "page"
    # the fetched transcript is still displayed in the result section
    _wait_result(page)
    assert page.locator("#video-title").inner_text() == DEFAULT_PAYLOAD["title"]
    assert DEFAULT_PAYLOAD["text"] in page.locator("#transcript-panel").inner_text()
    assert not page.locator("#copy-btn").is_disabled()


# --- T-WEB-INTERFACE-022 .. 023: Docs view embedding ----------------------------


def test_docs_rendered_in_iframe(page, server):
    """T-WEB-INTERFACE-022"""
    page.click("#nav-docs")
    assert page.locator("#view-docs").is_visible()

    # the Docs view holds the iframe pointing at the docs landing path
    frame = page.locator("#docs-frame")
    assert frame.count() == 1
    assert frame.get_attribute("src") == "/docs/"

    # the iframe is sized to fill the main pane (the toolbar owns the top
    # strip; the iframe takes the pane's full width and bottom)
    main_box = page.locator(".app-main").bounding_box()
    frame_box = frame.bounding_box()
    assert frame_box is not None
    assert frame_box["width"] == pytest.approx(main_box["width"], abs=2)
    assert frame_box["y"] + frame_box["height"] == pytest.approx(
        main_box["y"] + main_box["height"], abs=2
    )
    assert frame_box["x"] == pytest.approx(main_box["x"], abs=2)

    # the docs' own sidebar navigation renders inside the iframe's document
    docs_nav = page.frame_locator("#docs-frame").locator("nav.sidebar")
    docs_nav.wait_for(state="visible", timeout=10_000)
    assert docs_nav.count() == 1


def test_docs_open_in_new_window(page, server):
    """T-WEB-INTERFACE-023"""
    page.click("#nav-docs")
    assert page.locator("#view-docs").is_visible()

    with page.expect_popup() as popup_info:
        page.click("#docs-open-new")
    popup = popup_info.value

    try:
        assert popup.url == server["localhost_base"] + "/docs/"
    finally:
        popup.close()


# --- T-WEB-INTERFACE-024: narrow viewports ---------------------------------------


def test_narrow_viewport_nav_collapses(browser, server):
    """T-WEB-INTERFACE-024"""
    context = browser.new_context(viewport={"width": 420, "height": 640})
    narrow_page = context.new_page()
    narrow_page.goto(server["localhost_base"] + "/")
    try:
        # the two nav items form a horizontal row...
        transcripts = narrow_page.locator("#nav-transcripts").bounding_box()
        docs = narrow_page.locator("#nav-docs").bounding_box()
        input_box = narrow_page.locator("#url-input").bounding_box()
        assert transcripts is not None and docs is not None
        assert transcripts["y"] == pytest.approx(docs["y"], abs=1), (
            "nav items must sit in one horizontal row"
        )
        assert docs["x"] > transcripts["x"], (
            "the Docs item must be beside, not below, the Transcripts item"
        )
        # ...above the view content
        nav_bottom = transcripts["y"] + transcripts["height"]
        assert input_box["y"] >= nav_bottom - 0.5, (
            "the nav row must sit above the view content"
        )

        # no element overflows the viewport horizontally (document-wide sweep)
        _assert_no_horizontal_overflow(narrow_page)

        # the Docs view must not overflow either
        narrow_page.click("#nav-docs")
        narrow_page.frame_locator("#docs-frame").locator("nav.sidebar").wait_for(
            state="visible", timeout=10_000
        )
        _assert_no_horizontal_overflow(narrow_page)
    finally:
        context.close()


# --- T-WEB-INTERFACE-025 .. 026: no persistence, no docs in the app DOM ----------


def test_view_selection_not_persisted(page, server):
    """T-WEB-INTERFACE-025"""
    page.click("#nav-docs")
    assert page.locator("#view-docs").is_visible()

    page.reload()

    # the Transcripts view is active again on load; the Docs view is hidden
    assert page.locator("#view-transcripts").is_visible()
    assert page.locator("#view-docs").is_hidden()
    assert page.locator("#nav-transcripts").get_attribute("aria-current") == "page"
    assert page.locator("#nav-docs").get_attribute("aria-current") is None


def test_docs_not_inserted_into_app_dom(page, server):
    """T-WEB-INTERFACE-026"""
    page.click("#nav-docs")
    assert page.locator("#view-docs").is_visible()

    # the Docs view section holds only its toolbar and the iframe
    children = page.locator("#view-docs > *")
    assert children.count() == 2
    toolbar = children.filter(has=page.locator("#docs-open-new"))
    assert toolbar.count() == 1
    # the toolbar's only content is the open-in-new-window link
    link = page.locator("#docs-open-new")
    assert link.get_attribute("href") == "/docs/"
    assert link.get_attribute("target") == "_blank"

    # the iframe loads via src — no srcdoc, no injected docs HTML
    frame = page.locator("#docs-frame")
    assert frame.get_attribute("src") == "/docs/"
    assert frame.get_attribute("srcdoc") is None

    # no documentation markup anywhere in the application document: the
    # docs' own shell (sidebar nav + docs heading) exists only in the
    # iframe's document, and the app document is still the app's page
    assert page.locator("nav.sidebar").count() == 0
    assert page.locator("#view-docs h1").count() == 0
    assert page.title() == "inj-testing"
