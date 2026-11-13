"""FastAPI application: lifecycle logging, request logging, static UI."""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Empty

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import benchmark_dataset
from app import chain as chain_mod
from app import log as applog
from app import logbus
from app import model_discovery
from app import summarize as summarize_mod
from app.errors import (
    InputTooLongError,
    InvalidModelError,
    InvalidPresetError,
    InvalidProviderError,
    ModelNotRemovableError,
    SummaryNotConfiguredError,
    TranscriptError,
)
from app.library import (
    is_structurally_invalid_name,
    list_transcripts,
    read_transcript,
)
from app.log import get_logger
from app.persist import derive_file_name, save_transcript
from app.provider_overrides import (
    ModelNotInOverlayError,
    ProviderOverridesWriteError,
    add_model,
    apply_overrides,
    load_overrides,
    remove_model,
)
from app.providers import load_providers
from app.settings import load_settings, save_settings

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PORT = 8000

# How long a log stream waits for the next entry before looping again. The
# poll runs in an executor thread, so a client disconnect can cancel the
# in-flight poll instead of leaving a worker blocked in queue.get().
LOG_POLL_TIMEOUT = 0.5

# Max concurrent summarization backend calls. Each call pins a worker for up
# to the 300 s LLM timeout, so it runs on a bounded pool of its own rather
# than the default executor every other endpoint's blocking work shares;
# excess in-flight requests wait for a free slot instead of being rejected.
SUMMARIZE_MAX_CONCURRENCY = 2
SUMMARIZE_EXECUTOR = ThreadPoolExecutor(
    max_workers=SUMMARIZE_MAX_CONCURRENCY, thread_name_prefix="summarize"
)

# Max concurrent model-discovery calls (GET /models). Discovery gets its own
# bounded pool rather than SUMMARIZE_EXECUTOR (design D6): a 300 s summarize
# must not block a fast /models call, and a hanging discovery must not starve
# summarization.
DISCOVERY_MAX_CONCURRENCY = 2
DISCOVERY_EXECUTOR = ThreadPoolExecutor(
    max_workers=DISCOVERY_MAX_CONCURRENCY, thread_name_prefix="model-discovery"
)

# Max request-body size in bytes (5 MiB). Checked against the declared
# Content-Length before the body is read or parsed, so an oversized upload
# cannot exhaust process memory. The app's real payload ceiling is the
# 100k-char text cap (<1 MB worst case), so 5 MiB leaves wide headroom.
# Module-level so tests can monkeypatch it.
MAX_BODY_BYTES = 5 * 1024 * 1024


class TranscriptRequest(BaseModel):
    url: str = ""


class SummarizeRequest(BaseModel):
    text: str = ""  # the displayed transcript (source of truth, design 4)
    name: str = ""  # the transcript's file name (for the alongside save)
    provider: str = ""
    model: str = ""


class LlmCallRequest(BaseModel):
    # The non-persisting preset-driven provider call
    # (prompt-injection-benchmark). The system prompt comes only from the
    # server-side preset registry via `preset`; the model deliberately
    # defines no system-prompt field, so any client-supplied one is ignored
    # (pydantic drops unknown fields).
    text: str = ""
    preset: str = ""
    provider: str = ""
    model: str = ""

# Configure JSON-to-stdout logging once, at import time, so every entry point
# (uvicorn app.main:app, python -m app.main, tests) emits the same format.
# Tests may reconfigure afterwards; loggers are created lazily, so nothing
# binds to the import-time configuration.
applog.setup_logging()


