# `app/summarize.py` — summarization backend

## Purpose

The summarization feature's backend: an OpenAI-compatible
chat-completions call to a configured provider/model, plus save/read of the
result as a `.summary` file next to the transcript. It also hosts the
injection benchmark's two server-side pieces — the system-prompt preset
registry and the non-persisting `call_with_preset` — since the registry's
`summarize` preset *is* the fixed `SUMMARY_INSTRUCTION` and the call
reuses the same dispatch. The HTTP dispatch lives in the module-level
`_call_chat_completions` so the e2e harness can replace that function with
a recording stub while `summarize_with_provider` keeps running for real.

## Public surface

- `summarize_with_provider(provider, model, text, timeout=None) -> str` —
  the synchronous call; meant to run in a worker thread (the dedicated
  summarize executor in `main.py`).
- `save_summary(name, summary) -> None` — best-effort write to
  `<name>.summary`.
- `read_summary(name) -> tuple[bool, str]` — contained read of
  `<name>.summary`.
- `summary_timeout() -> float` — `SUMMARY_TIMEOUT` (default 120 s) read at
  call time; non-numeric values fall back to the default.
- `call_with_preset(provider, model, preset_id, text, timeout=None) -> str`
  — the injection benchmark's non-persisting call: builds
  `[system: <preset text>, user: text]`, reuses the dispatch, returns the
  model's output, and never writes a file.
- `resolve_preset(preset_id) -> str` — the preset registry resolver;
  raises `InvalidPresetError` (400 `INVALID_PRESET`) for an unknown id.
- `PRESETS` — the server-side system-prompt preset registry:
  `summarize` → `SUMMARY_INSTRUCTION`, `judge` → `JUDGE_INSTRUCTION`.
- `ProviderCallError` — a failed backend call with machine-readable
  `reason` (`unreachable`, `timeout`, `http_error`, `malformed_response`,
  `empty_response`) and a safe, app-constructed `detail`.
- Constants: `MAX_OUTPUT_TOKENS` (16384), `MAX_INPUT_CHARS` (100,000),
  `DEFAULT_SUMMARY_TIMEOUT` (120.0), `SUMMARY_INSTRUCTION` (the fixed,
  server-side summarization prompt), `JUDGE_INSTRUCTION` (the fixed,
  server-side judge prompt: first line exactly `resisted` / `partial` /
  `full`, then a brief reason), `SUMMARY_EXTENSION` (`.summary`).

## Invariants

- **No FastAPI imports.** The call is a plain synchronous function and the
  save/read helpers are testable directly against `tmp_path`.
- **Plain HTTP via `requests`, per-call `requests.post`** — no shared
  session (thread-safe without locking), no `openai` SDK. The bearer token
  is attached only when the provider defines an `apiKey`.
- **Exactly one structured event per call:** `summary_completed` (info) or
  `summary_failed` (error) — and those events (and every log) never carry
  transcript/summary content, config file contents, or keys. Exception
  details are exception *type names* — `str()` of `requests` exceptions
  embeds the base URL, which must stay out of the logs.
- **Empty content is a failure.** A 2xx whose `choices[0].message.content`
  is empty or whitespace-only raises `empty_response` — a backend that
  "succeeds" with no content (thinking models exhausting the output budget
  in reasoning) is a failed summarization, not a successful one.
- **Caps:** input over 100,000 chars is rejected upstream
  (`INPUT_TOO_LONG`); output is bounded server-side at `max_tokens=16384`
  — sized so reasoning plus a full summary both fit.
- **System prompts come only from the server-side preset registry.**
  `call_with_preset` resolves the system prompt via `resolve_preset`
  (`summarize` / `judge` in v1); the benchmark endpoint accepts a preset
  *id*, never client-supplied prompt text — with the app unauthenticated
  on `0.0.0.0`, that is the line that keeps arbitrary LAN peers from
  driving the configured backends with arbitrary prompts. Testing a
  defense later is a matter of registering a new defensive preset.
- **`call_with_preset` never persists.** It is the injection
  benchmark's delivery *and* judge primitive (one primitive, two
  callers): the route it serves writes no file, so benchmark runs
  cannot pollute the transcript directory by construction.
- **Save is best-effort and never raises;** a failure is only the
  `summary_save_failed` event. Overwriting on re-summarize is intended.
- **Read follows the read-side discipline** of `library.read_transcript`:
  structural reject, resolve-and-contain, regular-file check. The `.summary`
  extension keeps summary files out of the `.txt` saved-transcript list.

## Log events emitted

- `summary_completed` (info): `provider`, `model`, `duration_ms`,
  `chars_in`, `chars_out`.
- `summary_failed` (error): `provider`, `model`, `duration_ms`, `reason`,
  `detail`.
- `summary_save_failed` (error): `name`, `path`, `reason`, `detail`.
- `llm_call_completed` (info): `provider`, `model`, `preset`,
  `duration_ms`, `chars_in`, `chars_out`.
- `llm_call_failed` (error): `provider`, `model`, `preset`, `duration_ms`,
  `reason`, `detail`.

## Error codes raised/handled

Raises `ProviderError` (502 `PROVIDER_ERROR`, message includes the
machine-readable reason) when a backend call fails and
`InvalidPresetError` (400 `INVALID_PRESET`) for an unknown preset id;
handles `ProviderCallError` internally.

## Design decisions

Resolved from `add-transcript-summary`:

- **decision 1** — plain HTTP via `requests`, no SDK; the empty-content
  rule.
- **decision 2** — the providers/summarize module split, FastAPI-free.
- **decision 6** — summary files: `<name>.summary`, non-`.txt`, best-effort
  save, contained read.
- **decision 10** — timeouts and caps, including the "Output cap sizing"
  story (an observed thinking model produced an empty summary at a 600-token
  cap; 16384 was chosen for headroom).
- **decision 11** — the e2e seam: HTTP dispatch isolated in the module-level
  `_call_chat_completions` so the log emission still runs under stubs.
- **decision 13** — the logging fields and the never-log-secrets rule.

From `add-prompt-injection-benchmark`:

- **decision 2** — the non-persisting preset-driven endpoint: the
  benchmark does not call `POST /api/summarize` (which persists);
  delivery (`summarize` preset) and judge (`judge` preset) both call
  `POST /api/llm-call` over `call_with_preset`, so `.summary` pollution
  is impossible by construction.
- **decision 3** — the system prompt is a server-side preset id, not
  client text (the unauthenticated-LAN rationale).
- **decision 5** — the layered oracle; this module only supplies the
  judge preset's prompt shape (first line `resisted` / `partial` /
  `full`, then a brief reason).

## Cross-links

- [`providers.py`](providers.html) — the config that supplies the `Provider`
- [`main.py`](main.html) — the bounded executor, the validation order, and
  the `POST /api/llm-call` route over `call_with_preset`
- [`library.py`](library.html) — the read-side discipline `read_summary` mirrors
- [`persist.py`](persist.html) — the sibling writer in the same directory
