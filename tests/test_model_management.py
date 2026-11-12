"""T-SUMMARIZATION-MODEL-MANAGEMENT-008 .. 022, 042, 044 (+ discovery tests
from task 3.3).

The model-management endpoints (POST/DELETE /api/providers/{id}/models)
and their validation, persistence, logging, and fetch-chain independence,
unit-tested with TestClient against the real app, a tmp provider config,
a tmp transcript directory, and a captured log stream. The chat-completions
dispatch and the discovery HTTP seam are stubbed so no backend traffic
happens.
"""

import io
import json

import pytest
from starlette.testclient import TestClient

from app import chain as chain_mod
from app import log as applog
from app import model_discovery
from app import summarize as summarize_mod
from app.chain import FetchChain
from app.main import create_app

# The real HTTP seam, captured before any fixture stubs the module attribute:
# test 024 restores it so its header construction runs with only
# requests.get faked.
REAL_GET_PROVIDER_MODELS = model_discovery._get_provider_models

# --- shared fixtures -----------------------------------------------------------


class RecordingDispatch:
    """Recording stand-in for summarize_mod._call_chat_completions."""

    def __init__(self):
        self.calls = []
        self.summary = "The summary."
        self.failure = None

    def __call__(self, base_url, model, messages, api_key, timeout):
        self.calls.append({
            "base_url": base_url, "model": model, "messages": messages,
            "api_key": api_key, "timeout": timeout,
        })
        if self.failure is not None:
            raise summarize_mod.ProviderCallError(*self.failure)
        return self.summary


class DiscoveryStub:
    """Recording stand-in for model_discovery._get_provider_models.

    Sits at the HTTP seam (design D6): it returns the backend's parsed
    JSON body, so list_models' real parsing and log emission run.
    """

    def __init__(self):
        self.calls = []
        self.models = ["model-d1", "model-d2"]
        self.failure = None  # None | (reason, detail)

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
            "data": [{"id": model, "object": "model"} for model in self.models],
        }


