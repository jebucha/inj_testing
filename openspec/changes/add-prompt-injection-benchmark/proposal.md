# Proposal

## Why

This tool is a textbook **indirect prompt-injection** surface: an attacker-controlled
YouTube transcript is sent to an LLM behind a fixed summarization prompt, and the model's
output is displayed and persisted. But there is no way to *test* model resistance — you
cannot slip a payload into the transcript, run the same payload against several backends, or
measure whether the injection took. As an AI-security tool we want to benchmark how various
models behave under indirect injection (and, later, evaluate defenses), using a real
transcript as the carrier so the payload sits inside otherwise-legitimate content.

## What Changes

- A new **Injection** panel in the UI (toggle-gated): an attacker-payload field plus an
  insertion-point control (`prepend` / `middle` / `append`, default `append`). With the
  toggle off (or an empty payload) the displayed transcript is sent exactly as today.
- **Client-side splice** of transcript + payload into a single undifferentiated string
  before it reaches the LLM. The backend and model receive **no** separate injection field
  and **no** label marking the payload as an injection — preserving indirect-injection
  fidelity.
- A **benchmark run**: send the same spliced text to one or more configured
  provider/model combinations and collect a result per model.
- A **layered success oracle** per model: (1) a deterministic **canary** token the payload
  asks the model to emit (hit = output contains the canary); (2) an **LLM-as-judge** verdict
  (`resisted` / `partial` / `full`) plus a brief reason; (3) a **human** verdict control.
  A per-model **tally** reports canary hit-rate, judge compliance-rate, and the
  human-confirmed rate.
- A new backend endpoint that calls a configured provider/model with a **caller-selected
  system-prompt preset** and returns the model's output, persisting **no file**. v1 registers
  two presets: the existing summarization instruction (used as the delivery prompt) and a
  judge instruction (used by the oracle). Defense-prompt testing later is "add a defensive
  preset."
- Benchmark runs **neither create nor modify** saved `.txt` / `.summary` files (no library
  pollution across repeated runs).
- All injected payload, spliced text, model output, and judge output are inserted into the
  DOM as **plain text only** (the existing `textContent`-only discipline), never HTML.

## Capabilities

### New Capabilities
- `prompt-injection-benchmark`: a testing harness that splices attacker-authored payloads
  into a transcript, runs the result across multiple LLM backends, and measures injection
  success through a layered canary + judge + human oracle with a per-model tally.

### Modified Capabilities
<!-- None. The existing POST /api/summarize (and its persistence) is left unchanged; the
     injection/benchmark UI is additive and belongs to the new capability, and the only new
     server behavior is the non-persisting, preset-driven LLM endpoint, which is specified
     under the new capability rather than transcript-summarization. Judgment call noted for
     the record: the new Injection panel lands in the single-page UI governed by the
     `web-interface` capability (its "Result header layout" requirement covers the action
     toolbar the new controls join), but it is additive-only — no existing web-interface
     requirement's behavior changes — so it is specified under the new capability. -->

## Impact

- **Backend (new):** one preset-driven, non-persisting provider-call endpoint plus a small
  server-side system-prompt preset registry (summarize + judge). It reuses the already-generic
  `_call_chat_completions` dispatch, the existing provider config/validation, and the existing
  bounded `SUMMARIZE_EXECUTOR` concurrency cap, so it adds no new unbounded-LLM DoS surface.
- **Backend (reuse, unchanged):** `GET /api/providers` (model list), `POST /api/transcript`
  (real transcript carrier), and the existing `POST /api/summarize` (the normal Summarize /
  auto-summarize flow is untouched).
- **Frontend:** new injection panel, benchmark controls (model multi-select, judge picker),
  per-model results, and a tally table in `app/static/` (vanilla JS, no build step, no CDN).
- **Tests:** new backend API tests for the preset endpoint (validation order, no persistence,
  error mapping); new e2e tests for the panel, splice fidelity, multi-model run, oracle, and
  tally. No new runtime dependencies.
