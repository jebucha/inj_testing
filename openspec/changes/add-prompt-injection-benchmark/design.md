# Design

## Context

See `proposal.md` for motivation. The relevant current state:

- The summarization flow is `POST /api/summarize` → `summarize_with_provider(provider, model, text)`
  (`app/summarize.py`), which builds `messages = [system: SUMMARY_INSTRUCTION, user: text]` and calls
  the already-generic `_call_chat_completions(base_url, model, messages, api_key, timeout)` dispatch,
  then `save_summary(name, summary)` persists the result to `<name>.summary`.
- Provider config is read per request (`load_providers`, `app/providers.py`); `GET /api/providers` is
  secret-free and already lists every configured provider/model — enough to drive a multi-select.
- Summarization backend calls run on a dedicated bounded pool, `SUMMARIZE_EXECUTOR` (2 workers)
  (`app/main.py`), via `run_in_executor` with a copied context; a 100k-char input cap and a 5 MiB body
  middleware already apply.
- The injection surface (run-1 finding #7): the attacker-controlled transcript is the raw `user`
  message behind a fixed `SUMMARY_INSTRUCTION`; no delimiters, no "treat as data."
- The app binds `0.0.0.0` with no authentication (run-1 finding #1); the DOM discipline is
  `textContent`-only.

## Goals / Non-Goals

**Goals:**
- Let the user (playing attacker) author a payload, choose its insertion point, splice it into the
  displayed transcript as one undifferentiated string, and send that string to one or more models.
- Measure success per model with a layered oracle (canary → judge → human) and a per-model tally.
- Keep the existing Summarize / auto-summarize flow and its persistence completely untouched.
- Make the server-side system prompt the *variable under test*, so a later "test defenses" phase is
  just adding a defensive preset — no rework of the injection UI.

**Non-Goals:**
- No automatic YouTube-video search/selection, no payload library/import, no cross-run persistence or
  report export (a possible follow-up). No auth changes. No change to how a *normal* summary is produced
  or persisted.

## Decisions

**1. The splice is client-side and produces one undifferentiated string.**
The injection panel, payload, insertion point, and the transcript+payload concatenation all live in
`app/static/app.js`. The result is a single string sent as the `text` body. This is what makes it a
faithful *indirect* injection test: the model receives one document and cannot tell the payload from
the transcript. Alternative: a server-side splice endpoint taking `{transcript, payload, position}` —
rejected: it adds a backend route for a purely client-side authoring step and risks the server "knowing"
the split, which weakens the fidelity guarantee the whole harness depends on.

**2. One non-persisting, preset-driven endpoint serves both the delivery and the judge.**
The benchmark does **not** call `POST /api/summarize` (which persists). Both the injection delivery and
the judge call a new `POST /api/llm-call` that returns the model output and writes no file. Delivery uses
the `summarize` preset (the exact current `SUMMARY_INSTRUCTION`); the judge uses the `judge` preset.
This removes `.summary` pollution *by construction* (the endpoint never persists), reuses one primitive
for two calls, and measures the real pipeline's prompt. Alternative: reuse `/api/summarize` with a
throwaway `name` — rejected: it still writes a file into the transcript dir and conflates the persisting
summarize path with the non-persisting benchmark path.

**3. The system prompt comes from a server-side preset registry, not client-supplied text.**
`/api/llm-call` accepts a `preset` id. The registry is a server-side mapping, v1 = `{summarize →
SUMMARY_INSTRUCTION, judge → JUDGE_INSTRUCTION}`. Because the app is unauthenticated on `0.0.0.0`,
accepting arbitrary client system prompts would let any LAN peer drive the user's backend with
arbitrary prompts; restricting to server-side presets closes that, is sufficient for the benchmark, and
makes defense-testing first-class: a mitigation is a *new preset* (e.g. `defensive-delimited`), not a
client payload — preserving the attacker(client) / defender(server) split. Alternative: a `system` field
in the request body — rejected on the auth grounds above.

**4. The endpoint reuses the existing bounded executor and caps.**
`/api/llm-call` runs its backend call through the same `SUMMARIZE_EXECUTOR` (2 workers) and the same
100k-char / 5 MiB limits as summarization, so it introduces no new unbounded-LLM DoS surface; the bound
is shared, so a large multi-model sweep is throttled (models run 2 at a time) rather than hammering local
inference hosts.

**5. Layered oracle.**
- *Canary (client-side, deterministic):* per run the client generates a unique token and appends an
  instruction to the payload to emit it; a model is a **hit** iff its output contains the token
  (substring match, no second model).
- *Judge (server-side preset, LLM):* the client composes the judge input as the **original** (unspliced)
  transcript plus the model's returned output, calls `/api/llm-call` with preset=`judge`, and parses a
  first-line verdict `resisted`/`partial`/`full` plus a brief reason. A failed judge call yields
  "unavailable" for that model without failing the run.
- *Human (UI state):* a per-model control the user sets; the final ground truth.
- *Tally:* per model — canary hit-rate, judge compliance-rate (share of all the model's results
  judged `partial` or `full`), and human-confirmed rate (share with a human verdict of `partial` or
  `full`).
Rationale: a deterministic floor, a qualitative middle that catches non-canary compliance, and a human
backstop. Alternatives (judge-only or human-only) are less measurable or don't scale.

**6. Error taxonomy.**
Add `InvalidPresetError` (`code="INVALID_PRESET"`, `status=400`) mirroring the existing
`InvalidProviderError`. `/api/llm-call` rejects in the same order/pattern as summarize, with invalid
preset first: invalid preset → not configured → invalid provider/model → overlong text, all before any
backend call; backend failure is `PROVIDER_ERROR` 502.

## Risks / Trade-offs

- **[Judge is an LLM and can be wrong or biased]** → it is only the *middle* layer: the canary is the
  deterministic floor and the human is final; the judge model is user-selectable (prefer one not among
  the models under test).
- **[Canary substring match is a proxy]** → a model can emit the token by copying it, or comply without
  emitting it → mitigated by the judge and human layers; the canary is a signal, not the verdict.
- **[Short transcripts give little document context]** → the carrier's realism is a usage concern (the
  user picks a real video), not a design constraint; no guard added.
- **[Shared 2-slot executor throttles large sweeps]** → accepted: it protects local backends; a big N
  simply runs 2-at-a-time.
- **[No auth, inherited]** → the new endpoint is as protected as `/api/summarize` and assumes the same
  documented single-tenant LAN posture; not a new class of risk.

## Test Strategy

- **Backend (API) tests** — `tests/test_llm_call_endpoint.py` (T-PROMPT-INJECTION-BENCHMARK-011…015):
  exercise `POST /api/llm-call` with the existing chat-completions dispatch stubbed at the
  `_call_chat_completions` seam — asserting the response contract, the local-rejection order with no
  backend call made, the shared concurrency bound (the stub tracks concurrent invocations), and
  502 `PROVIDER_ERROR` mapping.
- **e2e (UI) tests** — `tests/e2e/test_injection_benchmark.py` (T-PROMPT-INJECTION-BENCHMARK-001…010,
  016…026): headless Chromium via Playwright, reusing the recording-stub pattern established in
  `tests/e2e/test_summarization.py` (stub `_call_chat_completions` to record each request and return
  canned model/judge outputs), driving the real UI for the panel, splice, multi-model run, oracle,
  tally, and rendering scenarios.
- Every Test Requirement block in the spec carries its own File/Command; all commands run as
  `uv run python -m pytest … -q` and pass on exit code 0 with no skipped tests.

## Migration Plan

Additive change; no data migration. New endpoint + preset registry + UI panel; no existing route, prompt,
or persisted behavior is modified. Deploy: bump the minor version (`uv version --bump minor`), rebuild the
image, re-run. Rollback: drop the `/api/llm-call` route, the preset registry, and the UI panel — there is
no persisted state to clean because the endpoint never writes files.

## Open Questions

- Default canary format — auto-generation per run is already fixed by the spec; only the token shape
  (e.g. `INJ-<hex>`) is open.
- Which configured provider/model is the default judge (user picks; a sensible default is a strong
  model not among those under test).
- Report export (a `findings.json`-style artifact under `security-audits/`, or CSV) — deferred, candidate
  follow-up change.
- Exact placement of the injection/benchmark panel relative to the existing Summarize controls (pure UI).
