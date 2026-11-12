"""Provider overrides store: per-request read and atomic write of
provider_overrides.json, plus the file-config-plus-overlay merge.

Kept free of FastAPI imports (mirroring ``app/providers.py`` and
``app/settings.py``): the reader, merge, and writer are pure over
``persist.transcript_dir()`` so they are testable directly against
``tmp_path``.

The overrides file holds only model ids that were added through the UI,
shaped ``{"<providerId>": ["model-id", ...]}`` (design D1). It never
defines a provider, a base URL, or an API key. The file is read on every
call, never at startup (design D3): edits on disk take effect on the next
request. A missing file is the normal "no additions" state; an unreadable
or malformed file degrades to no additions without raising. Writes go to a
sibling temp file followed by ``os.replace`` so a crash mid-write can never
leave a truncated file (the same pattern as ``settings.save_settings``).

Read-modify-write sequences run under a module-level lock: the app is a
single uvicorn process, so a process-local lock is sufficient
(multi-process coordination is a documented non-goal).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from pathlib import Path

from app.errors import (
    InvalidModelError,
    InvalidProviderError,
    ModelNotRemovableError,
)
from app.log import get_logger
from app.persist import transcript_dir
from app.providers import Provider, ProviderConfig, load_providers

# Overrides file name inside the transcript directory (design D1: the volume
# is already host-mounted and writable, and the name is invisible to the
# .txt-only transcript listing).
_OVERRIDES_FILE = "provider_overrides.json"

# Bounds for UI-added model ids (design D5).
MAX_MODEL_ID_CHARS = 200
MAX_ADDED_PER_PROVIDER = 50

# Guards read-modify-write sequences in this process (see module docstring).
_lock = threading.Lock()


class ProviderOverridesWriteError(Exception):
    """The atomic overlay write failed (the failure is already logged)."""


def overrides_path() -> Path:
    """Resolve the overrides file path at call time (design D3)."""
    return transcript_dir() / _OVERRIDES_FILE


def _log_load_failed(path: str, reason: str, detail: str) -> None:
    # The parse/OS error only — never the file's contents (design D3).
    get_logger().error(
        "provider_overrides_load_failed", path=path, reason=reason, detail=detail
    )


def load_overrides() -> dict[str, list[str]]:
    """Read and validate the overrides file (per call).

    A missing file is the normal "no additions" state (no log). An
    unreadable file, malformed JSON, or a non-object top level degrades to
    ``{}`` without raising and logs one ``provider_overrides_load_failed``
    error event carrying the path and the parse/OS detail — never file
    contents. Per-entry tolerance: a provider value that is not a list of
    strings is dropped for that provider only, without a log (the file
    itself parsed fine).
    """
    path = overrides_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        _log_load_failed(str(path), type(exc).__name__, str(exc))
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _log_load_failed(str(path), "invalid_json", str(exc))
        return {}
    if not isinstance(data, dict):
        _log_load_failed(str(path), "invalid_structure",
                         "top-level JSON value is not an object")
        return {}
    overrides: dict[str, list[str]] = {}
    for provider_id, models in data.items():
        if not isinstance(models, list):
            continue
        ids = [m for m in models if isinstance(m, str) and m]
        if ids:
            overrides[str(provider_id)] = ids
    return overrides


def apply_overrides(config: ProviderConfig,
                    overrides: dict[str, list[str]]) -> ProviderConfig:
    """Merge the overlay into a file-read ``ProviderConfig`` (pure).

    The provider set comes **only** from ``config.providers``: overlay keys
    for unknown providers are ignored (and left on disk). Each provider's
    effective ``models`` are the file models in order, followed by the
    overlay ids not already present (first occurrence wins); the overlay ids
    actually used are carried in ``added_models`` so the listing can expose
    them as removable (design D2).
    """
    if not overrides:
        return config
    providers = []
    for provider in config.providers:
        added = _added_for(provider, overrides.get(provider.id, ()))
        if not added:
            providers.append(provider)
        else:
            providers.append(replace(
                provider,
                models=provider.models + tuple(added),
                added_models=tuple(added),
            ))
    return ProviderConfig(tuple(providers), config.default)


def _added_for(provider: Provider, overlay_ids: list[str]) -> list[str]:
    """The overlay ids that extend this provider, deduped, in file order."""
    added: list[str] = []
    for model in overlay_ids:
        if model in provider.models or model in added:
            continue
        added.append(model)
    return added


def _write_overrides(overrides: dict[str, list[str]]) -> bool:
    """Atomically persist the full overrides map; never raises.

    Writes to a sibling temp file and swaps it into place with
    ``os.replace``. On any failure it logs ``provider_overrides_save_failed``
    (path + OS error detail, never file contents), cleans up the temp file,
    and returns ``False``.
    """
    path = overrides_path()
    tmp_path = path.with_name(path.name + ".tmp")
    payload = json.dumps(overrides)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)
    except Exception as exc:
        # Best-effort cleanup of a stranded temp file; the replace itself
        # never leaves one behind.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        get_logger().error(
            "provider_overrides_save_failed",
            path=str(path),
            reason=type(exc).__name__,
            detail=str(exc),
        )
        return False
    return True


def validate_model_id(raw_model: object) -> str | None:
    """Validate a client-supplied model id (design D5).

    Returns the trimmed id when it is a non-empty string of at most
    ``MAX_MODEL_ID_CHARS`` characters after trimming and free of control
    characters; otherwise ``None``.
    """
    if not isinstance(raw_model, str):
        return None
    model = raw_model.strip()
    if not model or len(model) > MAX_MODEL_ID_CHARS:
        return None
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in model):
        return None
    return model


def add_model(provider_id: str, raw_model: str) -> tuple[str, tuple[str, ...]]:
    """Persist ``raw_model`` as an overlay addition for ``provider_id``.

    Read-modify-write under the module lock. The provider must exist in the
    config file (validated by the caller; re-checked here defensively).
    Adding an id already in the effective list is idempotent: no write, no
    event, and the id is simply not duplicated. Emits one
    ``provider_model_added`` (info) event on an actual addition — never
    secrets or the model list.

    Raises :class:`~app.errors.InvalidModelError` when the id violates the
    id rules or the per-provider addition cap,
    :class:`~app.errors.InvalidProviderError` when the provider is missing
    from the config file, and :class:`ProviderOverridesWriteError` when the
    atomic write fails. Returns ``(trimmed id, effective model ids in
    order)``.
    """
    model = validate_model_id(raw_model)
    if model is None:
        raise InvalidModelError()
    with _lock:
        overrides = load_overrides()
        current = list(overrides.get(provider_id) or [])
        config = load_providers()
        provider = next(
            (p for p in config.providers if p.id == provider_id), None
        )
        if provider is None:
            raise InvalidProviderError()
        if model not in provider.models and model not in current:
            if len(current) >= MAX_ADDED_PER_PROVIDER:
                raise InvalidModelError()
            current.append(model)
            overrides[provider_id] = current
            if not _write_overrides(overrides):
                raise ProviderOverridesWriteError()
            # The event carries only the provider and model ids (design D3).
            get_logger().info(
                "provider_model_added", provider=provider_id, model=model
            )
        effective = provider.models + tuple(_added_for(provider, current))
        return model, effective


class ModelNotInOverlayError(Exception):
    """The model id is in neither the config file nor the overlay."""


def remove_model(provider_id: str, raw_model: str) -> tuple[str, tuple[str, ...]]:
    """Remove an overlay addition for ``provider_id`` (read-modify-write
    under the module lock).

    A config-file model is not removable (raises
    :class:`~app.errors.ModelNotRemovableError`), an id in neither set
    raises :class:`ModelNotInOverlayError`, and a provider missing from the
    config file raises :class:`~app.errors.InvalidProviderError`. Emits one
    ``provider_model_removed`` (info) event on success.

    Raises :class:`ProviderOverridesWriteError` when the atomic write fails.
    Returns ``(trimmed id, remaining effective model ids in order)``.
    """
    model = raw_model.strip() if isinstance(raw_model, str) else ""
    with _lock:
        overrides = load_overrides()
        config = load_providers()
        provider = next(
            (p for p in config.providers if p.id == provider_id), None
        )
        if provider is None:
            raise InvalidProviderError()
        if model in provider.models:
            raise ModelNotRemovableError()
        current = list(overrides.get(provider_id) or [])
        if model not in current:
            raise ModelNotInOverlayError()
        current.remove(model)
        if current:
            overrides[provider_id] = current
        else:
            overrides.pop(provider_id, None)
        if not _write_overrides(overrides):
            raise ProviderOverridesWriteError()
        get_logger().info(
            "provider_model_removed", provider=provider_id, model=model
        )
        effective = provider.models + tuple(_added_for(provider, current))
        return model, effective
