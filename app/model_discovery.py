"""Model discovery: OpenAI-compatible ``GET {baseURL}/models`` call for the
model-management UI's "refresh from backend" flow.

Kept free of FastAPI imports (mirroring ``app/summarize.py``): the call is a
plain synchronous function meant to be run in a worker thread on the
dedicated discovery executor in ``app/main.py`` (design D6). The HTTP
dispatch lives in the module-level :func:`_get_provider_models` seam
(mirroring ``summarize._call_chat_completions``): the e2e harness replaces
that function with a stub while :func:`list_models` keeps running for real,
so its ``provider_models_refreshed`` / ``provider_models_refresh_failed``
log emission still happens in e2e.

The response carries model id strings only — never the base URL or API key
(design D6). Discovery is advisory: a failure surfaces as 502
``PROVIDER_ERROR`` and never alters the effective model list.
"""

from __future__ import annotations

import os
import time

import requests

from app.errors import ProviderError
from app.log import get_logger
from app.providers import Provider

# Backend-call timeout in seconds (connect + read), default sized for a fast
# /models endpoint (design D6); overridable via MODEL_DISCOVERY_TIMEOUT,
# non-numeric values fall back to the default (same style as SUMMARY_TIMEOUT).
DEFAULT_DISCOVERY_TIMEOUT = 15.0

# Upper bound on ids returned per refresh: a hostile or broken backend
# cannot flood the response (design D6).
MAX_DISCOVERED_MODELS = 200


class ModelDiscoveryError(Exception):
    """A failed /models call, with a machine-readable reason.

    ``reason`` is one of ``unreachable``, ``timeout``, ``http_error``, or
    ``malformed_response``; ``detail`` is a safe, app-constructed message
    (no base URLs, API keys, or response bodies).
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def discovery_timeout() -> float:
    """Resolve the /models-call timeout at call time (design D6)."""
    raw = os.environ.get("MODEL_DISCOVERY_TIMEOUT")
    try:
        return float(raw) if raw is not None else DEFAULT_DISCOVERY_TIMEOUT
    except ValueError:
        return DEFAULT_DISCOVERY_TIMEOUT


def _get_provider_models(url: str, api_key: str | None, timeout: float) -> object:
    """GET the models endpoint and return its parsed JSON body.

    Per-call ``requests.get`` (no shared session: thread-safe without
    locking, as in ``app/summarize.py``). The bearer token is attached only
    when the provider defines an ``apiKey``. Raises
    :class:`ModelDiscoveryError` with a machine-readable reason on every
    failure — transport failures carry the exception's type name only, never
    the URL.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        raise ModelDiscoveryError(
            "timeout", f"backend did not respond within {timeout:.0f}s"
        ) from exc
    except requests.RequestException as exc:
        # Type name only: str() of requests exceptions embeds the URL, which
        # must stay out of the logs (design D6).
        raise ModelDiscoveryError("unreachable", type(exc).__name__) from exc
    if response.status_code // 100 != 2:
        raise ModelDiscoveryError(
            "http_error", f"backend returned HTTP {response.status_code}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ModelDiscoveryError(
            "malformed_response", "backend response is not valid JSON"
        ) from exc


def _parse_model_ids(data: object) -> list[str]:
    """Extract the model id list from a parsed /models body (design D6).

    Keeps only dict entries whose ``id`` is a non-empty string, dedupes
    preserving order, and caps the result at ``MAX_DISCOVERED_MODELS``.
    Raises :class:`ModelDiscoveryError` (``malformed_response``) when the
    body is not a JSON object with a ``data`` list.
    """
    if not isinstance(data, dict):
        raise ModelDiscoveryError(
            "malformed_response", "backend response is not a JSON object"
        )
    entries = data.get("data")
    if not isinstance(entries, list):
        raise ModelDiscoveryError(
            "malformed_response", "backend response missing a data list"
        )
    models: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        if model_id not in models:
            models.append(model_id)
        if len(models) >= MAX_DISCOVERED_MODELS:
            break
    return models


def list_models(provider: Provider, timeout: float | None = None) -> list[str]:
    """List the provider's models via its OpenAI-compatible /models endpoint.

    Emits exactly one structured event per call: ``provider_models_refreshed``
    (info, with count and duration) or ``provider_models_refresh_failed``
    (error, with reason and a safe detail) — never the base URL, API key, or
    response body (design D6). Raises :class:`~app.errors.ProviderError`
    (HTTP 502 ``PROVIDER_ERROR``) when the call or the parse fails.
    """
    logger = get_logger()
    start = time.monotonic()
    try:
        data = _get_provider_models(
            provider.base_url.rstrip("/") + "/models",
            provider.api_key,
            discovery_timeout() if timeout is None else timeout,
        )
        models = _parse_model_ids(data)
    except ModelDiscoveryError as exc:
        logger.error(
            "provider_models_refresh_failed",
            provider=provider.id,
            reason=exc.reason,
            detail=exc.detail,
        )
        raise ProviderError(
            "Could not refresh the model list from the backend. Please try again."
        ) from exc
    logger.info(
        "provider_models_refreshed",
        provider=provider.id,
        count=len(models),
        duration_ms=round((time.monotonic() - start) * 1000.0, 2),
    )
    return models
