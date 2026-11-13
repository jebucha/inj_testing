"""Application settings: per-request read and atomic write of settings.json.

Kept free of FastAPI imports (mirroring ``app/providers.py``): the reader and
writer are pure over ``persist.transcript_dir()`` so they are testable
directly against ``tmp_path``.

The file is read on every call, never at startup (design D3): edits on disk
take effect on the next request. A missing file is the normal "defaults"
state; an unreadable or malformed file degrades to the safe off-default
without raising. Writes go to a sibling temp file followed by ``os.replace``
so a crash mid-write can never leave a truncated ``settings.json``.

The file stores only the fields a client has actually written: a missing
field reads as its default (``autoSummarize`` False, ``theme`` "system")
rather than an error, and a partial write (``save_settings`` with only one
keyword set) merges over the stored fields, leaving the others untouched.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.log import get_logger
from app.persist import transcript_dir

# Settings file name inside the transcript directory (design D2: the volume
# is already host-mounted and writable, and the name is invisible to the
# .txt-only transcript listing).
_SETTINGS_FILE = "settings.json"

# The exact ``theme`` values (design D1): "system" is the read default and
# the only value that lets the stylesheet resolve a palette before
# JavaScript runs.
THEME_VALUES = frozenset({"system", "light", "dark"})
_DEFAULT_THEME = "system"


@dataclass(frozen=True)
class Settings:
    """The result of one settings read."""

    auto_summarize: bool
    theme: str = _DEFAULT_THEME


def settings_path() -> Path:
    """Resolve the settings file path at call time (design D3)."""
    return transcript_dir() / _SETTINGS_FILE


def _log_load_failed(path: str, reason: str, detail: str) -> None:
    # The parse/OS error only — never the file's contents (design D3).
    get_logger().error(
        "settings_load_failed", path=path, reason=reason, detail=detail
    )


def load_settings() -> Settings:
    """Read and validate the settings file (per call).

    A missing file is the normal default state (no log). An unreadable file,
    malformed JSON, or a non-object top level returns the safe off-default
    without raising and logs one ``settings_load_failed`` error event
    carrying the path and the parse/OS detail — never file contents. A
    missing or non-boolean ``autoSummarize`` value is likewise off, and a
    missing, non-string, or unrecognized ``theme`` value reads as "system",
    both without a log (the file itself parsed fine).
    """
    path = settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings(auto_summarize=False)
    except OSError as exc:
        _log_load_failed(str(path), type(exc).__name__, str(exc))
        return Settings(auto_summarize=False)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _log_load_failed(str(path), "invalid_json", str(exc))
        return Settings(auto_summarize=False)
    if not isinstance(data, dict):
        _log_load_failed(str(path), "invalid_structure",
                         "top-level JSON value is not an object")
        return Settings(auto_summarize=False)
    flag = data.get("autoSummarize")
    if not isinstance(flag, bool):
        flag = False
    theme = data.get("theme")
    if not isinstance(theme, str) or theme not in THEME_VALUES:
        theme = _DEFAULT_THEME
    return Settings(auto_summarize=flag, theme=theme)


def _read_stored_fields(path: Path) -> dict:
    """The recognized setting fields as stored on disk — no defaults applied.

    The merge base for ``save_settings`` (design D2): only keys a previous
    write actually persisted are returned, and a stored value that the read
    side would treat as its default (non-boolean flag, unrecognized theme)
    is dropped so it never survives a merge. An unusable or missing file
    yields ``{}`` — the same tolerance as ``load_settings``, without the log,
    because a merge write over an unusable file is a normal first write.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    stored: dict = {}
    flag = data.get("autoSummarize")
    if isinstance(flag, bool):
        stored["autoSummarize"] = flag
    theme = data.get("theme")
    if isinstance(theme, str) and theme in THEME_VALUES:
        stored["theme"] = theme
    return stored


def save_settings(
    auto_summarize: Optional[bool] = None,
    theme: Optional[str] = None,
) -> bool:
    """Atomically persist the provided setting fields; return whether the
    write succeeded.

    ``None`` means "leave as stored": the current fields are read first, the
    provided fields are overlaid, and the merged object is written to a
    sibling temp file and swapped into place with ``os.replace`` (design D2
    and D3). A field neither provided nor stored is written as absent, so a
    first ``save_settings(True)`` still writes exactly
    ``{"autoSummarize": true}``. Never raises: on any failure it logs
    ``settings_save_failed`` (path + OS error detail) and returns ``False``.
    """
    path = settings_path()
    stored = _read_stored_fields(path)
    if auto_summarize is not None:
        stored["autoSummarize"] = bool(auto_summarize)
    if theme is not None:
        stored["theme"] = theme
    tmp_path = path.with_name(path.name + ".tmp")
    payload = json.dumps(stored)
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
            "settings_save_failed",
            path=str(path),
            reason=type(exc).__name__,
            detail=str(exc),
        )
        return False
    return True
