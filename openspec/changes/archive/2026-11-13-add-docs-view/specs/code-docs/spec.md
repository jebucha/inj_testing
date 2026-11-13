# Spec Delta

## Purpose

The application serves the repository's committed, pre-rendered code documentation as a static site under `/docs/`, with the interactive OpenAPI UI that previously occupied that path retired.

## ADDED Requirements

### Requirement: Docs site availability
The application SHALL serve the pre-rendered code documentation committed under the repository's `docs/` directory at the `/docs/` path over plain HTTP, with no build step at serve time. The docs landing page SHALL be served at `/docs/`, and every page linked from the docs' own navigation SHALL be served at its linked path.

#### Scenario: Landing page served
- **WHEN** the client requests `GET /docs/`
- **THEN** the response is 200 and the body is the docs landing page's HTML, containing the docs' own navigation
- **Test Requirement**
  - **ID:** T-CODE-DOCS-001
  - **File:** tests/test_docs_serving.py::test_docs_landing_served
  - **Command:** python -m pytest tests/test_docs_serving.py::test_docs_landing_served -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Linked doc pages served
- **WHEN** the client requests the path of a page linked from the docs landing page, including a page in a subdirectory of the docs site
- **THEN** the response is 200 and the body is that page's HTML
- **Test Requirement**
  - **ID:** T-CODE-DOCS-002
  - **File:** tests/test_docs_serving.py::test_linked_doc_pages_served
  - **Command:** python -m pytest tests/test_docs_serving.py::test_linked_doc_pages_served -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: Docs pages are self-contained
- **WHEN** a docs page is served
- **THEN** the page references no external (http/https) resources — only references relative to the docs site
- **Test Requirement**
  - **ID:** T-CODE-DOCS-003
  - **File:** tests/test_docs_serving.py::test_docs_pages_have_no_external_resources
  - **Command:** python -m pytest tests/test_docs_serving.py::test_docs_pages_have_no_external_resources -q
  - **Pass:** exit code 0, no skipped tests

### Requirement: Interactive API documentation retired
The application SHALL NOT expose FastAPI's built-in interactive API documentation: the Swagger UI route at `/docs`, the `/redoc` route, and the OpenAPI schema at `/openapi.json` SHALL NOT be served.

#### Scenario: /docs is the docs site, not Swagger
- **WHEN** the client requests `GET /docs` without a trailing slash
- **THEN** the Swagger UI is not served and the client lands on the docs site (a redirect to `/docs/` whose target serves the docs landing page)
- **Test Requirement**
  - **ID:** T-CODE-DOCS-004
  - **File:** tests/test_docs_serving.py::test_docs_path_serves_docs_site
  - **Command:** python -m pytest tests/test_docs_serving.py::test_docs_path_serves_docs_site -q
  - **Pass:** exit code 0, no skipped tests

#### Scenario: OpenAPI endpoints removed
- **WHEN** the client requests `GET /openapi.json` or `GET /redoc`
- **THEN** the response is 404
- **Test Requirement**
  - **ID:** T-CODE-DOCS-005
  - **File:** tests/test_docs_serving.py::test_openapi_endpoints_removed
  - **Command:** python -m pytest tests/test_docs_serving.py::test_openapi_endpoints_removed -q
  - **Pass:** exit code 0, no skipped tests
