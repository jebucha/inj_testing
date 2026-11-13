"""Served code-docs site and retired OpenAPI endpoints (T-CODE-DOCS-001 .. 005).

The app serves the committed pre-rendered docs under /docs/ and no longer
exposes FastAPI's built-in interactive API documentation.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

import pytest
from starlette.testclient import TestClient

from app.main import DOCS_DIR, create_app

# <link>/<script>/<img>/<iframe> hrefs load a resource; a plain <a> hyperlink
# is content, not a resource, so it is not part of the "external resources"
# surface (T-CODE-DOCS-003).
RESOURCE_HREF_TAGS = {"link", "script", "img", "iframe"}


class _ResourceRefs(HTMLParser):
    """Every src attribute and every resource-tag href in a document."""

    def __init__(self):
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value is None:
                continue
            if name == "src" or (name == "href" and tag in RESOURCE_HREF_TAGS):
                self.refs.append(value)


class _Hyperlinks(HTMLParser):
    """Every <a href> on a document (page links of the docs navigation)."""

    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value is not None:
                self.hrefs.append(value)
                break


@pytest.fixture
def client():
    client = TestClient(create_app())
    with client:
        yield client


def test_docs_landing_served(client):
    """T-CODE-DOCS-001"""
    response = client.get("/docs/")

    assert response.status_code == 200
    # the docs' own navigation (the shared shell's sidebar) is in the body
    assert '<nav class="sidebar">' in response.text
    assert "inj-testing docs" in response.text


def test_linked_doc_pages_served(client):
    """T-CODE-DOCS-002"""
    landing = client.get("/docs/")
    assert landing.status_code == 200
    links = _Hyperlinks()
    links.feed(landing.text)
    assert links.hrefs, "the landing page must link to docs pages"

    subdirectory_pages = 0
    for href in sorted(set(links.hrefs)):
        # skip in-page anchors and anything leaving the site: page links
        # relative to the docs site are what must be served
        if not href or href.startswith(("#", "mailto:", "http://", "https://")):
            continue
        url = urljoin("/docs/", href)
        assert url.startswith("/docs/"), f"link escapes the docs site: {href}"
        if url.count("/") >= 3:  # /docs/<subdirectory>/<page>
            subdirectory_pages += 1
        response = client.get(url)
        assert response.status_code == 200, f"linked page not served: {url}"

    assert subdirectory_pages >= 1, (
        "expected at least one linked page in a docs subdirectory"
    )


def test_docs_pages_have_no_external_resources(client):
    """T-CODE-DOCS-003"""
    html_files = sorted(DOCS_DIR.rglob("*.html"))
    assert html_files, "the committed docs site must exist"
    for path in html_files:
        url = "/docs/" + path.relative_to(DOCS_DIR).as_posix()
        response = client.get(url)
        assert response.status_code == 200, f"docs page not served: {url}"
        refs_parser = _ResourceRefs()
        refs_parser.feed(response.text)
        external = [r for r in refs_parser.refs if r.startswith(("http://", "https://"))]
        assert not external, f"{url} references external resources: {external}"


def test_docs_path_serves_docs_site(client):
    """T-CODE-DOCS-004"""
    response = client.get("/docs", follow_redirects=False)

    # the client lands on the docs site, not the (retired) Swagger UI:
    # a redirect to /docs/ whose target serves the docs landing page
    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["location"] == "/docs/"

    landing = client.get("/docs/")
    assert landing.status_code == 200
    assert '<nav class="sidebar">' in landing.text
    assert "swagger" not in landing.text.lower()


def test_openapi_endpoints_removed(client):
    """T-CODE-DOCS-005"""
    assert client.get("/openapi.json", follow_redirects=False).status_code == 404
    assert client.get("/redoc", follow_redirects=False).status_code == 404
