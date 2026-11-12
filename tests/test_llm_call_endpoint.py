"""T-PROMPT-INJECTION-BENCHMARK-011 .. 015 + preset registry / error entry.

The preset registry (app/summarize.py), the InvalidPresetError taxonomy
entry (app/errors.py), and the non-persisting POST /api/llm-call endpoint
(app/main.py), unit-tested with TestClient and the chat-completions dispatch
stubbed at the same seam the summarization endpoint tests use.
"""

import json
import threading
import time

import pytest
from starlette.testclient import TestClient

from app import summarize as summarize_mod
from app.errors import InvalidPresetError
from app.main import create_app

# --- preset registry and error entry (tasks 1.1 / 1.2) ------------------------


def test_presets_resolve_to_distinct_non_empty_text():
    """Both preset ids resolve to non-empty, distinct system-prompt text; an
    unknown id is rejected."""
    summarize_text = summarize_mod.resolve_preset("summarize")
    judge_text = summarize_mod.resolve_preset("judge")

    assert summarize_text and judge_text
    assert summarize_text != judge_text
    assert summarize_text == summarize_mod.SUMMARY_INSTRUCTION
    assert judge_text == summarize_mod.JUDGE_INSTRUCTION


def test_unknown_preset_rejected():
    with pytest.raises(InvalidPresetError):
        summarize_mod.resolve_preset("not-a-preset")
    # an empty id is unknown too
    with pytest.raises(InvalidPresetError):
        summarize_mod.resolve_preset("")


def test_invalid_preset_error_entry():
    error = InvalidPresetError()

    assert error.code == "INVALID_PRESET"
    assert error.status == 400
    assert error.message  # a stable, human-readable message


# --- API endpoint (TestClient; dispatch stubbed, files on tmp_path) -----------


class RecordingDispatch:
    """Recording stand-in for summarize_mod._call_chat_completions."""

    def __init__(self):
        self.calls = []
        self.output = "The model output."
        self.failure = None  # None | (reason, detail)

    def reset(self):
        self.calls = []
        self.failure = None

    def set_failure(self, reason, detail):
        self.failure = (reason, detail)

    def __call__(self, base_url, model, messages, api_key, timeout):
        self.calls.append({
            "base_url": base_url, "model": model, "messages": messages,
            "api_key": api_key, "timeout": timeout,
        })
        if self.failure is not None:
            raise summarize_mod.ProviderCallError(*self.failure)
        return self.output


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
    """TestClient with a tmp provider config, a tmp transcript dir, and the
    chat-completions dispatch replaced by a recording stub."""
    config_file = tmp_path / "providers.json"
    config_file.write_text(json.dumps(PROVIDER_CONFIG), encoding="utf-8")
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    monkeypatch.setenv("PROVIDERS_CONFIG", str(config_file))
    monkeypatch.setenv("TRANSCRIPT_DIR", str(transcript_dir))
    dispatch = RecordingDispatch()
    monkeypatch.setattr(summarize_mod, "_call_chat_completions", dispatch)
    client = TestClient(create_app())
    with client:
        yield {
            "client": client,
            "config_file": config_file,
            "transcript_dir": transcript_dir,
            "dispatch": dispatch,
        }


def _valid_body(text="The transcript text.", preset="summarize",
                provider="alpha", model="model-a1"):
    return {"text": text, "preset": preset, "provider": provider,
            "model": model}


def test_llm_call_returns_output_without_persisting(api):
    """T-PROMPT-INJECTION-BENCHMARK-011"""
    for preset in ("summarize", "judge"):
        api["dispatch"].reset()
        response = api["client"].post(
            "/api/llm-call", json=_valid_body(preset=preset)
        )

        assert response.status_code == 200
        assert response.json() == {"text": "The model output."}
        assert len(api["dispatch"].calls) == 1
        # the system prompt is the preset's text, the user message the body
        messages = api["dispatch"].calls[0]["messages"]
        assert messages[0] == {
            "role": "system", "content": summarize_mod.PRESETS[preset]
        }
        assert messages[1] == {"role": "user", "content": "The transcript text."}
        # the endpoint never persists: the transcript dir stays empty
        assert list(api["transcript_dir"].iterdir()) == []


