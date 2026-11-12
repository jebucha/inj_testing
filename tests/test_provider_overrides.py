"""T-SUMMARIZATION-MODEL-MANAGEMENT-001 .. 007.

The provider-overrides store (app/provider_overrides.py): overlay reading,
merge into the file config, and the read-only transcript listing's
exclusion of the overrides file. Unit-tested against tmp_path with a
captured log stream.
"""

import io
import json

from starlette.testclient import TestClient

from app import log as applog
from app.library import list_transcripts
from app.main import create_app
from app.provider_overrides import apply_overrides, load_overrides
from app.providers import Provider, ProviderConfig


def _file_config(models=("a", "b"), provider_id="radai"):
    return ProviderConfig(
        (Provider(
            id=provider_id, name="Radai Local",
            base_url="http://localhost:8181/v1", api_key=None,
            models=tuple(models),
        ),),
        provider_id,
    )


def _entries(buf, event=None) -> list[dict]:
    lines = [json.loads(ln) for ln in buf.getvalue().splitlines() if ln.strip()]
    return lines if event is None else [e for e in lines if e.get("event") == event]


def test_overrides_merge_after_file_models(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-001"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["c"]}), encoding="utf-8"
    )

    config = apply_overrides(_file_config(("a", "b")), load_overrides())

    (provider,) = config.providers
    assert provider.models == ("a", "b", "c")
    assert provider.added_models == ("c",)
    assert config.default == "radai"


def test_override_duplicates_not_repeated(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-002"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))
    # The id already present in the file list is not repeated ...
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["a", "b", "a"]}), encoding="utf-8"
    )
    config = apply_overrides(_file_config(("a", "b")), load_overrides())
    (provider,) = config.providers
    assert provider.models == ("a", "b")
    assert provider.added_models == ()

    # ...and overlay entries that duplicate each other appear once
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["c", "c"]}), encoding="utf-8"
    )
    config = apply_overrides(_file_config(("a", "b")), load_overrides())
    (provider,) = config.providers
    assert provider.models == ("a", "b", "c")
    assert provider.added_models == ("c",)


def test_overlay_cannot_add_provider(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-003"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))
    # The overlay names a provider that is not in the config file.
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["c"], "ghost": ["x", "y"]}), encoding="utf-8"
    )

    config = apply_overrides(_file_config(("a", "b")), load_overrides())

    assert [p.id for p in config.providers] == ["radai"]
    (provider,) = config.providers
    assert provider.models == ("a", "b", "c")
    assert "ghost" not in {p.id for p in config.providers}


def test_missing_overrides_means_file_only(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-004"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))  # no file in the dir
    buf = io.StringIO()
    applog.setup_logging(stream=buf)

    config = apply_overrides(_file_config(("a", "b")), load_overrides())

    (provider,) = config.providers
    assert provider.models == ("a", "b")
    assert provider.added_models == ()
    # a missing file is the normal state: no failure is logged
    assert not _entries(buf, "provider_overrides_load_failed")


def test_malformed_overrides_degrades(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-005"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))
    marker = "SECRET_OVERRIDES_CONTENT_MARKER_42"

    for content in (f'{{"radai": {{{marker}}}', json.dumps(["not", "an", "object"])):
        (tmp_path / "provider_overrides.json").write_text(content, encoding="utf-8")
        buf = io.StringIO()
        applog.setup_logging(stream=buf)

        # no request crashes: the read degrades to no additions...
        config = apply_overrides(_file_config(("a", "b")), load_overrides())
        (provider,) = config.providers
        assert provider.models == ("a", "b")
        assert provider.added_models == ()

        # ...and one load-failed event records the path and the reason,
        # never the file's contents
        failed = _entries(buf, "provider_overrides_load_failed")
        assert len(failed) == 1
        event = failed[0]
        assert event["level"] == "error"
        assert event["path"] == str(tmp_path / "provider_overrides.json")
        assert event["reason"]
        assert event["detail"]
        assert marker not in buf.getvalue()


def test_overrides_edit_takes_effect_without_restart(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-006"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))

    # The app has already served a provider list (no additions yet)...
    config = apply_overrides(_file_config(("a", "b")), load_overrides())
    (provider,) = config.providers
    assert provider.models == ("a", "b")

    # ...then the overrides file gains a model after the fact; the next
    # read picks it up without a restart.
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["c"]}), encoding="utf-8"
    )
    config = apply_overrides(_file_config(("a", "b")), load_overrides())
    (provider,) = config.providers
    assert provider.models == ("a", "b", "c")


def test_overrides_file_excluded_from_list(tmp_path, monkeypatch):
    """T-SUMMARIZATION-MODEL-MANAGEMENT-007"""
    monkeypatch.setenv("TRANSCRIPT_DIR", str(tmp_path))
    (tmp_path / "provider_overrides.json").write_text(
        json.dumps({"radai": ["c"]}), encoding="utf-8"
    )
    (tmp_path / "video.txt").write_text("transcript\n", encoding="utf-8")

    # directly: the .txt-only listing never sees the overrides file
    assert [t["name"] for t in list_transcripts()] == ["video.txt"]

    # and through the endpoint
    client = TestClient(create_app())
    with client:
        response = client.get("/api/transcripts")
    assert response.status_code == 200
    assert [t["name"] for t in response.json()["transcripts"]] == ["video.txt"]
