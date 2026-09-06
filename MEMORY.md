# MEMORY.md — Rupantar project memory

> **Read this file at the start of every session, before touching any code.**
> **Update it at the end of every session, before you stop.**
> Keep it under 300 lines. When a section grows past its cap, compress the oldest entries into one summary line.
> This file is append-and-compress, not append-forever. Stale detail is worse than no detail.

---

## 1. Project state

| Field | Value |
|---|---|
| Current phase | **3 — All artefact agents (not started)** |
| Last session | 2026-09-06 — grammar-cost investigation (Phase 2 shipped prior) |
| Last commit | `phase-2: text generation path` |
| Blocking Phase 3 | human call on schema-enforcement mechanism — see §7 |
| `make check` status | **green** (ruff + format 53 files + mypy 25 files + 99 unit + 8 inv / 3 inv skeleton; slow lane `pytest -m slow` → 2 pass) |
| Active hardware profile | `laptop-16gb` |
| Models present on disk | **brain** only — `models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2.5 GB, sha `3605803b…`); vlm/asr/tts absent |
| Python | 3.11.15, uv-managed, `.venv/`, pinned in `.python-version` |

---

## 2. Phase ledger

Mark each phase `TODO` / `IN PROGRESS` / `DONE (date)`. Add one line on what actually shipped.

| Phase | Status | Notes |
|---|---|---|
| 0 — Scaffold and contracts | **DONE (2026-09-06)** | Package, frozen `core/schemas.py` + `core/artefacts.py` (7 artefacts, all validators), async `core/store.py`, minimal `core/config.py`, `core/errors.py`, Typer CLI stubs (4 commands), 8 inv skip-skeletons, fixtures (2 articles, image, 30s clip, 7 artefact JSONs). `make check` green. |
| 1 — Model Manager | **DONE (2026-09-06)** | `models/` package: `runtime_base.py` (ABC + SIGTERM→SIGKILL `terminate_process`, `wait_healthy`, `read_rss_bytes` via `ps`), `_ports.py`, `runtime_stub.py` (child `python -m` stdlib `http.server`, zero model files), `registry.py` (skips file/SHA for `runtime == "stub"`; real missing file → `ModelFileMissingError` naming `scripts/fetch_models.sh`), `_support.py` (Lease/Event/state), `manager.py` (async `acquire()` CM + `obtain/release`, refcount, single `asyncio.Condition` serialises load/evict/reap, `max_heavy_resident` eviction waits for real process exit, LRU + idle-TTL reaper, external-death respawn, `status()`), `runtime_llama.py` (untested vs real binary, `@pytest.mark.slow`). Events → new `events` table in `store.py`. `models status` CLI (not the API route — see Deviations). INV-1/2/7/8 tests real and green. |
| 2 — Text generation path | **DONE (2026-09-06)** | `models/client.py` (async **httpx** `/v1/chat/completions`, GBNF `grammar` passthrough, SSE `stream()`, retry-once on conn reset, `ModelClientError` on 4xx/5xx). `agents/grammar.py` (Pydantic JSON-Schema → GBNF: object/array w/ min-maxItems/string/int/bool, `enum`+`const` → quoted-literal alternation, `$ref`/`$defs`). `agents/base.py` (`ArtefactAgent`; `SHARED_PREAMBLE`+dossier in the **system** turn, agent/param text in the **user** turn — prefix-cache design; `string.Template` params; validate → retry-once appending the error as new turns → `AgentError`). `agents/loader.py` (dotted `module:Class` schema import). `orchestrator/runner.py` `run_single` (minimal 1-`TextBlock` dossier, `acquire`→client→agent→write `data/outputs/<job_id>/<type>.json`; `AgentError` → FAILED job, never raises out; no manifest — Phase 4). `configs/agents/executive_summary.yaml`. Real `cli transform --text FILE --output … [--profile] [--stream/--no-stream] [--out-dir]`. INV-6 real. `runtime_stub.py` now OpenAI-compatible (canned via `RUPANTAR_STUB_COMPLETION`). Real path measured: exec summary in ~53 s on laptop-16gb (DoD < 90 s). |
| 3 — All artefact agents | TODO | Next. `client.py`/`grammar.py`/`base.py`/`loader.py` are done and general. Add the 6 remaining `configs/agents/*.yaml` + prompts (schemas already frozen in `core/artefacts.py`), `orchestrator/planner.py`, `orchestrator/scheduler.py` (group by `model_key`), `api/` package (`app.py` + routes `transforms`/`jobs`/`models`/`health`) — FastAPI + uvicorn land here, and INV-1's dynamic "API process never loads a model" check. |
| 4 — Renderers | TODO | |
| 5 — Parivartan converters | TODO | Adds fixtures: messy CSV, Sigma rule, CEF log. |
| 6 — Multimodal ingestion | TODO | Adds fixture: advisory PDF. en-only ASR/TTS → `language_limitation` manifest warning. |
| 7 — Video assembly | TODO | |
| 8 — Air-gap, audit, selfcheck | TODO | selfcheck asserts `sys.version_info[:2] == (3, 11)`. |
| 9 — Frontend | DEFERRED | Do not start without a PLAN.md update |

---

## 3. Invariant status

| ID | Invariant | Test | Status |
|---|---|---|---|
| INV-1 | No in-process model loads | `tests/inv/test_no_inprocess_models.py` | **PASS** — AST scan: no module-scope import of torch/transformers/llama_cpp/ctranslate2/faster_whisper/onnxruntime under `src/`. Dynamic (API-process) check deferred until `api/` exists. |
| INV-2 | ≤1 heavy model resident | `tests/inv/test_single_resident.py` | **PASS** — event-stream replay over brain→vlm→brain swaps (stub runtime) proves never two heavy READY; + live `os.kill(pid,0)` probes prove old process dead before new alive. |
| INV-3 | Lazy heavy imports | `tests/inv/test_lazy_imports.py` | skip-skeleton (phase 4) |
| INV-4 | No non-loopback egress | `tests/inv/test_no_egress.py` | skip-skeleton (phase 8); grep clean |
| INV-5 | Provenance manifest per artefact | `tests/inv/test_provenance.py` | skip-skeleton (phase 4) |
| INV-6 | Schema-validated model output | `tests/inv/test_validated_outputs.py` | **PASS** — valid stub completion → `ExecutiveSummary` instance; invalid JSON → `AgentError`, never returned unvalidated. `ArtefactAgent.run` gates every return on `schema.model_validate`. |
| INV-7 | Single model-start entry point | `tests/inv/test_single_entry_point.py` | **PASS** — regex scan: `subprocess`/`Popen`/`os.spawn`/`create_subprocess_*`/`multiprocessing` only in `models/runtime_*.py`; `ModelManager.acquire`/`obtain` present. |
| INV-8 | Unload = process kill | `tests/inv/test_unload_kills_process.py` | **PASS** — acquire stub, `os.kill(pid,0)` ok, evict, poll to `ProcessLookupError`; `EVICT_DONE` event carries the dead pid. |

INV-1/2/6/7/8 are real assertions run in `make check`. INV-3/4/5 are still `pytest.skip("implemented in phase N")` skeletons (green as skipped).

---

## 4. Frozen decisions

Things that are settled. Do not relitigate these without an explicit instruction from the user.

- Models run as **child processes** (`llama-server`), never in-process with torch/transformers. Unload = SIGTERM. This is the core of the design.
- **One heavy model resident at a time**, enforced by `ModelManager` with refcounting + LRU + idle TTL.
- "Agents" are **prompt template + Pydantic schema + GBNF grammar + validator** over the single loaded brain. Not separate fine-tuned models.
- Scheduler groups jobs by required model so a multi-artefact request causes **one swap per modality**, not per artefact.
- Dropped from scope: knowledge graph, Neo4j, vector RAG, embeddings, re-ranker, ChromaDB, video RAG, digital twin, fine-tuning.
- Frontend deferred to Phase 9. API + Typer CLI are the interface until then.
- Deterministic work (renderers, converters) has **zero model dependency** and must never block on the Model Manager.
- Air-gap is proven, not claimed: offline env vars, loopback-only assertion, egress monitor, selfcheck report.
- **Two entities:** `Transform` = one operator request (batch); `Job` = one artefact. `Job.transform_id` links them. Routes: `POST /transforms`, `GET /transforms/{id}`, `GET /transforms/{id}/artefacts`, `GET /jobs/{id}`.
- **`core/artefacts.py` and `core/schemas.py` are FROZEN** as of end-of-Phase-0. `docs/SCHEMAS.md` is their locked spec. Changing either requires a Deviations entry.
- Python **3.11 exactly** — vendored wheels (ctranslate2, pyarrow, onnxruntime) target 3.11; other versions are a build failure.
- Artefact list items carry **no `index` field** — array order is the order; renderers use `enumerate()`.
- Enums are plain `enum.Enum` (not `StrEnum`/`str,Enum`) — see Deviations. Phase-0 Deviation-1 (GBNF string identity) is **resolved**: Pydantic v2 `model_json_schema()` still emits `type: string` beside `enum`/`const`, and `agents/grammar.py` keys off `enum`/`const` regardless.
- HTTP client is **httpx** (async). Chosen Phase 2; FastAPI pulls it in at Phase 3 anyway. Imported at module top only in `models/client.py`, like `aiosqlite` in `store.py` — not an INV-3 concern.
- **Agent prompt layout:** identical `SHARED_PREAMBLE` + source dossier go in the **system** turn; all agent- and param-specific text goes last, in the **user** turn. This keeps the long dossier as a byte-identical prefix so llama-server prefix caching spares agents 2–7 the re-eval. Retry turns are appended, never spliced into the first user message.

---

## 5. Deviations from PLAN.md

Anything you did differently from the plan, and why. One line each. Empty is fine.

- **Enums are plain `enum.Enum`, not `str, Enum` / `StrEnum`.** `StrEnum` trips ruff `UP042`; `str, Enum` + `SlideLayout.title` shadows `str.title` under mypy. Pydantic still serialises `.value` in JSON mode; `store.py` uses explicit `.value`. Revisit if Phase 2 GBNF generation needs string-enum identity.
- **Added `tests/unit/test_config.py`** (not in the Phase 0 file list). Leaving `core/config.py` untested contradicted the test-alongside-code rule.
- **Artefact example fixtures were generated by serialising hand-authored model instances** (scratchpad `gen_fixtures.py`, not in repo), not typed as raw JSON by hand. Content is hand-written; only serialisation is mechanical. If `core/artefacts.py` were ever unfrozen and changed, regenerate the 7 fixtures.
- `Advisory` round-trip requires `model_dump(mode="json", by_alias=True)` to emit the `type` key (ruling G alias). The other six artefacts are alias-free.
- **Phase 1: `api/routes/models.py` not built.** The Phase 1 build list names it (`GET /models`, `GET /models/status`, `POST /models/{key}/unload`), but there is no `api/` package and FastAPI is not a Phase 1 dependency. Implemented `models status` in `cli/main.py` instead. The route module lands with the rest of `api/` (Phase 3). A fresh CLI process always shows `NOT_LOADED` — the manager lives in the server/runner process, not the CLI.
- **Phase 1: events go to a new `events` table in `core/store.py`** (`id/ts/kind/model_key/pid/detail_json` + `idx_events_kind`, async `append_event`/`list_events`). `store.py` is not frozen. The `ModelManager` event sink is injectable (defaults to in-memory; Store-backed sink available) and events are also kept in-process as `manager.events`.
- **Phase 1: `manager.py` split** — support types/helpers (`Lease`, `Event`, `ModelState`, `store_event_sink`, `default_runtime_factory`) live in `models/_support.py` to keep `manager.py` under 400 lines (337 now). Re-exported from `manager` via `__all__`.
- **Phase 1: manager serialises all load/evict/reap through one `asyncio.Condition`.** A load holds the lock across `runtime.start()`. Intentional — single heavy residency means concurrent heavy loads are never wanted. `status()` is lock-free.
- **Phase 1: new additive `core/errors.py` classes** — `ModelError`, `UnknownModelError`, `ModelFileMissingError` (carries `key`/`path`), `RuntimeStartError`, `NoFreePortError`, `AcquireTimeoutError`. `errors.py` is not a frozen contract.
- **Phase 1: INV-1 test implemented as a static import scan now** (not the phase it was pencilled for). The dynamic "API process never loads a model" check waits for `api/`.
- **Phase 2: Deviation-1 (plain `enum.Enum` → GBNF) resolved with no contract change.** `model_json_schema()` emits `{"enum": [...], "type": "string"}` for a string-valued plain Enum and `{"const": "...", "type": "string"}` for a `Literal`. `agents/grammar.py` checks `enum`/`const` before `type` and emits an alternation of exact double-quoted JSON literals, so identity holds regardless.
- **Phase 2: agent validation-retry appends new `assistant`+`user` turns** instead of editing the first user message — keeps the dossier prefix byte-identical for llama-server prefix caching.
- **Phase 2: `runtime_stub.py` extended to speak `/v1/chat/completions`** (OpenAI envelope; canned content from `RUPANTAR_STUB_COMPLETION` = literal or `@file`, else echoes the last user message; SSE frames on `stream`). Not frozen. `tests/unit/test_runtime_stub.py` updated to the new POST shape.
- **Phase 2: real llama-server boot test moved** from `tests/unit/test_runtime_llama.py` (where it was an unconditional `pytest.skip` lie) to `tests/integration/test_runtime_llama_real.py` (`@pytest.mark.slow` + `skipif` on binary/GGUF). Keeps `make check` model-free; it now boots a real server, health-checks, SIGTERMs, asserts the pid is gone.
- **Phase 2: `transform`/`run_single` use `Registry.from_config(verify=False)`** to skip the 2.5 GB startup SHA-256; `llama-server` still fails loudly if the GGUF is missing.
- **Phase 2: `--n-gpu-layers` left at 0 for `laptop-16gb`.** No-op on Apple Silicon (llama.cpp uses Metal by default; 36.6 vs 36.8 tok/s). `titan-24gb` keeps 99 for Linux/CUDA. `models.yaml brain.notes` records this.

---

## 6. Blockers

Things that are broken or unfinished and need attention. Include the file and the symptom.

- **RESOLVED (Phase 2):** `runtime_llama.py` real path is now verified — `tests/integration/test_runtime_llama_real.py` (slow) boots a real `llama-server` on the brain GGUF, health-checks, SIGTERMs, and asserts the pid is gone. Real end-to-end text path also exercised by `tests/integration/test_text_path_real.py`.
- `configs/models.yaml` `laptop-16gb`: **brain is present**; `vlm`, `asr`, `tts` files are still absent, so `Registry.from_config(verify=True)` on the full profile still raises `ModelFileMissingError` (on `vlm`). `models status`, `transform`, and `run_single` use `verify=False`. Fetch vlm/asr/tts before Phase 6.
- `make check-all` runs `pytest tests/integration` with **no `-m "not slow"` filter**, so on a machine with the brain GGUF it executes the two real-model integration tests (~55 s total). `make check` (the phase gate) stays fast and model-free. See Open Questions.
- `requirements-lock.txt` is still an empty placeholder. `httpx` (+ `anyio`, `certifi`, `h11`, `httpcore`, `idna`, `sniffio`) must be captured by `scripts/vendor_wheels.sh` before air-gapping.

---

## 7. Open questions for the human

Decisions you could not make on your own. Do not guess — list them here and continue with the safest default.

- Exact GGUF builds and quantisation for `brain` and `vlm` on the demo laptop, **and the laptop's OS/arch** (needed for `requirements-lock.txt` / wheel vendoring — the dev machine is macOS arm64, the demo laptop may not be). Needs a one-time online fetch + benchmark.
- Which three cyber formats matter most to the evaluators for Parivartan. Current default: IOC CSV ↔ STIX 2.1, Sigma YAML → JSON, CEF/syslog → JSONL.
- Whether the recorded demo video uses the `laptop-16gb` or `titan-24gb` profile.
- `GenerationParams.language`: field kept, brain honours it best-effort; ASR/TTS are en-only and emit a `language_limitation` manifest warning (Phase 6). Tested values `en`, `hi`; others accepted as best-effort. Confirm `hi` is actually a demo requirement.
- Should `make check-all` deselect `-m slow`? It currently runs the real-model integration tests when models are on disk. Fixing it touches the `Makefile` **and** `PLAN.md` §7 (the single shared `make check` / `check-all` definition) and `CLAUDE.md`. Left as-is for now; `make check` itself is unaffected.
- **Schema-enforcement mechanism for the agents (GBNF vs `response_format:json_schema` vs none).** Investigation 2026-09-06 (session log §9) found the mechanism has ~no measurable cost or benefit here: all four modes generate at the same tok/s and unconstrained had 0/16 validation failures on `ExecutiveSummary`. The user's stated switch trigger ("materially faster") is not met, so on that rule GBNF stays. Open recommendation the other way: adopt native `response_format:json_schema` and delete `agents/grammar.py` (+ its test) — speed-neutral, a stronger structural guarantee than our converter, and ~150 fewer lines to extend/debug across the 6 nested schemas in Phase 3. **Awaiting a human call before Phase 3.**

---

## 8. Environment facts learned

Measured, not assumed. Update whenever you measure something new.

| Fact | Value | Measured on |
|---|---|---|
| Dev machine | macOS 15.3 (Darwin 25.3), Apple Silicon, 16 GB RAM — matches target profile | 2026-09-06 |
| Python | 3.11.15 (uv-managed), `.venv/` | 2026-09-06 |
| `uv` version | 0.11.29 | 2026-09-06 |
| `ffmpeg` version | 8.1.2 (`/opt/homebrew/bin/ffmpeg`) | 2026-09-06 |
| `llama-server` on PATH | **present** — v0.4.0 build 10809 (AppleClang, Darwin arm64, Metal), `/opt/homebrew/bin/llama-server` | 2026-09-06 |
| `piper` on PATH | **absent** — needed Phase 7 | 2026-09-06 |
| `git` version | 2.51.2 | 2026-09-06 |
| `asyncio.Condition()` outside a running loop | constructs fine on 3.11 (used in sync CLI path) | 2026-09-06 |
| Stub runtime child | `python -m rupantar.models.runtime_stub --port N`, stdlib `http.server`, real PID, SIGKILL grace 3s | 2026-09-06 |
| Phase 1 test suite | no stray `runtime_stub`/`llama-server` procs after run; ports 8100–8199 clean | 2026-09-06 |
| Free RAM | ~1 GB free+inactive under load (not a clean idle measure) | 2026-09-06 |
| brain GGUF | `models/brain/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2 497 281 120 B, sha256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597` | 2026-09-06 |
| brain llama-server boot → healthy | ~7.5 s first, ~4.0 s warm (GGUF page-cache hot; no true cold-disk figure — `purge` needs sudo) | 2026-09-06 |
| brain prompt eval | ~40 tok/s (752-tok dossier prompt); with `cache_prompt` a repeat prompt is ~0 | 2026-09-06 |
| brain generation — **constraint mechanism is NOT the cost** | GBNF, `response_format:json_object`, `response_format:json_schema`, and *no constraint* all measured **within noise of each other** (see grammar-investigation block in §9). Interleaved: 6.9 / 6.9 / 6.9 tok/s. First (staggered) run: 6.6 / 7.7 / 7.8 / 7.2. GBNF is at most ~10 % slower; json_schema == unconstrained. | 2026-09-06 |
| brain generation, absolute tok/s | **swings 2–3× with machine load** — 17 tok/s (single gen, quieter moment) down to ~7 tok/s (sustained, dev box running node/vite servers + a 54 %-CPU `python@3.14`). `llama-bench` (synthetic, tiny prompt) ~37 tok/s. **Re-measure on the real demo hardware, quiet.** | 2026-09-06 |
| `ExecutiveSummary` JSON validity, temp 0.3 | **0 failures in 32 runs** across all four constraint modes incl. *unconstrained* — Qwen3-4B-2507 emits schema-valid JSON on its own for this schema. Harder schemas (Advisory, Presentation, VideoPackage) untested. | 2026-09-06 |
| One `executive_summary` end-to-end (CLI, laptop-16gb) | ~53 s wall when measured 2026-09-06 morning; ~70 s under later dev-box load. DoD is < 90 s. | 2026-09-06 |
| `--n-gpu-layers 99` vs `0`, Apple Silicon | no measurable difference — llama.cpp uses Metal by default. Flag kept only for titan-24gb / Linux-CUDA. | 2026-09-06 |
| llama-server prefix caching | per-slot; `cache_prompt: true` reuses the longest common token prefix across requests to the same slot. Agents put the identical dossier first so agents 2–7 skip re-evaluating it. | 2026-09-06 |
| Peak RSS, full multimodal run | unknown | — |

---

## 9. Session log

Newest first. One block per session. Keep the last 8; compress older ones into a single summary line.

### Session template — copy this
```
### YYYY-MM-DD — <phase> — <one-line outcome>
Did:
-
Verified:
- command → result
Changed in this file:
-
Next session should start with:
-
```

### 2026-09-06 — Investigation — GBNF sampling cost (pre-Phase-3)
Premise to test: "GBNF is costing >half our throughput (37→17 tok/s), ×7 in Phase 3."
Method: `executive_summary` agent, `ai_policy_brief.md`, one warm llama-server, raw httpx for full `timings`. Two runs: (1) 4 modes × 8 seeds staggered; (2) cold single-shot + 4 interleaved rounds × 3 modes. Each output run through `ExecutiveSummary.model_validate`. Scripts in scratchpad (not committed).
Findings:
- **The premise is wrong.** GBNF / `response_format:json_object` / `response_format:json_schema` / no-constraint all generate at the same tok/s. Interleaved: 6.9/6.9/6.9. Staggered: 6.6/7.7/7.8/7.2 (GBNF ran first/coolest and was still slowest → its ~10 % gap is real but tiny). `json_schema` output was **token-identical** to unconstrained for every seed — the constraint never fires.
- The 37→17→7 drop is **context size + sustained load + a busy dev box** (node/vite servers, a 54 %-CPU `python@3.14`), not grammar. Absolute tok/s here is unreliable; must be re-measured on quiet demo hardware.
- **0 validation failures in 32 runs**, unconstrained included, for `ExecutiveSummary`. Retry-once path would rarely fire for this schema.
- Generated GBNF for `ExecutiveSummary` inspected: 11 rules, 1079 chars, canonical JSON `string` rule, no unbounded-alternation traps. Our GBNF does **not** encode the Pydantic count validators (`key_points` 3–6 etc.) — neither would `json_schema` as generated from the frozen models (bounds live in `field_validator`s, not `Field(...)`).
- Noted but not changed: `agents/base.py` calls `gbnf_for(self.schema)` once per `run()` (per artefact), not cached on the agent. Cheap (~1 ms) but should be memoised whichever mechanism wins.
Decision: **deferred to the human** — speed says "keep GBNF", maintenance/robustness says "switch to `response_format:json_schema` + delete `grammar.py`". No code changed. See §7.
Also did: fixed the stale `sample_article.txt` → `--text tests/fixtures/articles/ai_policy_brief.md` in `PLAN.md` §8 demo path.
Next: get the human's call on the mechanism, then start Phase 3.

### 2026-09-06 — Phase 2 — Text generation path shipped, INV-6 real, real brain measured
Did:
- Recorded the two benchmark notes from the human (`--n-gpu-layers` no-op on Apple Silicon; llama-server prefix caching → dossier-first prompt design).
- Repointed `configs/models.yaml` `laptop-16gb.brain` at the real GGUF (`Qwen3-4B-Instruct-2507-Q4_K_M.gguf`), added `sha256:` + real `approx_bytes`; updated `tests/unit/test_registry.py` for the new filename.
- Chose **httpx** as the HTTP client; added to `requirements.txt` + `pyproject.toml`; installed in `.venv` (0.28.1).
- Builder subagent built Phase 2: `models/client.py`, `agents/{grammar,base,loader}.py`, `orchestrator/runner.py`, `configs/agents/executive_summary.yaml`, real `cli transform`, OpenAI-compatible `runtime_stub.py`, `core/errors.py` +`ModelClientError`/`AgentError`, INV-6 made a real assertion.
- Moved the real llama-server boot test out of `tests/unit/` (was a lying unconditional skip) into `tests/integration/test_runtime_llama_real.py` (slow) — now a genuine boot→health→SIGTERM→pid-gone assertion. Keeps `make check` model-free.
- Ran builder → verifier (PASS w/ warnings) → arch-guard (CLEAN). Ran a real-brain benchmark + timed CLI run.
Verified:
- `make check` → ruff ✓, format ✓ (53 files), mypy ✓ (25 files), `pytest tests/unit tests/inv` → 107 passed / 3 inv skeleton, model-free, 15.9 s
- Phase 2 verify `pytest tests/integration/test_text_path.py -q` → 2 passed (stub, zero model files)
- `pytest -m slow -q` → 2 passed / 112 deselected, 52 s (real llama boot + real exec summary); no stray `llama-server`/`runtime_stub` procs
- `transform --text tests/fixtures/articles/ai_policy_brief.md --output executive_summary` → 52.7 s wall, valid `ExecutiveSummary` JSON written to `data/outputs/<job_id>/`
Changed in this file:
- §1 phase→3, commit, check counts, brain on disk. §2 Phase 2 → DONE + Phase 3 note. §3 INV-6 → PASS. §4 +httpx / prompt-layout / Deviation-1-resolved decisions. §5 +7 Phase-2 deviations. §6 rewrote (llama real path resolved; brain present / vlm-asr-tts absent; check-all slow note; lock file). §7 +2 open questions. §8 llama-server present + 8 measured rows. §9 this block. §10 httpx.
Next session should start with:
- Phase 3 — All artefact agents. `client.py`/`grammar.py`/`base.py`/`loader.py` already general; add the 6 remaining `configs/agents/*.yaml` + prompts, `orchestrator/{planner,scheduler}.py`, and the `api/` package (FastAPI + uvicorn land here). Assert: one 7-output request → exactly one `brain` load, zero reloads. Watch GBNF gen speed (~17 tok/s) for the multi-artefact wall time.

### 2026-09-06 — Phase 1 — Model Manager shipped, INV-1/2/7/8 real and green
Did:
- Built `src/rupantar/models/`: `runtime_base.py` (Runtime ABC, `terminate_process` SIGTERM→grace→SIGKILL, `wait_healthy`, `read_rss_bytes`), `_ports.py` (bind-test allocator), `runtime_stub.py` (child stdlib `http.server`, `python -m` entrypoint — zero model files), `registry.py` (`ModelEntry` + `Registry.from_config`; skips file/SHA when `runtime == "stub"`; real missing → `ModelFileMissingError` naming `scripts/fetch_models.sh`), `_support.py` (Lease/Event/ModelState/sinks), `manager.py` (async `acquire()` CM + `obtain/release`, refcount, one `asyncio.Condition` serialising load/evict/reap, `max_heavy_resident` eviction that waits for real process exit via `wait_process_gone`, LRU + idle-TTL reaper, external-death respawn, `status()`), `runtime_llama.py` (SIGKILL grace 10s; real-binary tests `@pytest.mark.slow`).
- `core/errors.py`: +`ModelError`/`UnknownModelError`/`ModelFileMissingError`/`RuntimeStartError`/`NoFreePortError`/`AcquireTimeoutError` (additive).
- `core/store.py`: +`events` table + `append_event`/`list_events`.
- `cli/main.py`: `models status` prints the residency table (deviation: not the planned `api/routes/models.py`).
- Made INV-2 (`test_single_resident`), INV-7 (`test_single_entry_point`), INV-8 (`test_unload_kills_process`) real. Also implemented INV-1 (`test_no_inprocess_models`) as a module-scope import scan (was a lying skip skeleton).
- Ran builder → verifier (PASS w/ warnings) → arch-guard (CLEAN).
Verified:
- `make check` → ruff ✓, format ✓ (38 files), mypy ✓ (18 files), `pytest tests/unit` → 84 passed / 1 slow-skip, `pytest tests/inv` → 6 passed / 4 skeleton
- Phase 1 verify `pytest tests/inv/test_single_resident.py tests/inv/test_unload_kills_process.py -q` → 2 passed
- `pytest -m slow` → 1 skipped (llama-server absent), 0 errors
- zero `.gguf`/`.onnx` on disk; no stray child procs; `models status` → 4-row table; `--help` → 4 commands
- `core/schemas.py` + `core/artefacts.py` untouched
Changed in this file:
- §1 phase→2, commit, check counts. §2 Phase 1 → DONE with build summary; §2 Phase 2 note (HTTP client gap). §3 INV-1/2/7/8 → PASS with method. §5 +7 deviations. §6 +2 blockers (llama unverified, laptop-16gb paths absent). §8 +3 env facts. §9 this block.
Next session should start with:
- Phase 2 — Text generation path. First decision: HTTP client for `models/client.py` (httpx vs stdlib `urllib`+`asyncio.to_thread`) — Phase 1 added no HTTP dep. Record the choice in §10 + `requirements.txt` if httpx. Use `test-stub` profile / stub runtime for all non-slow tests.

### 2026-09-06 — Phase 0 — scaffold and contracts shipped, `make check` green
Did:
- Applied the user's rulings A–O to the docs: rewrote `docs/SCHEMAS.md` (moved from root; added `SourceInput`/`TransformRequest`/`Job`/`JobStatus`/`ArtefactType`; removed `index` fields; `priority`+`ioc_type` enums; `artefact_type` → `Literal`; `confidence_notes` default `""`; language best-effort note). Updated `PLAN.md` (§2 Python 3.11-exact, §3 layout, §4 Transform vs Job, Phase 0 build list, Phase 1 stub-skip note, Phase 3 routes, Phase 8 version assert, §7 single `make check` def + fixture accumulation, rule 10 → `main`). Aligned `CLAUDE.md` `make check` wording + added 3.11 / frozen-contract bullets.
- Repo housekeeping: `master` → `main`; `SCHEMAS.md` → `docs/`, agent `.md` → `.claude/agents/`, `models.yaml` → `configs/` (fixed 9 invalid `1_000_000` YAML literals); removed committed `.DS_Store`; `uv python install 3.11` + `.venv` + `.python-version`.
- Built Phase 0 via a builder subagent: `pyproject.toml` (src layout, ruff/mypy+pydantic-plugin/pytest config), `requirements.txt` + lock stub, `Makefile`, `.gitignore`, `README`, `configs/policy.yaml`; `src/rupantar/` — `__init__`, `py.typed`, `core/{errors,config,schemas,artefacts,store}.py`, `cli/{__main__,main}.py`; `tests/` — conftest, 6 unit modules (57 tests), 8 inv skip-skeletons, fixtures (2 articles, PNG, 30s MP4, 7 artefact JSONs); `scripts/{make_fixtures(real),fetch_models,vendor_wheels,demo}.sh`.
Verified:
- `make check` → ruff ✓, `ruff format --check` ✓ (26 files), `mypy src` ✓ (10 files), `pytest tests/unit` → 57 passed, `pytest tests/inv` → 8 skipped
- `python -m rupantar.cli --help` → lists exactly transform, convert, selfcheck, models
- All 7 artefact models round-trip their fixture; re-parse stable
- INV-1/4/7/8 greps over `src/` → clean (no torch/transformers/subprocess/gc-unload/network libs)
- Largest src file `core/artefacts.py` = 356 lines (< 400); no function > ~25 lines
Changed in this file:
- Rewrote §1–§9 for Phase 0 completion; added frozen-contract + Python-3.11 + Transform/Job decisions; recorded 4 deviations; added env facts (Python, ffmpeg 8.1.2, llama-server/piper absent).
Next session should start with:
- Phase 1 — Model Manager. Restate its Definition of Done, list files. Note: `registry.py` skips existence/SHA checks when `runtime == "stub"`; `test-stub` profile in `configs/models.yaml` has no `path` keys. Consider installing `llama-server` for the real-model checks, or stay on `runtime_stub`.

---

## 10. Dependencies

Recorded per CLAUDE.md. Also in `requirements.txt` / `pyproject.toml`.

- **runtime** — `pydantic>=2.7`, `pydantic-settings>=2.2`, `PyYAML>=6.0`, `typer>=0.12`, `aiosqlite>=0.20`, `httpx>=0.27`
- **dev** (`[dev]` extra) — `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `types-PyYAML`
- **Phase 1 added no dependency** — Model Manager is stdlib only.
- **Phase 2 added `httpx>=0.27`** (resolved 0.28.1; transitively `anyio`, `certifi`, `h11`, `httpcore`, `idna`, `sniffio`). Used only in `models/client.py`, imported at module top like `aiosqlite`. FastAPI needs it at Phase 3 regardless. Not yet in `requirements-lock.txt`.