def test_unknown_preset_rejected_before_backend(api):
    """T-PROMPT-INJECTION-BENCHMARK-012"""
    response = api["client"].post(
        "/api/llm-call", json=_valid_body(preset="not-a-preset")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PRESET"
    # no backend request was made
    assert api["dispatch"].calls == []

    # invalid preset wins over an equally invalid provider (order: preset
    # first, then unknown provider/model)
    response = api["client"].post(
        "/api/llm-call",
        json=_valid_body(preset="not-a-preset", provider="ghost"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PRESET"
    assert api["dispatch"].calls == []


def test_local_rejections_made_without_backend_call(api):
    """The analogous not-configured / invalid-provider / overlong rejections,
    each asserted with no backend call made (the rejection order after an
    invalid preset)."""
    # not configured: a valid preset but an empty config
    api["config_file"].unlink()
    response = api["client"].post("/api/llm-call", json=_valid_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_CONFIGURED"
    assert api["dispatch"].calls == []

    # unknown provider / model (config restored by rewriting the file)
    api["config_file"].write_text(json.dumps(PROVIDER_CONFIG), encoding="utf-8")
    response = api["client"].post(
        "/api/llm-call", json=_valid_body(provider="ghost")
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PROVIDER"
    assert api["client"].post(
        "/api/llm-call", json=_valid_body(model="model-zz")
    ).json()["error"]["code"] == "INVALID_PROVIDER"

    # overlong text (the other rejections would also apply to the body; the
    # provider/model are valid, so the length check is the failing step)
    response = api["client"].post(
        "/api/llm-call",
        json=_valid_body(text="x" * (summarize_mod.MAX_INPUT_CHARS + 1)),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INPUT_TOO_LONG"
    assert api["dispatch"].calls == []

    # at the cap the call goes through
    response = api["client"].post(
        "/api/llm-call", json=_valid_body(text="x" * summarize_mod.MAX_INPUT_CHARS)
    )
    assert response.status_code == 200
    assert len(api["dispatch"].calls) == 1


def test_client_supplied_system_prompt_ignored(api):
    """T-PROMPT-INJECTION-BENCHMARK-013"""
    response = api["client"].post(
        "/api/llm-call",
        json=dict(_valid_body(), system="EVIL_CLIENT_SYSTEM_PROMPT",
                  systemPrompt="EVIL_CLIENT_SYSTEM_PROMPT",
                  instructions="EVIL_CLIENT_SYSTEM_PROMPT"),
    )

    assert response.status_code == 200
    assert response.json() == {"text": "The model output."}
    # the system prompt used is the server-side preset's text, not the
    # client-supplied field
    messages = api["dispatch"].calls[0]["messages"]
    assert messages[0] == {
        "role": "system", "content": summarize_mod.SUMMARY_INSTRUCTION
    }
    assert "EVIL_CLIENT_SYSTEM_PROMPT" not in json.dumps(messages)


def test_llm_call_respects_concurrency_bound(api, monkeypatch):
    """T-PROMPT-INJECTION-BENCHMARK-015"""
    # Tracking stub for the call function: the endpoint sends it through the
    # bounded pool (SUMMARIZE_EXECUTOR, shared with summarization), so it
    # runs at most SUMMARIZE_MAX_CONCURRENCY times concurrently.
    lock = threading.Lock()
    state = {"active": 0, "peak": 0, "started": 0}

    def tracking_stub(provider, model, preset, text):
        with lock:
            state["active"] += 1
            state["started"] += 1
            state["peak"] = max(state["peak"], state["active"])
        try:
            time.sleep(0.2)  # long enough for all 4 requests to overlap
        finally:
            with lock:
                state["active"] -= 1
        return "The model output."

    monkeypatch.setattr(summarize_mod, "call_with_preset", tracking_stub)

    responses = []

    def post_request():
        # list.append is atomic under the GIL
        responses.append(api["client"].post("/api/llm-call", json=_valid_body()))

    threads = [threading.Thread(target=post_request) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert [r.status_code for r in responses] == [200] * 4
    assert [r.json() for r in responses] == [{"text": "The model output."}] * 4
    assert state["started"] == 4
    assert state["peak"] <= 2


def test_backend_failure_returns_502(api):
    """T-PROMPT-INJECTION-BENCHMARK-014"""
    api["dispatch"].set_failure("unreachable", "ConnectionError")

    response = api["client"].post("/api/llm-call", json=_valid_body())

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "PROVIDER_ERROR"
    # a message suggesting a retry
    assert "try again" in error["message"].lower()
    # and the non-2xx / malformed / empty shapes map to the same code:
    # those raise ProviderCallError inside _call_chat_completions, which the
    # call function turns into a ProviderError before the endpoint sees it.
    for reason in ("http_error", "malformed_response", "empty_response",
                   "timeout"):
        api["dispatch"].set_failure(reason, "detail")
        response = api["client"].post("/api/llm-call", json=_valid_body())
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "PROVIDER_ERROR"