PROVIDER_CONFIG = {
    "provider": {
        "alpha": {
            "name": "Alpha Local",
            "options": {"baseURL": "http://127.0.0.1:41411/v1"},
            "models": {"model-a1": "Model A1", "model-a2": "Model A2"},
        },
        "beta": {
            "name": "Beta Remote",
            "options": {"baseURL": "http://127.0.0.1:41412/v1",
                        "apiKey": "sk-endpoint-test-key"},
            "models": {"model-b1": "Model B1"},
        },
    },
    "default": "alpha",
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient with a tmp provider config, a tmp transcript dir, a
    captured log stream, and both backend seams stubbed."""
    config_file = tmp_path / "providers.json"
    config_file.write_text(json.dumps(PROVIDER_CONFIG), encoding="utf-8")
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    monkeypatch.setenv("PROVIDERS_CONFIG", str(config_file))
    monkeypatch.setenv("TRANSCRIPT_DIR", str(transcript_dir))
    dispatch = RecordingDispatch()
    monkeypatch.setattr(summarize_mod, "_call_chat_completions", dispatch)
    discovery = DiscoveryStub()
    monkeypatch.setattr(model_discovery, "_get_provider_models", discovery)
    buf = io.StringIO()
    applog.setup_logging(stream=buf)
    client = TestClient(create_app())
    with client:
        yield {
            "client": client,
            "config_file": config_file,
            "transcript_dir": transcript_dir,
            "dispatch": dispatch,
            "discovery": discovery,
            "log": buf,
        }


def _overrides_file(api):
    return api["transcript_dir"] / "provider_overrides.json"


def _entries(buf, event=None) -> list[dict]:
    lines = [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
    return lines if event is None else [e for e in lines if e.get("event") == event]


def _add(client, provider_id, model):
    return client.post(
        f"/api/providers/{provider_id}/models", json={"model": model}
    )


def _remove(client, provider_id, model):
    # httpx's Client.delete() takes no body arguments, so the DELETE with a
    # JSON body goes through the generic request() (design D4: the model id
    # travels in the body, not the path).
    return client.request(
        "DELETE", f"/api/providers/{provider_id}/models", json={"model": model}
    )


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-008 .. 012: add endpoint -----------------


def test_add_model_persists_and_lists(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-008"""
    response = _add(api["client"], "alpha", "model-ax")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "alpha"
    assert body["model"] == "model-ax"
    assert body["models"] == ["model-a1", "model-a2", "model-ax"]
    # the overrides file contains the id...
    stored = json.loads(_overrides_file(api).read_text(encoding="utf-8"))
    assert stored == {"alpha": ["model-ax"]}
    # ...and a subsequent provider listing includes it after the file models
    listing = api["client"].get("/api/providers").json()
    alpha = next(p for p in listing["providers"] if p["id"] == "alpha")
    assert alpha["models"] == ["model-a1", "model-a2", "model-ax"]
    assert alpha["addedModels"] == ["model-ax"]
    # the add did not call any summarization backend
    assert api["dispatch"].calls == []


def test_add_existing_model_is_idempotent(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-009"""
    # a file-provided id is already in the effective list...
    response = _add(api["client"], "alpha", "model-a1")

    assert response.status_code == 200
    assert response.json()["models"] == ["model-a1", "model-a2"]
    # no overlay write happened for it
    assert not _overrides_file(api).exists()

    # and re-adding an overlay id keeps the effective list duplicate-free
    assert _add(api["client"], "alpha", "model-ax").status_code == 200
    response = _add(api["client"], "alpha", "model-ax")
    assert response.status_code == 200
    assert response.json()["models"] == ["model-a1", "model-a2", "model-ax"]
    stored = json.loads(_overrides_file(api).read_text(encoding="utf-8"))
    assert stored == {"alpha": ["model-ax"]}


def test_add_unknown_provider_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-010"""
    response = _add(api["client"], "ghost", "model-ax")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PROVIDER"
    assert not _overrides_file(api).exists()
    assert api["dispatch"].calls == []


def test_add_write_failure_no_partial_state(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-011"""
    # The transcript directory is under a file, so the overlay write
    # deterministically fails.
    blocker = api["transcript_dir"].parent / "blocker"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    monkeypatch.setenv("TRANSCRIPT_DIR", str(blocker / "sub"))

    response = _add(api["client"], "alpha", "model-ax")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "WRITE_FAILED"
    # no partial state: no overrides file and no stranded temp file
    assert not (blocker / "sub").exists()
    assert not (blocker / "provider_overrides.json.tmp").exists()
    # the effective model list is unchanged
    monkeypatch.setenv("TRANSCRIPT_DIR", str(api["transcript_dir"]))
    listing = api["client"].get("/api/providers").json()
    alpha = next(p for p in listing["providers"] if p["id"] == "alpha")
    assert alpha["models"] == ["model-a1", "model-a2"]
    assert alpha["addedModels"] == []


def test_add_during_in_flight_fetch_succeeds(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-012"""
    import threading

    # A real chain whose fetcher blocks until released: it holds the
    # single-flight semaphore for the whole in-flight window.
    fetch_started = threading.Event()
    release_fetch = threading.Event()
    fetch_calls = []

    def blocking_fetch(video_id, requested_language):
        fetch_calls.append(video_id)
        fetch_started.set()
        release_fetch.wait(timeout=10)
        return ("fetched text", "en", "A Title")

    chain = FetchChain(primary=blocking_fetch, fallback=blocking_fetch)
    monkeypatch.setattr(chain_mod, "default_chain", chain)

    holder = {}

    def fetch_thread():
        holder["response"] = api["client"].post(
            "/api/transcript",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

    thread = threading.Thread(target=fetch_thread)
    thread.start()
    try:
        assert fetch_started.wait(timeout=10)  # the fetch is in flight
        response = _add(api["client"], "alpha", "model-ax")
        assert response.status_code == 200
        assert response.json()["models"] == ["model-a1", "model-a2", "model-ax"]
        # the add did not invoke the fetch chain
        assert fetch_calls == ["dQw4w9WgXcQ"]
    finally:
        release_fetch.set()
        thread.join(timeout=15)


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-013 .. 017: id validation and bounds -----


def test_add_blank_model_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-013"""
    for blank in ("", "   ", "\t\n"):
        response = _add(api["client"], "alpha", blank)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_MODEL"
    assert not _overrides_file(api).exists()


def test_add_overlong_model_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-014"""
    response = _add(api["client"], "alpha", "x" * 201)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MODEL"
    assert not _overrides_file(api).exists()

    # exactly at the cap is accepted
    response = _add(api["client"], "alpha", "x" * 200)
    assert response.status_code == 200


def test_add_control_char_model_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-015"""
    for model in ("bad\x00id", "bad\x1bid", "bad\x7fid", "line\nbreak"):
        response = _add(api["client"], "alpha", model)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_MODEL"
    assert not _overrides_file(api).exists()


def test_add_per_provider_cap_enforced(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-016"""
    for i in range(50):
        response = _add(api["client"], "alpha", f"bulk-{i}")
        assert response.status_code == 200

    response = _add(api["client"], "alpha", "bulk-50")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MODEL"

    # the cap is per provider: a different provider is unaffected
    response = _add(api["client"], "beta", "model-bx")
    assert response.status_code == 200
    stored = json.loads(_overrides_file(api).read_text(encoding="utf-8"))
    assert len(stored["alpha"]) == 50
    assert stored["beta"] == ["model-bx"]


def test_add_invalid_body_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-017"""
    client = api["client"]
    # a non-object body
    response = client.post(
        "/api/providers/alpha/models", content=json.dumps(["model"]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BODY"

    # a body without the model field
    response = client.post("/api/providers/alpha/models", json={"other": 1})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BODY"

    # unparseable JSON
    response = client.post(
        "/api/providers/alpha/models", content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BODY"

    assert not _overrides_file(api).exists()


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-018 .. 022: remove endpoint --------------


def test_remove_added_model(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-018"""
    assert _add(api["client"], "alpha", "model-ax").status_code == 200

    response = _remove(api["client"], "alpha", "model-ax")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "alpha"
    assert body["model"] == "model-ax"
    assert body["models"] == ["model-a1", "model-a2"]
    # the overrides file no longer contains it...
    assert not json.loads(_overrides_file(api).read_text(encoding="utf-8"))

    # ...and the provider listing no longer offers it
    listing = api["client"].get("/api/providers").json()
    alpha = next(p for p in listing["providers"] if p["id"] == "alpha")
    assert alpha["models"] == ["model-a1", "model-a2"]
    assert alpha["addedModels"] == []
    # the remove did not call any summarization backend
    assert api["dispatch"].calls == []


def test_remove_file_model_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-019"""
    response = _remove(api["client"], "alpha", "model-a1")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MODEL_NOT_REMOVABLE"
    # the model remains in the effective list, the overlay is untouched
    listing = api["client"].get("/api/providers").json()
    alpha = next(p for p in listing["providers"] if p["id"] == "alpha")
    assert "model-a1" in alpha["models"]
    assert not _overrides_file(api).exists()


def test_remove_absent_model_404(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-020"""
    response = _remove(api["client"], "alpha", "model-zz")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert not _overrides_file(api).exists()


def test_remove_unknown_provider_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-021"""
    response = _remove(api["client"], "ghost", "model-ax")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PROVIDER"
    assert not _overrides_file(api).exists()


def test_remove_write_failure_no_partial_state(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-022"""
    assert _add(api["client"], "alpha", "model-ax").status_code == 200

    # The temp-file slot is occupied by a directory, so the atomic write
    # deterministically fails while the overlay file itself stays readable:
    # the remove request is valid (the model is still in the overlay), only
    # the save is blocked.
    _overrides_file(api).with_name("provider_overrides.json.tmp").mkdir()

    response = _remove(api["client"], "alpha", "model-ax")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "WRITE_FAILED"
    # the model remains listed (the old overlay file is intact)
    listing = api["client"].get("/api/providers").json()
    alpha = next(p for p in listing["providers"] if p["id"] == "alpha")
    assert "model-ax" in alpha["models"]


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-023 .. 028: discovery --------------------


def test_discover_models_returns_ids(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-023"""
    # The body carries duplicates, a non-dict entry, a non-string id, an
    # empty id, and a missing id: only clean string ids survive, deduped
    # preserving order.
    def fake_get(url, api_key, timeout):
        return {
            "object": "list",
            "data": [
                {"id": "m1", "object": "model"},
                {"id": "m2", "object": "model"},
                {"id": "m1", "object": "model"},
                "not-a-dict",
                {"id": 42, "object": "model"},
                {"id": "", "object": "model"},
                {"object": "model"},
            ],
        }
    monkeypatch.setattr(model_discovery, "_get_provider_models", fake_get)

    response = api["client"].get("/api/providers/alpha/available-models")

    assert response.status_code == 200
    assert response.json() == {"models": ["m1", "m2"]}


def test_discover_auth_header_only_when_key_present(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-024"""
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"object": "list", "data": [{"id": "m1"}]}

    seen = []

    def fake_get(url, headers=None, timeout=None):
        seen.append({"url": url, "headers": dict(headers or {})})
        return FakeResponse()

    # Stub the HTTP layer itself so the real _get_provider_models seam runs:
    # restore the seam the fixture stubbed, then fake only requests.get.
    monkeypatch.setattr(
        model_discovery, "_get_provider_models", REAL_GET_PROVIDER_MODELS
    )
    monkeypatch.setattr(model_discovery.requests, "get", fake_get)

    # the provider with an apiKey: the request carries the bearer token...
    response = api["client"].get("/api/providers/beta/available-models")
    assert response.status_code == 200
    assert seen[0]["url"] == "http://127.0.0.1:41412/v1/models"
    assert seen[0]["headers"].get("Authorization") == \
        "Bearer sk-endpoint-test-key"
    # ...the keyless provider: no Authorization header at all
    response = api["client"].get("/api/providers/alpha/available-models")
    assert response.status_code == 200
    assert seen[1]["url"] == "http://127.0.0.1:41411/v1/models"
    assert "Authorization" not in seen[1]["headers"]


def test_discover_unknown_provider_rejected(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-025"""
    response = api["client"].get("/api/providers/ghost/available-models")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PROVIDER"
    # no backend request was made
    assert api["discovery"].calls == []


def test_discover_backend_failure_returns_502(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-026"""
    # transport-level failure through the seam stub...
    api["discovery"].set_failure("unreachable", "ConnectionError")
    response = api["client"].get("/api/providers/alpha/available-models")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"

    # ...and a 2xx with a malformed body (no data list)
    def bad_body(url, api_key, timeout):
        return {"object": "list"}
    monkeypatch.setattr(model_discovery, "_get_provider_models", bad_body)
    response = api["client"].get("/api/providers/alpha/available-models")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_ERROR"

    failed = _entries(api["log"], "provider_models_refresh_failed")
    assert [e["reason"] for e in failed] == [
        "unreachable", "malformed_response"
    ]


def test_discover_response_omits_secrets(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-027"""
    response = api["client"].get("/api/providers/beta/available-models")

    assert response.status_code == 200
    assert response.json() == {"models": ["model-d1", "model-d2"]}
    # neither the API key nor the base URL appears in the body
    assert "sk-endpoint-test-key" not in response.text
    assert "127.0.0.1:41412" not in response.text


def test_discover_during_in_flight_fetch_succeeds(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-028"""
    import threading

    # A real chain whose fetcher blocks until released: it holds the
    # single-flight semaphore for the whole in-flight window.
    fetch_started = threading.Event()
    release_fetch = threading.Event()
    fetch_calls = []

    def blocking_fetch(video_id, requested_language):
        fetch_calls.append(video_id)
        fetch_started.set()
        release_fetch.wait(timeout=10)
        return ("fetched text", "en", "A Title")

    chain = FetchChain(primary=blocking_fetch, fallback=blocking_fetch)
    monkeypatch.setattr(chain_mod, "default_chain", chain)

    holder = {}

    def fetch_thread():
        holder["response"] = api["client"].post(
            "/api/transcript",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

    thread = threading.Thread(target=fetch_thread)
    thread.start()
    try:
        assert fetch_started.wait(timeout=10)  # the fetch is in flight
        response = api["client"].get(
            "/api/providers/alpha/available-models"
        )
        assert response.status_code == 200
        assert response.json() == {"models": ["model-d1", "model-d2"]}
        # discovery did not invoke the fetch chain
        assert fetch_calls == ["dQw4w9WgXcQ"]
    finally:
        release_fetch.set()
        thread.join(timeout=15)


# --- T-SUMMARIZATION-MODEL-MANAGEMENT-042 .. 045: observability ----------------


def test_add_and_remove_are_logged(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-042"""
    assert _add(api["client"], "alpha", "model-ax").status_code == 200
    assert _remove(api["client"], "alpha", "model-ax").status_code == 200

    added = _entries(api["log"], "provider_model_added")
    removed = _entries(api["log"], "provider_model_removed")
    assert len(added) == 1
    assert added[0]["level"] == "info"
    assert added[0]["provider"] == "alpha"
    assert added[0]["model"] == "model-ax"
    assert len(removed) == 1
    assert removed[0]["level"] == "info"
    assert removed[0]["provider"] == "alpha"
    assert removed[0]["model"] == "model-ax"


def test_discovery_failure_logged(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-043"""
    api["discovery"].set_failure("http_error", "backend returned HTTP 500")

    response = api["client"].get("/api/providers/beta/available-models")
    assert response.status_code == 502

    failed = _entries(api["log"], "provider_models_refresh_failed")
    assert len(failed) == 1
    event = failed[0]
    assert event["level"] == "error"
    assert event["provider"] == "beta"
    assert event["reason"] == "http_error"
    assert event["detail"] == "backend returned HTTP 500"


def test_overlay_failures_logged(api, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-044"""
    marker = "SECRET_OVERRIDES_CONTENT_MARKER_99"

    # malformed overrides file: a load failure with path/reason/detail,
    # never the file's contents
    _overrides_file(api).write_text(
        f'{{"alpha": {{{marker}}}', encoding="utf-8"
    )
    assert _add(api["client"], "alpha", "model-ax").status_code == 200
    failed = _entries(api["log"], "provider_overrides_load_failed")
    assert len(failed) == 1
    event = failed[0]
    assert event["level"] == "error"
    assert event["path"] == str(_overrides_file(api))
    assert event["reason"]
    assert event["detail"]
    assert marker not in api["log"].getvalue()

    # unwritable overrides file: a save failure with path/reason/detail
    blocker = api["transcript_dir"].parent / "blocker"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    monkeypatch.setenv("TRANSCRIPT_DIR", str(blocker / "sub"))
    response = _add(api["client"], "alpha", "model-ay")
    assert response.status_code == 500
    saved = _entries(api["log"], "provider_overrides_save_failed")
    assert len(saved) == 1
    event = saved[0]
    assert event["level"] == "error"
    assert event["path"] == str(blocker / "sub" / "provider_overrides.json")
    assert event["reason"]
    assert event["detail"]


def test_logs_carry_no_secrets(api):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-045"""
    # add, remove, and discovery against the provider that carries an
    # apiKey and a base URL...
    assert _add(api["client"], "beta", "model-bx").status_code == 200
    assert _remove(api["client"], "beta", "model-bx").status_code == 200
    response = api["client"].get("/api/providers/beta/available-models")
    assert response.status_code == 200

    # ...no emitted log event contains the API key or a base URL
    log = api["log"].getvalue()
    assert "sk-endpoint-test-key" not in log
    assert "127.0.0.1:41411" not in log
    assert "127.0.0.1:41412" not in log