def _listen_port() -> int:
    try:
        return int(os.environ.get("PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT


def _merged_provider_config():
    """The effective provider config: file providers/models plus the
    UI-added overlay models (design D2). The single source both the listing
    and the summarize validation read, per request."""
    return apply_overrides(load_providers(), load_overrides())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = get_logger()
    logger.info("server_started", port=_listen_port())
    try:
        yield
    finally:
        get_logger().info("server_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="inj-testing", lifespan=lifespan)
    applog.install_excepthook()

    # Registered before the logging middleware (Starlette applies the
    # first-added HTTP middleware as the outermost layer) so 413 rejections
    # are covered by the http_request log line. Header check only: the
    # declared length is compared without reading the body, which fires
    # before Starlette's full-body read + JSON parse.
    @app.middleware("http")
    async def limit_body_size(request, call_next):
        length = request.headers.get("content-length")
        if length is not None and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "BODY_TOO_LARGE",
                                   "message": "Request body too large."}},
            )
        return await call_next(request)

    @app.middleware("http")
    async def log_http_requests(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000.0
            get_logger().error(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=500,
                duration_ms=round(duration_ms, 2),
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000.0
        get_logger().info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response

    @app.post("/api/transcript")
    async def transcript_endpoint(request: TranscriptRequest):
        try:
            result = await chain_mod.default_chain.run(request.url)
        except TranscriptError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        # Best-effort persistence after a successful fetch: runs in a worker
        # thread (blocking I/O off the event loop) and never affects the
        # response (design decisions 1, 4 and 5).
        await asyncio.to_thread(
            save_transcript, result.text, result.title, result.video_id
        )
        # The derived persistence name (design decision 5): computed from the
        # title/video id, so the client gets it even when the best-effort
        # save above failed. Single source of truth for the file name.
        return {
            "text": result.text,
            "video_id": result.video_id,
            "title": result.title,
            "language": result.language,
            "source": result.source,
            "name": derive_file_name(result.title, result.video_id),
        }

    @app.get("/api/transcripts")
    async def list_transcripts_endpoint():
        # Read-only, best-effort: an unusable directory degrades to an empty
        # list (never an error). Blocking I/O runs off the event loop, as with
        # save_transcript; the endpoint never touches the fetch chain or the
        # single-flight semaphore (design decisions 1, 4 and 5).
        transcripts = await asyncio.to_thread(list_transcripts)
        return {"transcripts": transcripts}

    @app.get("/api/providers")
    async def providers_endpoint():
        # Read the config per request (design decision 3): edits take effect
        # without a restart, a missing/malformed file degrades to "not
        # configured". The response is secret-free: API keys and base URLs
        # never leave the server (design decision 7).
        # Effective config = file config plus overlay (design D2): added
        # models are listed after the file models, with addedModels exposing
        # the removable subset. The response is secret-free: API keys and
        # base URLs never leave the server.
        config = await asyncio.to_thread(_merged_provider_config)
        return {
            "default": config.default,
            "providers": [
                {"id": p.id, "name": p.name, "models": list(p.models),
                 "addedModels": list(p.added_models)}
                for p in config.providers
            ],
        }

    @app.post("/api/providers/{provider_id}/models")
    async def add_model_endpoint(provider_id: str, request: Request):
        # Validate the body before any filesystem access (design D5): a
        # non-object body or a missing model field is 400 INVALID_BODY with
        # no write; a model value that violates the id rules, or one that
        # would exceed the per-provider cap, is 400 INVALID_MODEL. The
        # provider must exist in the file config (400 INVALID_PROVIDER) —
        # the overlay never introduces providers. The read-modify-write
        # runs in a worker thread (blocking I/O off the event loop) and
        # never touches the fetch chain or the single-flight semaphore.
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict) or "model" not in body:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_BODY",
                                   "message": "Expected a JSON object with a "
                                              "model field."}},
            )
        model = body["model"]
        config = await asyncio.to_thread(load_providers)
        if not any(p.id == provider_id for p in config.providers):
            error = InvalidProviderError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        try:
            added, models = await asyncio.to_thread(add_model, provider_id, model)
        except InvalidModelError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        except ProviderOverridesWriteError:
            # provider_overrides_save_failed was already logged by the store.
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "WRITE_FAILED",
                                   "message": "Could not save the model "
                                              "overrides file."}},
            )
        return {"provider": provider_id, "model": added,
                "models": list(models)}

    @app.delete("/api/providers/{provider_id}/models")
    async def remove_model_endpoint(provider_id: str, request: Request):
        # The model id travels in the JSON body, not the path: model ids
        # routinely contain "/" (design D4). The provider must exist in the
        # file config (400 INVALID_PROVIDER); a config-file model is not
        # removable (400 MODEL_NOT_REMOVABLE); an id in neither set is
        # 404 NOT_FOUND. The read-modify-write runs in a worker thread and
        # never touches the fetch chain or the single-flight semaphore.
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict) or "model" not in body:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_BODY",
                                   "message": "Expected a JSON object with a "
                                              "model field."}},
            )
        model = body["model"]
        config = await asyncio.to_thread(load_providers)
        if not any(p.id == provider_id for p in config.providers):
            error = InvalidProviderError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        try:
            removed, models = await asyncio.to_thread(
                remove_model, provider_id, model
            )
        except ModelNotRemovableError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        except ModelNotInOverlayError:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND",
                                   "message": "That model is not configured "
                                              "for this provider."}},
            )
        except ProviderOverridesWriteError:
            # provider_overrides_save_failed was already logged by the store.
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "WRITE_FAILED",
                                   "message": "Could not save the model "
                                              "overrides file."}},
            )
        return {"provider": provider_id, "model": removed,
                "models": list(models)}

    @app.get("/api/providers/{provider_id}/available-models")
    async def available_models_endpoint(provider_id: str):
        # Discovery (design D6): the provider is resolved against the file
        # config first (400 INVALID_PROVIDER, backend-free) — the overlay
        # never changes which base URL is contacted. The /models call runs on
        # the dedicated bounded pool, so a hanging discovery can neither
        # starve summarization nor the default executor other endpoints
        # share; a backend failure is 502 PROVIDER_ERROR with the failure
        # already logged by the module. The response carries model id strings
        # only — never the base URL or API key. Never touches the fetch chain
        # or the single-flight semaphore.
        config = await asyncio.to_thread(load_providers)
        provider = next(
            (p for p in config.providers if p.id == provider_id), None
        )
        if provider is None:
            error = InvalidProviderError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        try:
            models = await asyncio.get_running_loop().run_in_executor(
                DISCOVERY_EXECUTOR,
                contextvars.copy_context().run,
                model_discovery.list_models,
                provider,
            )
        except TranscriptError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        return {"models": list(models)}

    @app.get("/api/settings")
    async def settings_read_endpoint():
        # Read settings.json per request (design D3): edits on disk take
        # effect without a restart, and a missing/unusable file degrades to
        # the safe off-default. Read-only and side-effect-free: it never
        # touches the fetch chain or the single-flight semaphore, and blocking
        # I/O runs off the event loop.
        settings = await asyncio.to_thread(load_settings)
        return {"autoSummarize": settings.auto_summarize}

    @app.post("/api/settings")
    async def settings_write_endpoint(request: Request):
        # Validate the body before any filesystem access (design D3): a
        # non-object body or a missing/non-boolean autoSummarize is a 400
        # INVALID_BODY with no write. A write failure is a 500 WRITE_FAILED
        # (save_settings already logged settings_save_failed). Never touches
        # the fetch chain or the single-flight semaphore.
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_BODY",
                                   "message": "Expected a JSON object with a "
                                              "boolean autoSummarize field."}},
            )
        auto_summarize = body.get("autoSummarize")
        if not isinstance(auto_summarize, bool):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_BODY",
                                   "message": "autoSummarize must be a "
                                              "boolean."}},
            )
        saved = await asyncio.to_thread(save_settings, auto_summarize)
        if not saved:
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "WRITE_FAILED",
                                   "message": "Could not save the settings "
                                              "file."}},
            )
        return {"autoSummarize": auto_summarize}

    @app.get("/api/transcripts/{name}")
    async def read_transcript_endpoint(name: str):
        # Structural reject is the hard 400 rule (design decision 3, step 1),
        # applied before any filesystem access; a plain miss is a 404.
        if is_structurally_invalid_name(name):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_NAME",
                                   "message": "Invalid transcript name."}},
            )
        ok, text = await asyncio.to_thread(read_transcript, name)
        if not ok:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND",
                                   "message": "This transcript is no longer available."}},
            )
        return {"name": name, "text": text}

    @app.get("/api/transcripts/{name}/summary")
    async def read_summary_endpoint(name: str):
        # Structural reject is the hard 400 rule, applied before any
        # filesystem access; a plain miss is a 404. Read-only and
        # side-effect-free, and it never touches the fetch chain or the
        # single-flight semaphore (design decisions 4 and 9).
        if is_structurally_invalid_name(name):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_NAME",
                                   "message": "Invalid transcript name."}},
            )
        ok, summary = await asyncio.to_thread(summarize_mod.read_summary, name)
        if not ok:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND",
                                   "message": "No saved summary for this transcript."}},
            )
        return {"name": name, "summary": summary}

    @app.post("/api/summarize")
    async def summarize_endpoint(request: SummarizeRequest):
        # Validation order (design decision 8): cheap local checks precede
        # the expensive network call, every rejection path is backend-free,
        # and when several rejections apply the first failing step wins.
        if is_structurally_invalid_name(request.name):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_NAME",
                                   "message": "Invalid transcript name."}},
            )
        # The merged config is the single source the endpoint validates
        # against (design D2): overlay-added models are accepted exactly
        # like file models.
        config = await asyncio.to_thread(_merged_provider_config)
        if not config.providers:
            error = SummaryNotConfiguredError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        provider = next(
            (p for p in config.providers if p.id == request.provider), None
        )
        if provider is None or request.model not in provider.models:
            error = InvalidProviderError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        if len(request.text) > summarize_mod.MAX_INPUT_CHARS:
            error = InputTooLongError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        # The backend call runs in a worker thread on the dedicated bounded
        # pool (SUMMARIZE_EXECUTOR), so in-flight LLM calls can never occupy
        # the default executor other endpoints share; excess in-flight
        # requests wait for a free pool slot. run_in_executor with a copied
        # context mirrors asyncio.to_thread's semantics — this runtime's
        # to_thread has no executor parameter (design D1 runtime note) — and
        # the endpoint never touches the fetch chain or the single-flight
        # semaphore (design decision 9).
        try:
            summary = await asyncio.get_running_loop().run_in_executor(
                SUMMARIZE_EXECUTOR,
                contextvars.copy_context().run,
                summarize_mod.summarize_with_provider,
                provider, request.model, request.text,
            )
        except TranscriptError as exc:
            # ProviderError (PROVIDER_ERROR 502) and friends.
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        # Best-effort summary save: a failure is logged, never returned
        # (design decision 6).
        await asyncio.to_thread(summarize_mod.save_summary, request.name, summary)
        return {"summary": summary}

    @app.post("/api/llm-call")
    async def llm_call_endpoint(request: LlmCallRequest):
        # The injection benchmark's non-persisting provider call: the system
        # prompt comes only from the server-side preset registry, the result
        # is returned as `text`, and this route never creates or modifies a
        # file. Local rejection order (all backend-free, first failing step
        # wins): invalid preset -> not configured -> unknown provider/model
        # -> overlong text.
        try:
            summarize_mod.resolve_preset(request.preset)
        except InvalidPresetError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code,
                                   "message": exc.message}},
            )
        config = await asyncio.to_thread(load_providers)
        if not config.providers:
            error = SummaryNotConfiguredError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        provider = next(
            (p for p in config.providers if p.id == request.provider), None
        )
        if provider is None or request.model not in provider.models:
            error = InvalidProviderError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        if len(request.text) > summarize_mod.MAX_INPUT_CHARS:
            error = InputTooLongError()
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code,
                                   "message": error.message}},
            )
        # Shared bounded pool with summarization (the same 2-worker cap),
        # same run_in_executor + copied-context pattern: the benchmark adds
        # no new unbounded-LLM surface. ProviderError (PROVIDER_ERROR 502)
        # and friends surface via the TranscriptError mapping.
        try:
            text = await asyncio.get_running_loop().run_in_executor(
                SUMMARIZE_EXECUTOR,
                contextvars.copy_context().run,
                summarize_mod.call_with_preset,
                provider, request.model, request.preset, request.text,
            )
        except TranscriptError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        return {"text": text}

    @app.get("/api/benchmarks")
    async def benchmarks_endpoint(difficulty: str | None = None):
        # Read-only dataset pick (design decision 1): a random entry of the
        # requested difficulty. Difficulty validation, file reading/parsing,
        # and selection all run in a worker thread (blocking I/O off the
        # event loop). The endpoint never touches the fetch chain or the
        # single-flight semaphore, and never creates or modifies a file.
        try:
            entry = await asyncio.to_thread(
                benchmark_dataset.select_entry, difficulty
            )
        except TranscriptError as exc:
            return JSONResponse(
                status_code=exc.status,
                content={"error": {"code": exc.code, "message": exc.message}},
            )
        return entry

    @app.get("/api/logs")
    async def log_stream_endpoint():
        # Server-sent events stream of the in-memory log bus (design 2-4).
        # Read-only: no filesystem work, and it never touches the fetch chain
        # or the single-flight semaphore.
        bus = logbus.DEFAULT_BUS

        async def event_stream():
            # Subscribe before snapshotting: an entry logged between the two
            # would otherwise be lost on the first connect.
            queue = bus.subscribe()
            try:
                for entry in bus.snapshot():
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                while True:
                    try:
                        entry = await asyncio.to_thread(
                            queue.get, timeout=LOG_POLL_TIMEOUT
                        )
                    except Empty:
                        continue
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            finally:
                bus.unsubscribe(queue)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Mounted last so the API routes above take precedence.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    applog.setup_logging()
    applog.install_excepthook()
    host = os.environ.get("HOST", "0.0.0.0")
    # App-wide connection backpressure: while 100 connections are in flight,
    # uvicorn itself rejects new ones with 503 (design D2).
    uvicorn.run(app, host=host, port=_listen_port(), log_level="warning",
                limit_concurrency=100)


if __name__ == "__main__":
    main()
